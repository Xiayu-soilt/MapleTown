"""重建记忆向量库：python -m scripts.rebuild_vectors

适用场景：
- 老库升级（M2 之前产生的记忆从未向量化）
- 切换嵌入 provider 后（维度变化会自动清空重建 collection，此脚本负责回填）
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.cognition.vector_store import vector_store  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.cognition import Memory  # noqa: E402

BATCH = 64


async def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        total = db.query(Memory).filter(Memory.embedding_id.is_(None)).count()
        print(f"待向量化记忆: {total}")
        done = 0
        while True:
            batch = (
                db.query(Memory)
                .filter(Memory.embedding_id.is_(None))
                .order_by(Memory.id)
                .limit(BATCH)
                .all()
            )
            if not batch:
                break
            await vector_store.upsert(
                [{"id": m.id, "resident_id": m.resident_id, "content": m.content} for m in batch]
            )
            for m in batch:
                m.embedding_id = f"chroma:{m.id}"
            db.commit()
            done += len(batch)
            print(f"已向量化 {done}/{total}")
    print("rebuild done")


if __name__ == "__main__":
    asyncio.run(main())
