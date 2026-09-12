import datetime as dt
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.cognition import prompts
from app.cognition.memory_stream import memory_stream
from app.cognition.vector_store import vector_store
from app.core.config import get_settings
from app.llm.client import llm
from app.models.cognition import Memory, Reflection
from app.models.world import Resident, SimState
from app.services.events import emit_event

logger = logging.getLogger("mapletown.reflection")

MAX_SOURCE_MEMORIES = 100
MAX_QUESTIONS = 3
MAX_INSIGHTS_PER_QUESTION = 2
MAX_INSIGHTS = 3
REFLECTION_IMPORTANCE_CAP = 9.0


class ReflectionEngine:
    """反思引擎（论文两步法）：

    触发：自上次反思以来记忆的累积重要性 ≥ 阈值（反思产生的记忆同样计入——级联洞察）。
    管线：① 取材（上次反思以来的已打分记忆 ≤100 条，不足则跳过）
          ② 提问（LLM 提炼 2~3 个高层问题）
          ③ 求证（每个问题 → 三因子检索 top-8 证据）
          ④ 合成（LLM 生成带 source 记忆 id 溯源的洞察）
          ⑤ 入库（Memory(type=reflection) 立即向量化 + Reflection 行记录双向链）
          ⑥ 事件（emit reflect，观测价值最高的时刻）
    """

    def last_reflection_time(self, db: Session, resident_id: int) -> dt.datetime | None:
        row = (
            db.query(Reflection)
            .filter(Reflection.resident_id == resident_id)
            .order_by(Reflection.sim_time.desc(), Reflection.id.desc())
            .first()
        )
        return row.sim_time if row else None

    def pending_stats(self, db: Session, resident_id: int) -> tuple[float, int]:
        """自上次反思以来的 (累积重要性, 已打分记忆条数)。

        用 >= 比较：反思产生的记忆与 Reflection 同刻，严格 > 会把它们排除在
        下一轮累积之外，违背"洞察级联出更深洞察"的论文特性。
        """
        query = db.query(Memory).filter(
            Memory.resident_id == resident_id,
            Memory.importance.isnot(None),
        )
        since = self.last_reflection_time(db, resident_id)
        if since is not None:
            query = query.filter(Memory.sim_time >= since)
        value, count = query.with_entities(
            func.coalesce(func.sum(Memory.importance), 0.0), func.count(Memory.id)
        ).one()
        return float(value or 0.0), int(count or 0)

    def fetch_material(self, db: Session, resident_id: int) -> list[Memory]:
        """上次反思以来的已打分记忆（新→旧取 ≤100 条，返回旧→新顺序）。"""
        query = db.query(Memory).filter(
            Memory.resident_id == resident_id,
            Memory.importance.isnot(None),
        )
        since = self.last_reflection_time(db, resident_id)
        if since is not None:
            query = query.filter(Memory.sim_time >= since)
        rows = query.order_by(Memory.sim_time.desc(), Memory.id.desc()).limit(MAX_SOURCE_MEMORIES).all()
        return list(reversed(rows))

    async def check_and_run(
        self,
        db: Session,
        state: SimState,
        awake: list[Resident],
        busy_ids: set[int] | None = None,
    ) -> int:
        """tick 调度入口：累积值超阈值的清醒居民（不在对话中）逐个跑反思，每 tick ≤N 人。"""
        settings = get_settings()
        busy = busy_ids or set()
        done = 0
        for r in awake:
            if done >= settings.reflection_per_tick:
                break
            if r.id in busy:
                continue
            value, count = self.pending_stats(db, r.id)
            if value < settings.reflection_threshold or count < settings.reflection_min_memories:
                continue
            try:
                await self.reflect(db, state, r)
            except Exception:
                # 失败不落任何 Reflection 行，阈值累积值保留待下次重试
                logger.exception("reflection failed for %s", r.name)
            done += 1
        return done

    async def reflect(self, db: Session, state: SimState, resident: Resident) -> list[Reflection]:
        """单次反思管线。失败时不落任何 Reflection 行，阈值累积值保留待下次。"""
        settings = get_settings()
        material = self.fetch_material(db, resident.id)
        if len(material) < settings.reflection_min_memories:
            return []
        p = resident.persona or {}

        data = await llm.chat_json(
            [
                {"role": "system", "content": prompts.REFLECTION_SYSTEM},
                {
                    "role": "user",
                    "content": prompts.build_reflection_questions_prompt(
                        name=resident.name,
                        identity=p.get("identity", ""),
                        memory_lines=[f"{m.id}: {m.content}" for m in material],
                    ),
                },
            ],
            temperature=0.7,
            max_tokens=300,
        )
        questions: list[str] = []
        if isinstance(data, dict):
            for q in (data.get("questions") or [])[:MAX_QUESTIONS]:
                text = str(q).strip()
                if text:
                    questions.append(text[:80])
        if not questions:
            return []

        material_ids = {m.id for m in material}
        insights: list[dict] = []
        for question in questions:
            try:
                evidence = await memory_stream.retrieve(
                    db, resident.id, question, k=8, now_sim=state.sim_time
                )
            except Exception:
                logger.exception("reflection evidence retrieval failed: %s", question)
                continue
            if not evidence:
                continue
            try:
                sdata = await llm.chat_json(
                    [
                        {"role": "system", "content": prompts.REFLECTION_SYSTEM},
                        {
                            "role": "user",
                            "content": prompts.build_reflection_insights_prompt(
                                name=resident.name,
                                identity=p.get("identity", ""),
                                question=question,
                                evidence_lines=[f"{m.id}: {m.content}" for m, _ in evidence],
                            ),
                        },
                    ],
                    temperature=0.5,
                    max_tokens=400,
                )
            except Exception:
                logger.exception("reflection synthesis failed: %s", question)
                continue
            insights.extend(self._clean_insights(sdata, valid_ids=material_ids | {m.id for m, _ in evidence}))

        created: list[Reflection] = []
        for ins in insights[:MAX_INSIGHTS]:
            memory = memory_stream.add(db, resident.id, ins["content"], "reflection", state.sim_time)
            memory.importance = ins["importance"]
            try:
                await vector_store.upsert(
                    [{"id": memory.id, "resident_id": resident.id, "content": memory.content}]
                )
                memory.embedding_id = f"chroma:{memory.id}"
            except Exception:
                logger.exception("reflection vectorize failed, degrades to recency retrieval")
            reflection = Reflection(
                resident_id=resident.id,
                content=ins["content"],
                source_memory_ids=ins["source_ids"],
                sim_time=state.sim_time,
                memory_id=memory.id,
            )
            db.add(reflection)
            db.flush()
            emit_event(
                db,
                state,
                "reflect",
                f"{resident.name} 陷入了沉思：{ins['content']}",
                participants=[resident.id],
                location=resident.current_location,
            )
            created.append(reflection)
        return created

    @staticmethod
    def _clean_insights(data, valid_ids: set[int]) -> list[dict]:
        """清洗合成输出：过滤空结论/幻觉 id，重要度 clamp 到 [1, 9]。"""
        out: list[dict] = []
        if not isinstance(data, dict):
            return out
        for item in (data.get("insights") or [])[:MAX_INSIGHTS_PER_QUESTION]:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "").strip()[:120]
            source_ids = [sid for sid in item.get("source_ids") or [] if sid in valid_ids]
            if not content or not source_ids:
                continue
            try:
                importance = max(1.0, min(REFLECTION_IMPORTANCE_CAP, float(item.get("importance", 8))))
            except (TypeError, ValueError):
                importance = 8.0
            out.append({"content": content, "source_ids": source_ids[:5], "importance": importance})
        return out


reflection_engine = ReflectionEngine()
