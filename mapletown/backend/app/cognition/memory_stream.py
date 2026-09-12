import datetime as dt
import logging

from sqlalchemy.orm import Session

from app.cognition.prompts import build_importance_prompt
from app.cognition.vector_store import vector_store
from app.core.config import get_settings
from app.llm.client import llm
from app.models.cognition import Memory

logger = logging.getLogger("mapletown.memory")


class MemoryStreamService:
    """记忆流：写入、向量化、三因子检索、批量重要性打分。

    检索算法（Generative Agents 论文）：
        score = α·recency + β·importance + γ·relevance
        - recency: 距上次访问的指数衰减（默认 0.995^小时数）
        - importance: LLM 打的 1-10 分归一化
        - relevance: 与查询文本的 cosine 相似度
    """

    def add(
        self,
        db: Session,
        resident_id: int,
        content: str,
        mtype: str,
        sim_time: dt.datetime,
    ) -> Memory:
        memory = Memory(
            resident_id=resident_id,
            type=mtype,
            content=content,
            sim_time=sim_time,
            last_access_sim_time=sim_time,
        )
        db.add(memory)
        db.flush()
        return memory

    def recent(self, db: Session, resident_id: int, limit: int = 8) -> list[Memory]:
        return (
            db.query(Memory)
            .filter(Memory.resident_id == resident_id)
            .order_by(Memory.sim_time.desc(), Memory.id.desc())
            .limit(limit)
            .all()
        )

    async def retrieve(
        self,
        db: Session,
        resident_id: int,
        query: str,
        k: int = 8,
        now_sim: dt.datetime | None = None,
    ) -> list[tuple[Memory, dict]]:
        """三因子检索。返回 (记忆, 各因子得分) 列表，按综合分降序，并刷新 last_access。"""
        settings = get_settings()
        if now_sim is None:
            latest = self.recent(db, resident_id, limit=1)
            if not latest:
                return []
            now_sim = latest[0].sim_time

        candidates = await vector_store.query(resident_id, query, top_k=settings.retrieval_candidates)
        relevance_map = {c["memory_id"]: c["relevance"] for c in candidates}

        fresh_ids = [m.id for m in self.recent(db, resident_id, limit=3) if m.id not in relevance_map]
        all_ids = list(relevance_map) + fresh_ids
        if not all_ids:
            return []
        memories = db.query(Memory).filter(Memory.id.in_(all_ids)).all()

        scored: list[tuple[Memory, dict]] = []
        for m in memories:
            last_access = m.last_access_sim_time or m.sim_time
            hours = max(0.0, (now_sim - last_access).total_seconds() / 3600.0)
            factors = {
                "recency": settings.recency_decay_per_hour**hours,
                "importance": (m.importance if m.importance is not None else 5.0) / 10.0,
                "relevance": relevance_map.get(m.id, 0.0),
            }
            factors["score"] = round(
                settings.retrieval_alpha * factors["recency"]
                + settings.retrieval_beta * factors["importance"]
                + settings.retrieval_gamma * factors["relevance"],
                6,
            )
            scored.append((m, factors))

        scored.sort(key=lambda pair: pair[1]["score"], reverse=True)
        top = scored[:k]
        for m, _ in top:
            m.last_access_sim_time = now_sim
        return top

    async def retrieve_contents(
        self,
        db: Session,
        resident_id: int,
        query: str,
        k: int = 8,
        now_sim: dt.datetime | None = None,
    ) -> list[str]:
        rows = await self.retrieve(db, resident_id, query, k=k, now_sim=now_sim)
        return [m.content for m, _ in rows]

    async def score_pending(self, db: Session, limit: int = 24) -> int:
        """一次 LLM 调用批量打重要性分，随后统一向量化入库（省 token 的关键工程点）。"""
        pending = (
            db.query(Memory)
            .filter(Memory.importance.is_(None))
            .order_by(Memory.id)
            .limit(limit)
            .all()
        )
        if not pending:
            return 0
        data = await llm.chat_json(
            [
                {"role": "system", "content": "你是记忆重要性评估引擎，只输出合法 JSON。"},
                {"role": "user", "content": build_importance_prompt([{"id": m.id, "content": m.content} for m in pending])},
            ],
            temperature=0.1,
            max_tokens=600,
        )
        scores = data.get("scores", []) if isinstance(data, dict) else []
        score_map: dict[int, float] = {}
        for item in scores:
            try:
                score_map[int(item["id"])] = max(0.0, min(10.0, float(item["score"])))
            except (KeyError, TypeError, ValueError):
                continue
        for memory in pending:
            memory.importance = score_map.get(memory.id, 5.0)

        try:
            count = await vector_store.upsert(
                [
                    {"id": m.id, "resident_id": m.resident_id, "content": m.content}
                    for m in pending
                ]
            )
            for memory in pending:
                memory.embedding_id = f"chroma:{memory.id}"
            logger.debug("vectorized %s memories", count)
        except Exception:
            # 向量化失败不影响主流程（记忆仍在 SQLite，检索退化为时间+重要性）
            logger.exception("vectorize failed, retrieval degrades gracefully")
        return len(pending)


memory_stream = MemoryStreamService()
