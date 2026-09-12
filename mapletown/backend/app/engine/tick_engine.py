import asyncio
import datetime as dt
import logging

from app.core.config import get_settings
from app.core.constants import LOCATIONS, WEEKDAY_CN, is_sleeping_hour, sim_day_of
from app.cognition import prompts
from app.cognition.memory_stream import memory_stream
from app.db.session import SessionLocal
from app.engine.dialogue import dialogue_engine
from app.engine.planning import planning_engine
from app.engine.reflection import reflection_engine
from app.llm.client import llm
from app.models.cognition import Memory
from app.models.world import Resident, SimState, TokenUsage
from app.services.events import emit_event

logger = logging.getLogger("mapletown.tick")

VALID_ACTIONS = {"move", "chat", "work", "rest", "continue"}

# DeepSeek 参考单价（元/百万 token）：输入约 2，输出约 8，用于成本估算
_COST_PER_M_INPUT = 2.0
_COST_PER_M_OUTPUT = 8.0


class TickEngine:
    """模拟时间引擎：心跳循环驱动整个小镇运转。

    每 tick 流程：时间推进 → 睡眠结算 → 感知 → LLM 并发决策 → 应用行动（含简版对话）
    → 观察记忆入库 → 批量重要性打分 → Token 用量落库 → 事件广播。
    """

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.is_running:
            return
        self._task = asyncio.create_task(self._run(), name="mapletown-tick-engine")
        logger.info("tick engine started")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("tick engine stopped")

    async def _run(self) -> None:
        settings = get_settings()
        while True:
            interval = 1.0
            try:
                interval = await self.tick_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("tick failed")
            await asyncio.sleep(interval)

    async def tick_once(self) -> float:
        settings = get_settings()
        db = SessionLocal()
        try:
            state = db.get(SimState, 1)
            if state is None or not state.running:
                return 1.0
            if self._check_budget(db, state):
                return 2.0

            prev_day = state.current_sim_day
            state.tick += 1
            state.sim_time = state.sim_time + dt.timedelta(minutes=settings.sim_minutes_per_tick)
            state.current_sim_day = sim_day_of(state.sim_time)
            if state.current_sim_day != prev_day:
                emit_event(db, state, "system", f"枫叶镇第 {state.current_sim_day} 天开始了", location="全镇")

            residents = db.query(Resident).order_by(Resident.id).all()
            sleeping = is_sleeping_hour(state.sim_time.hour)

            for r in residents:
                if sleeping:
                    if r.current_location != r.home:
                        r.current_location = r.home
                        emit_event(db, state, "move", f"{r.name} 回家休息", participants=[r.id], location=r.home)
                    r.current_activity = "睡觉"

            awake: list[Resident] = [] if sleeping else residents
            prev_snapshot = {r.id: (r.current_location, r.current_activity) for r in awake}

            try:
                await planning_engine.ensure_daily_plans(db, state, awake)
            except Exception:
                logger.exception("daily planning failed")

            plans_ctx: dict[int, tuple[str | None, str | None]] = {}
            for r in awake:
                plan = planning_engine.get_plan(db, r.id, state.current_sim_day)
                segment = planning_engine.current_segment(plan, state.sim_time)
                plans_ctx[r.id] = (
                    plan.daily_goal if plan else None,
                    f"{segment['start']}–{segment['end']} {segment['activity']}" if segment else None,
                )

            location_peers: dict[str, list[Resident]] = {}
            for r in awake:
                location_peers.setdefault(r.current_location, []).append(r)

            retrieval_results = await asyncio.gather(
                *[
                    memory_stream.retrieve_contents(
                        db, r.id, self._memory_query(r, location_peers), k=8, now_sim=state.sim_time
                    )
                    for r in awake
                ],
                return_exceptions=True,
            )
            recent_memories: dict[int, list[str]] = {}
            for r, result in zip(awake, retrieval_results):
                if isinstance(result, BaseException):
                    logger.warning("retrieval failed for %s: %s", r.name, result)
                    recent_memories[r.id] = [m.content for m in memory_stream.recent(db, r.id, limit=8)]
                else:
                    recent_memories[r.id] = result

            decisions = await asyncio.gather(
                *[
                    self._decide(
                        r,
                        state,
                        location_peers,
                        recent_memories[r.id],
                        plan_goal=plans_ctx[r.id][0],
                        plan_segment=plans_ctx[r.id][1],
                    )
                    for r in awake
                ],
                return_exceptions=True,
            )

            chats: list[tuple[Resident, Resident]] = []
            replans: list[tuple[Resident, str]] = []
            for r, decision in zip(awake, decisions):
                if isinstance(decision, BaseException):
                    logger.warning("decision failed for %s: %s", r.name, decision)
                    continue
                if isinstance(decision, dict) and str(decision.get("replan", "")).lower() == "true":
                    reason = str(decision.get("replan_reason") or "计划被打断").strip()[:60] or "计划被打断"
                    replans.append((r, reason))
                chat_pair = self._apply_decision(db, state, r, decision, residents)
                if chat_pair is not None:
                    chats.append(chat_pair)

            for r, reason in replans[:2]:
                try:
                    await planning_engine.replan(db, state, r, reason)
                except Exception:
                    logger.exception("replan failed for %s", r.name)

            selected: list[tuple[Resident, Resident]] = []
            busy: set[int] = set()
            for pair in chats:
                a, b = pair
                if a.id in busy or b.id in busy:
                    continue
                selected.append(pair)
                busy.update((a.id, b.id))
                if len(selected) >= settings.dialogue_per_tick:
                    break
            for a, b in selected:
                try:
                    await dialogue_engine.run(db, state, a, b)
                except Exception:
                    logger.exception("dialogue failed between %s and %s", a.name, b.name)

            self._write_observation_memories(db, state, awake, prev_snapshot)

            try:
                await memory_stream.score_pending(db)
            except Exception:
                logger.exception("importance scoring failed")

            reflect_busy = {rid for pair in selected for rid in (pair[0].id, pair[1].id)}
            try:
                await reflection_engine.check_and_run(db, state, awake, busy_ids=reflect_busy)
            except Exception:
                logger.exception("reflection scheduling failed")

            self._flush_usage(db, state.current_sim_day)
            db.commit()

            from app.services.event_bus import bus

            bus.publish(
                {
                    "type": "tick",
                    "tick": state.tick,
                    "sim_time": state.sim_time.isoformat(),
                    "sim_day": state.current_sim_day,
                }
            )
            return settings.tick_seconds / max(1, state.speed)
        finally:
            db.close()

    def _memory_query(self, resident: Resident, location_peers: dict[str, list[Resident]]) -> str:
        """构造检索 query：把当前处境（目标/地点/活动/在场的人）压缩成一句查询。"""
        p = resident.persona or {}
        peers = [q for q in location_peers.get(resident.current_location, []) if q.id != resident.id]
        peer_text = " ".join(
            f"{q.name}{'（' + (q.persona or {}).get('identity', '') + '）' if (q.persona or {}).get('identity') else ''}"
            for q in peers
        )
        return " ".join(
            x for x in [p.get("goal", ""), resident.current_activity, resident.current_location, peer_text] if x
        )

    async def _decide(
        self,
        resident: Resident,
        state: SimState,
        location_peers: dict[str, list[Resident]],
        memory_lines: list[str],
        plan_goal: str | None = None,
        plan_segment: str | None = None,
    ) -> dict | None:
        peers = [p for p in location_peers.get(resident.current_location, []) if p.id != resident.id]
        prompt = prompts.build_decision_prompt(
            name=resident.name,
            age=resident.age,
            persona=resident.persona or {},
            sim_day=state.current_sim_day,
            weekday=WEEKDAY_CN[state.sim_time.weekday()],
            clock=state.sim_time.strftime("%H:%M"),
            hour=state.sim_time.hour,
            minute=state.sim_time.minute,
            location=resident.current_location,
            activity=resident.current_activity,
            workplace=resident.workplace,
            peers=[
                {"name": p.name, "identity": (p.persona or {}).get("identity", ""), "activity": p.current_activity}
                for p in peers
            ],
            memory_lines=memory_lines,
            locations=LOCATIONS,
            plan_goal=plan_goal,
            plan_segment=plan_segment,
        )
        data = await llm.chat_json(
            [
                {"role": "system", "content": prompts.DECISION_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=300,
        )
        return data if isinstance(data, dict) else None

    def _apply_decision(
        self,
        db,
        state: SimState,
        resident: Resident,
        decision: dict | None,
        all_residents: list[Resident],
    ) -> tuple[Resident, Resident] | None:
        if not isinstance(decision, dict):
            return None
        action = str(decision.get("action", "continue")).strip().lower()
        if action not in VALID_ACTIONS:
            action = "continue"
        activity = str(decision.get("activity") or "").strip()[:60]

        if action == "move":
            target = decision.get("target_location")
            if target in LOCATIONS and target != resident.current_location:
                resident.current_location = target
                resident.current_activity = activity or "在路上"
                emit_event(db, state, "move", f"{resident.name} 前往 {target}", participants=[resident.id], location=target)
                memory_stream.add(db, resident.id, f"你前往了{target}，{resident.current_activity}", "action", state.sim_time)
            return None

        if action == "chat":
            partner_name = str(decision.get("chat_with") or "").strip()
            partner = next((p for p in all_residents if p.name == partner_name), None)
            if (
                partner is not None
                and partner.id != resident.id
                and partner.current_location == resident.current_location
                and partner.current_activity != "睡觉"
            ):
                resident.current_activity = f"正和 {partner.name} 聊天"
                partner.current_activity = f"正和 {resident.name} 聊天"
                emit_event(
                    db,
                    state,
                    "chat",
                    f"{resident.name} 拉住了 {partner.name} 开始聊天",
                    participants=[resident.id, partner.id],
                    location=resident.current_location,
                )
                return (resident, partner)
            action = "continue"

        if activity and activity != resident.current_activity:
            resident.current_activity = activity
            emit_event(db, state, "act", f"{resident.name} {activity}", participants=[resident.id], location=resident.current_location)
            memory_stream.add(db, resident.id, f"你开始{activity}（在{resident.current_location}）", "action", state.sim_time)
        return None

    def _write_observation_memories(self, db, state: SimState, awake: list[Resident], prev_snapshot: dict) -> None:
        by_location: dict[str, list[Resident]] = {}
        for r in awake:
            by_location.setdefault(r.current_location, []).append(r)
        for r in awake:
            changed = []
            for p in by_location.get(r.current_location, []):
                if p.id == r.id:
                    continue
                if prev_snapshot.get(p.id) != (p.current_location, p.current_activity):
                    changed.append(f"{p.name}正在{p.current_activity}")
            if changed:
                content = f"在{r.current_location}，你注意到" + "、".join(changed[:4])
                memory_stream.add(db, r.id, content, "observation", state.sim_time)

    def _check_budget(self, db, state: SimState) -> bool:
        settings = get_settings()
        row = db.query(TokenUsage).filter(TokenUsage.sim_day == state.current_sim_day).first()
        used = (row.prompt_tokens + row.completion_tokens) if row is not None else 0
        if used < settings.daily_token_budget:
            return False
        state.running = False
        emit_event(db, state, "system", "今日 Token 预算已耗尽，模拟自动暂停", location="全镇")
        db.commit()
        return True

    def _flush_usage(self, db, sim_day: int) -> None:
        delta = llm.take_usage_delta()
        if delta["calls"] <= 0:
            return
        row = db.query(TokenUsage).filter(TokenUsage.sim_day == sim_day).first()
        if row is None:
            row = TokenUsage(sim_day=sim_day)
            db.add(row)
            db.flush()
        row.calls += delta["calls"]
        row.prompt_tokens += delta["prompt_tokens"]
        row.completion_tokens += delta["completion_tokens"]
        row.cost_estimate += round(
            (delta["prompt_tokens"] * _COST_PER_M_INPUT + delta["completion_tokens"] * _COST_PER_M_OUTPUT) / 1_000_000,
            6,
        )


tick_engine = TickEngine()
