import datetime as dt

from sqlalchemy.orm import Session

from app.models.world import Relationship


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def update_relationship(
    db: Session,
    a_id: int,
    b_id: int,
    delta: float,
    sim_time: dt.datetime,
    sentiment: str | None = None,
) -> Relationship:
    lo, hi = (a_id, b_id) if a_id < b_id else (b_id, a_id)
    row = db.query(Relationship).filter(Relationship.a_id == lo, Relationship.b_id == hi).first()
    if row is None:
        row = Relationship(a_id=lo, b_id=hi, closeness=clamp(0.3 + delta), updated_sim_time=sim_time)
        if sentiment:
            row.sentiment = sentiment
        db.add(row)
    else:
        row.closeness = clamp(row.closeness + delta)
        row.updated_sim_time = sim_time
        if sentiment:
            row.sentiment = sentiment
    db.flush()
    return row
