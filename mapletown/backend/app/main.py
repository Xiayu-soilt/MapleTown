import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, conversations, events, llm as llm_routes, residents, sim
from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.engine.seed_data import ensure_initialized
from app.engine.tick_engine import tick_engine
from app.models import Base

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def _migrate_sqlite() -> None:
    """create_all 不会 ALTER 已有表：为旧库补齐 M3 新增列。"""
    from sqlalchemy import inspect, text

    column_additions = {
        "conversations": {"participants": "JSON", "a_summary": "TEXT", "b_summary": "TEXT"},
        "reflections": {"memory_id": "INTEGER"},
    }
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, cols in column_additions.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for col, ddl in cols.items():
                if col not in existing:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN "{col}" {ddl}'))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()
    with SessionLocal() as db:
        ensure_initialized(db)
    await tick_engine.start()
    yield
    await tick_engine.stop()


settings = get_settings()
app = FastAPI(
    title="MapleTown API",
    description="枫叶镇 · AI 小镇观测站（Generative Agents 产品化）",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for route in (auth.router, sim.router, residents.router, events.router, conversations.router, llm_routes.router):
    app.include_router(route, prefix="/api/v1")


@app.get("/")
def root():
    return {"app": "MapleTown API", "docs": "/docs", "status": "ok"}
