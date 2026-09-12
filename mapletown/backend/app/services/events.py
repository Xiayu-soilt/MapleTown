from sqlalchemy.orm import Session

from app.models.world import SimState, WorldEvent
from app.services.event_bus import bus


def emit_event(
    db: Session,
    state: SimState,
    etype: str,
    content: str,
    participants: list[int] | None = None,
    location: str | None = None,
) -> WorldEvent:
    """写库 + 实时广播，事件流（SSE）与小镇时间线共用此入口。"""
    participants = participants or []
    event = WorldEvent(
        tick=state.tick,
        sim_time=state.sim_time,
        type=etype,
        content=content,
        location=location,
        participants=participants,
    )
    db.add(event)
    db.flush()
    bus.publish(
        {
            "type": etype,
            "tick": state.tick,
            "sim_time": state.sim_time.isoformat(),
            "content": content,
            "location": location,
            "participants": participants,
        }
    )
    return event
