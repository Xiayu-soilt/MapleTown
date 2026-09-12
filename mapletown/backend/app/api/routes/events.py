import asyncio
import json

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.world import SimState, WorldEvent
from app.schemas import EventOut
from app.services.event_bus import bus

router = APIRouter(tags=["events"])


@router.get("/events")
def list_events(limit: int = 50, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 200))
    rows = db.query(WorldEvent).order_by(WorldEvent.id.desc()).limit(limit).all()
    return [EventOut.model_validate(e) for e in reversed(rows)]


@router.get("/stream/feed")
async def stream_feed(request: Request, db: Session = Depends(get_db)):
    state = db.get(SimState, 1)
    init = {
        "type": "tick",
        "tick": state.tick if state else 0,
        "sim_time": state.sim_time.isoformat() if state else None,
        "sim_day": state.current_sim_day if state else 1,
    }
    queue = bus.subscribe()

    async def generator():
        try:
            yield {"event": "tick", "data": json.dumps(init, ensure_ascii=False)}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
                    continue
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event, ensure_ascii=False, default=str),
                }
        finally:
            bus.unsubscribe(queue)

    return EventSourceResponse(generator())
