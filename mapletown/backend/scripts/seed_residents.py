"""手动重建种子数据：python -m scripts.seed_residents（服务启动时也会自动播种，本脚本仅幂等兜底）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal, engine  # noqa: E402
from app.engine.seed_data import ensure_initialized  # noqa: E402
from app.models import Base  # noqa: E402

Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    ensure_initialized(db)
print("seed done")
