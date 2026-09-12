import datetime as dt
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.constants import SIM_START, sim_day_of
from app.db.session import get_db
from app.models.cognition import Conversation, ConversationTurn
from app.models.world import Resident
from app.schemas import (
    ConversationDetail,
    ConversationOut,
    ConversationParticipant,
    ConversationTurnOut,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _participants_of(resident_map: dict[int, Resident], ids: list) -> list[ConversationParticipant]:
    return [
        ConversationParticipant(id=r.id, name=r.name, avatar_color=r.avatar_color)
        for rid in ids
        if (r := resident_map.get(rid)) is not None
    ]


def _conversation_out(
    conv: Conversation,
    resident_map: dict[int, Resident],
    turn_count: int,
) -> ConversationOut:
    return ConversationOut(
        id=conv.id,
        sim_time=conv.sim_time,
        sim_day=sim_day_of(conv.sim_time),
        location=conv.location,
        status=conv.status,
        participants=_participants_of(resident_map, conv.participants or []),
        turn_count=turn_count,
        a_summary=conv.a_summary,
        b_summary=conv.b_summary,
    )


@router.get("", response_model=list[ConversationOut])
def list_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    day: int | None = None,
    resident_id: int | None = None,
    db: Session = Depends(get_db),
):
    """对话列表（新→旧）。可按模拟日、居民过滤。"""
    query = db.query(Conversation).order_by(Conversation.id.desc())
    if day is not None:
        start = SIM_START + dt.timedelta(days=day - 1)
        end = SIM_START + dt.timedelta(days=day)
        query = query.filter(Conversation.sim_time >= start, Conversation.sim_time < end)

    convs: list[Conversation] = []
    for conv in query:
        if resident_id is not None and resident_id not in (conv.participants or []):
            continue
        convs.append(conv)
        if len(convs) >= limit:
            break

    turn_counts: dict[int, int] = defaultdict(int)
    if convs:
        rows = db.query(ConversationTurn.conversation_id).filter(
            ConversationTurn.conversation_id.in_([c.id for c in convs])
        )
        for (cid,) in rows:
            turn_counts[cid] += 1
    resident_map = {r.id: r for r in db.query(Resident).all()}
    return [_conversation_out(c, resident_map, turn_counts.get(c.id, 0)) for c in convs]


@router.get("/{cid}", response_model=ConversationDetail)
def conversation_detail(cid: int, db: Session = Depends(get_db)):
    """对话详情：含全部轮次与双方视角总结。"""
    conv = db.get(Conversation, cid)
    if conv is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    turns = (
        db.query(ConversationTurn, Resident.name)
        .join(Resident, Resident.id == ConversationTurn.speaker_id)
        .filter(ConversationTurn.conversation_id == cid)
        .order_by(ConversationTurn.turn_no)
        .all()
    )
    resident_map = {r.id: r for r in db.query(Resident).all()}
    out = _conversation_out(conv, resident_map, len(turns))
    return ConversationDetail(
        **out.model_dump(),
        turns=[
            ConversationTurnOut(
                turn_no=t.turn_no,
                speaker_id=t.speaker_id,
                speaker_name=name,
                content=t.content,
            )
            for t, name in turns
        ],
    )
