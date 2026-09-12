import asyncio
import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.cognition import prompts
from app.cognition.memory_stream import memory_stream
from app.core.config import get_settings
from app.core.constants import WEEKDAY_CN
from app.llm.client import llm
from app.models.cognition import Plan, Reflection
from app.models.world import Resident, SimState
from app.services.events import emit_event

logger = logging.getLogger("mapletown.planning")

DAY_START_HOUR = 7
LATE_PLAN_HOUR = 9


def _to_minutes(value) -> int | None:
    try:
        hh, mm = str(value).strip().split(":")
        h, m = int(hh), int(mm)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h * 60 + m
    except (ValueError, AttributeError):
        return None
    return None


def _fmt(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def clean_segments(raw) -> list[dict]:
    """清洗 LLM 输出的 segments：丢掉时间畸形/空活动的段，按开始时间排序。"""
    out: list[dict] = []
    for seg in raw if isinstance(raw, list) else []:
        if not isinstance(seg, dict):
            continue
        start = _to_minutes(seg.get("start"))
        end = _to_minutes(seg.get("end"))
        activity = str(seg.get("activity") or "").strip()[:40]
        if start is None or end is None or end <= start or not activity:
            continue
        out.append({"start": _fmt(start), "end": _fmt(end), "activity": activity})
    out.sort(key=lambda s: _to_minutes(s["start"]))
    return out


class PlanningEngine:
    """日程规划：清晨生成当日计划，LLM 可标记 replan 重排剩余时段（1 次/日）。"""

    def get_plan(self, db: Session, resident_id: int, sim_day: int) -> Plan | None:
        return (
            db.query(Plan)
            .filter(Plan.resident_id == resident_id, Plan.sim_day == sim_day)
            .first()
        )

    @staticmethod
    def segments_of(plan: Plan | None) -> list[dict]:
        if plan is None or not isinstance(plan.hourly, dict):
            return []
        return plan.hourly.get("segments", []) or []

    def current_segment(self, plan: Plan | None, sim_time: dt.datetime) -> dict | None:
        now_min = sim_time.hour * 60 + sim_time.minute
        for seg in self.segments_of(plan):
            start, end = _to_minutes(seg.get("start")), _to_minutes(seg.get("end"))
            if start is None or end is None:
                continue
            if start <= now_min < end:
                return seg
        return None

    async def ensure_daily_plans(self, db: Session, state: SimState, awake: list[Resident]) -> None:
        """为当日尚无计划的居民生成日程（每 tick 错峰 ≤N 人）。

        清醒时段内任何时候都可以补规划：晚于 LATE_PLAN_HOUR 只规划剩余时段，
        避免暂停/恢复后错过清晨窗口的居民整天没有日程。
        """
        if state.sim_time.hour < DAY_START_HOUR:
            return
        settings = get_settings()
        pending = [
            r
            for r in awake
            if self.get_plan(db, r.id, state.current_sim_day) is None
        ][: settings.plan_per_tick]
        if not pending:
            return
        results = await asyncio.gather(
            *[self.generate(db, state, r) for r in pending], return_exceptions=True
        )
        for r, result in zip(pending, results):
            if isinstance(result, BaseException):
                logger.warning("planning failed for %s: %s", r.name, result)

    async def generate(self, db: Session, state: SimState, resident: Resident) -> Plan | None:
        """生成（或重新生成）当日日程并落库，失败返回 None（决策退化为无计划模式）。"""
        try:
            memory_lines = await memory_stream.retrieve_contents(
                db, resident.id, "昨天的经历和没做完的事", k=5, now_sim=state.sim_time
            )
        except Exception:
            logger.exception("planning memory retrieval failed for %s", resident.name)
            memory_lines = []
        last_reflection = (
            db.query(Reflection)
            .filter(Reflection.resident_id == resident.id)
            .order_by(Reflection.sim_time.desc())
            .first()
        )
        data = await llm.chat_json(
            [
                {"role": "system", "content": prompts.PLANNING_SYSTEM},
                {
                    "role": "user",
                    "content": prompts.build_planning_prompt(
                        name=resident.name,
                        age=resident.age,
                        persona=resident.persona or {},
                        sim_day=state.current_sim_day,
                        weekday=WEEKDAY_CN[state.sim_time.weekday()],
                        memory_lines=memory_lines,
                        last_reflection=last_reflection.content if last_reflection else None,
                        from_time=_fmt(state.sim_time.hour * 60 + state.sim_time.minute)
                        if state.sim_time.hour >= LATE_PLAN_HOUR
                        else None,
                    ),
                },
            ],
            temperature=0.6,
            max_tokens=600,
        )
        segments = clean_segments(data.get("segments")) if isinstance(data, dict) else []
        if not segments:
            logger.warning("planning produced no valid segments for %s", resident.name)
            return None
        daily_goal = str(data.get("daily_goal") or "").strip()[:80]
        plan = self.get_plan(db, resident.id, state.current_sim_day)
        if plan is None:
            plan = Plan(resident_id=resident.id, sim_day=state.current_sim_day)
            db.add(plan)
        plan.daily_goal = daily_goal
        plan.hourly = {"segments": segments, "replanned": False}
        plan.updated_at = state.sim_time
        db.flush()
        emit_event(
            db,
            state,
            "plan",
            f"{resident.name} 制定了今天的计划：{daily_goal}",
            participants=[resident.id],
            location=resident.current_location,
        )
        return plan

    async def replan(self, db: Session, state: SimState, resident: Resident, reason: str) -> Plan | None:
        """重排从当前时间起的剩余日程；已过去的时段保留，每人每天限一次。"""
        plan = self.get_plan(db, resident.id, state.current_sim_day)
        if plan is None:
            return None
        if isinstance(plan.hourly, dict) and plan.hourly.get("replanned"):
            return None
        now_min = state.sim_time.hour * 60 + state.sim_time.minute
        kept = [
            seg
            for seg in self.segments_of(plan)
            if (_to_minutes(seg.get("end")) or 0) <= now_min
        ]
        try:
            memory_lines = await memory_stream.retrieve_contents(
                db, resident.id, "今天发生了什么、计划为什么被打乱", k=5, now_sim=state.sim_time
            )
        except Exception:
            memory_lines = []
        data = await llm.chat_json(
            [
                {"role": "system", "content": prompts.PLANNING_SYSTEM},
                {
                    "role": "user",
                    "content": prompts.build_planning_prompt(
                        name=resident.name,
                        age=resident.age,
                        persona=resident.persona or {},
                        sim_day=state.current_sim_day,
                        weekday=WEEKDAY_CN[state.sim_time.weekday()],
                        memory_lines=memory_lines,
                        last_reflection=None,
                        from_time=_fmt(now_min),
                    )
                    + f"\n\n注意：你今天原本的计划已因「{reason}」被打乱，请只重排当前之后的安排。",
                },
            ],
            temperature=0.6,
            max_tokens=500,
        )
        fresh = clean_segments(data.get("segments")) if isinstance(data, dict) else []
        if not fresh:
            logger.warning("replan produced no valid segments for %s", resident.name)
            return None
        plan.daily_goal = str(data.get("daily_goal") or plan.daily_goal).strip()[:80]
        plan.hourly = {"segments": kept + fresh, "replanned": True}
        plan.updated_at = state.sim_time
        db.flush()
        emit_event(
            db,
            state,
            "plan",
            f"{resident.name} 调整了今天的安排：{plan.daily_goal}（原因：{reason[:30]}）",
            participants=[resident.id],
            location=resident.current_location,
        )
        return plan


planning_engine = PlanningEngine()
