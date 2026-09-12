import datetime as dt

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Resident(Base):
    __tablename__ = "residents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    age: Mapped[int] = mapped_column(Integer)
    avatar_color: Mapped[str] = mapped_column(String(20), default="#3C2ECA")
    persona: Mapped[dict] = mapped_column(JSON)
    home: Mapped[str] = mapped_column(String(32), default="枫叶公寓")
    workplace: Mapped[str] = mapped_column(String(32))
    current_location: Mapped[str] = mapped_column(String(32), default="枫叶公寓")
    current_activity: Mapped[str] = mapped_column(String(128), default="睡觉")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class WorldEvent(Base):
    __tablename__ = "world_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    tick: Mapped[int] = mapped_column(Integer, index=True)
    sim_time: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    type: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(32), nullable=True)
    participants: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (UniqueConstraint("a_id", "b_id", name="uq_relationship_pair"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    a_id: Mapped[int] = mapped_column(ForeignKey("residents.id"), index=True)
    b_id: Mapped[int] = mapped_column(ForeignKey("residents.id"), index=True)
    closeness: Mapped[float] = mapped_column(Float, default=0.3)
    sentiment: Mapped[str] = mapped_column(String(16), default="neutral")
    updated_sim_time: Mapped[dt.datetime] = mapped_column(DateTime)


class SimState(Base):
    __tablename__ = "sim_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sim_time: Mapped[dt.datetime] = mapped_column(DateTime)
    tick: Mapped[int] = mapped_column(Integer, default=0)
    speed: Mapped[int] = mapped_column(Integer, default=1)
    running: Mapped[bool] = mapped_column(Boolean, default=False)
    current_sim_day: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class TokenUsage(Base):
    __tablename__ = "token_usage"
    __table_args__ = (UniqueConstraint("sim_day", name="uq_token_usage_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sim_day: Mapped[int] = mapped_column(Integer)
    calls: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0)


class Newspaper(Base):
    __tablename__ = "newspapers"

    id: Mapped[int] = mapped_column(primary_key=True)
    sim_day: Mapped[int] = mapped_column(Integer, unique=True)
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
