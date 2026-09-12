import datetime as dt

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (Index("ix_memories_resident_sim", "resident_id", "sim_time"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"), index=True)
    type: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    sim_time: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    importance: Mapped[float | None] = mapped_column(Float, nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_access_sim_time: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class Reflection(Base):
    __tablename__ = "reflections"

    id: Mapped[int] = mapped_column(primary_key=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    source_memory_ids: Mapped[list] = mapped_column(JSON, default=list)
    sim_time: Mapped[dt.datetime] = mapped_column(DateTime)
    memory_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"), index=True)
    sim_day: Mapped[int] = mapped_column(Integer, index=True)
    daily_goal: Mapped[str] = mapped_column(Text, default="")
    hourly: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    sim_time: Mapped[dt.datetime] = mapped_column(DateTime)
    location: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="ongoing")
    participants: Mapped[list] = mapped_column(JSON, default=list)
    a_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    b_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    turn_no: Mapped[int] = mapped_column(Integer)
    speaker_id: Mapped[int] = mapped_column(ForeignKey("residents.id"))
    content: Mapped[str] = mapped_column(Text)


class UserChat(Base):
    __tablename__ = "user_chats"

    id: Mapped[int] = mapped_column(primary_key=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(8))
    content: Mapped[str] = mapped_column(Text)
    sim_time: Mapped[dt.datetime] = mapped_column(DateTime)
