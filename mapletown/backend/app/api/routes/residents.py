import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.cognition.embeddings import embedding_service
from app.cognition.memory_stream import memory_stream
from app.core.config import get_settings
from app.db.session import get_db
from app.engine.planning import planning_engine
from app.models.cognition import Memory, Reflection
from app.models.world import Resident, SimState
from app.schemas import (
    MemoryListOut,
    MemoryOut,
    MemorySearchOut,
    PlanOut,
    PlanSegment,
    ReflectionListOut,
    ReflectionOut,
    ReflectionSourceOut,
    ResidentDetail,
)

router = APIRouter(prefix="/residents", tags=["residents"])


def _resident_out(r: Resident) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "age": r.age,
        "avatar_color": r.avatar_color,
        "identity": (r.persona or {}).get("identity", ""),
        "workplace": r.workplace,
        "current_location": r.current_location,
        "current_activity": r.current_activity,
    }


def _memory_out(m: Memory) -> MemoryOut:
    out = MemoryOut.model_validate(m)
    out.vectorized = m.embedding_id is not None
    return out


@router.get("")
def list_residents(db: Session = Depends(get_db)):
    return [_resident_out(r) for r in db.query(Resident).order_by(Resident.id).all()]


@router.get("/{rid}", response_model=None)
def resident_detail(rid: int, db: Session = Depends(get_db)):
    r = db.get(Resident, rid)
    if r is None:
        raise HTTPException(status_code=404, detail="居民不存在")
    data = _resident_out(r)
    data["persona"] = r.persona or {}
    data["memories"] = [_memory_out(m) for m in memory_stream.recent(db, r.id, limit=10)]
    return ResidentDetail(**data)


@router.get("/{rid}/memories", response_model=MemoryListOut)
def resident_memories(
    rid: int,
    type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    if db.get(Resident, rid) is None:
        raise HTTPException(status_code=404, detail="居民不存在")
    query = db.query(Memory).filter(Memory.resident_id == rid)
    if type:
        query = query.filter(Memory.type == type)
    total = query.count()
    items = query.order_by(Memory.id.desc()).offset(offset).limit(max(1, min(limit, 100))).all()
    return MemoryListOut(total=total, items=[_memory_out(m) for m in reversed(items)])


@router.get("/{rid}/plan", response_model=PlanOut)
def resident_plan(rid: int, day: int | None = None, db: Session = Depends(get_db)):
    """居民的当日日程（day 缺省取模拟当前日）。"""
    if db.get(Resident, rid) is None:
        raise HTTPException(status_code=404, detail="居民不存在")
    if day is None:
        state = db.get(SimState, 1)
        day = state.current_sim_day if state is not None else 1
    plan = planning_engine.get_plan(db, rid, day)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"第 {day} 天该居民暂无日程")
    hourly = plan.hourly if isinstance(plan.hourly, dict) else {}
    return PlanOut(
        resident_id=plan.resident_id,
        sim_day=plan.sim_day,
        daily_goal=plan.daily_goal or "",
        segments=[PlanSegment(**seg) for seg in hourly.get("segments", [])],
        replanned=bool(hourly.get("replanned", False)),
    )


@router.get("/{rid}/reflections", response_model=ReflectionListOut)
def resident_reflections(
    rid: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """反思列表：洞察 + 溯源到具体记忆（反思树：源记忆可为反思，经 reflection_id 递归）。"""
    if db.get(Resident, rid) is None:
        raise HTTPException(status_code=404, detail="居民不存在")
    total = db.query(Reflection).filter(Reflection.resident_id == rid).count()
    rows = (
        db.query(Reflection)
        .filter(Reflection.resident_id == rid)
        .order_by(Reflection.id.desc())
        .limit(limit)
        .all()
    )
    source_ids = {sid for r in rows for sid in (r.source_memory_ids or [])}
    source_map: dict[int, Memory] = {}
    if source_ids:
        source_map = {m.id: m for m in db.query(Memory).filter(Memory.id.in_(source_ids)).all()}
    own_memory_ids = [r.memory_id for r in rows if r.memory_id is not None]
    own_map = {m.id: m for m in db.query(Memory).filter(Memory.id.in_(own_memory_ids)).all()} if own_memory_ids else {}
    reflection_mem_ids = [m.id for m in source_map.values() if m.type == "reflection"]
    refl_of_memory = (
        {rf.memory_id: rf.id for rf in db.query(Reflection).filter(Reflection.memory_id.in_(reflection_mem_ids)).all()}
        if reflection_mem_ids
        else {}
    )

    def _source_out(sid: int) -> ReflectionSourceOut:
        m = source_map.get(sid)
        return ReflectionSourceOut(
            id=sid,
            type=m.type if m else "unknown",
            content=m.content if m else "",
            sim_time=m.sim_time if m else dt.datetime.min,
            importance=m.importance if m else None,
            reflection_id=refl_of_memory.get(sid),
        )

    items = [
        ReflectionOut(
            id=r.id,
            content=r.content,
            sim_time=r.sim_time,
            importance=own_map[r.memory_id].importance if r.memory_id in own_map else None,
            source_memory_ids=r.source_memory_ids or [],
            sources=[_source_out(sid) for sid in (r.source_memory_ids or [])],
            memory_id=r.memory_id,
        )
        for r in rows
    ]
    return ReflectionListOut(total=total, items=items)


@router.get("/{rid}/memory-search", response_model=MemorySearchOut)
async def resident_memory_search(
    rid: int,
    q: str = Query(min_length=1, max_length=200),
    k: int = Query(default=8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """三因子检索观测：返回每条记忆的 recency/importance/relevance/score 得分分解。"""
    if db.get(Resident, rid) is None:
        raise HTTPException(status_code=404, detail="居民不存在")
    settings = get_settings()
    state = db.get(SimState, 1)
    now_sim = state.sim_time if state is not None else None
    try:
        rows = await memory_stream.retrieve(db, rid, q, k=k, now_sim=now_sim)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"检索失败: {exc}") from exc
    db.commit()
    items = []
    for m, factors in rows:
        item = _memory_out(m).model_dump()
        item["factors"] = factors
        items.append(item)
    return MemorySearchOut(
        query=q,
        provider=embedding_service.provider or "unloaded",
        weights={
            "alpha": settings.retrieval_alpha,
            "beta": settings.retrieval_beta,
            "gamma": settings.retrieval_gamma,
        },
        items=items,
    )
