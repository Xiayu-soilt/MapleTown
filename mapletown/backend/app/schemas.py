from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_\u4e00-\u9fa5]+$")
    email: str = Field(min_length=5, max_length=128)
    password: str = Field(min_length=6, max_length=64)


class UserLogin(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    created_at: datetime


class SimStateOut(BaseModel):
    sim_time: datetime
    tick: int
    speed: int
    running: bool
    sim_day: int


class SimControlIn(BaseModel):
    action: Literal["start", "pause", "speed"]
    value: int | None = Field(default=None, ge=1, le=5)


class MemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    content: str
    sim_time: datetime
    importance: float | None = None
    last_access_sim_time: datetime | None = None
    vectorized: bool = False


class ResidentOut(BaseModel):
    id: int
    name: str
    age: int
    avatar_color: str
    identity: str
    workplace: str
    current_location: str
    current_activity: str


class ResidentDetail(ResidentOut):
    persona: dict[str, Any]
    memories: list[MemoryOut]


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tick: int
    sim_time: datetime
    type: str
    content: str
    location: str | None = None
    participants: list = []


class MemoryListOut(BaseModel):
    total: int
    items: list[MemoryOut]


class MemorySearchItem(MemoryOut):
    factors: dict[str, float]


class MemorySearchOut(BaseModel):
    query: str
    provider: str
    weights: dict[str, float]
    items: list[MemorySearchItem]


class PlanSegment(BaseModel):
    start: str
    end: str
    activity: str


class PlanOut(BaseModel):
    resident_id: int
    sim_day: int
    daily_goal: str
    segments: list[PlanSegment]
    replanned: bool = False


class ConversationParticipant(BaseModel):
    id: int
    name: str
    avatar_color: str


class ConversationTurnOut(BaseModel):
    turn_no: int
    speaker_id: int
    speaker_name: str
    content: str


class ConversationOut(BaseModel):
    id: int
    sim_time: datetime
    sim_day: int
    location: str
    status: str
    participants: list[ConversationParticipant] = []
    turn_count: int = 0
    a_summary: str | None = None
    b_summary: str | None = None


class ConversationDetail(ConversationOut):
    turns: list[ConversationTurnOut] = []


class ReflectionSourceOut(BaseModel):
    id: int
    type: str
    content: str
    sim_time: datetime
    importance: float | None = None
    reflection_id: int | None = None  # 源记忆本身是反思时指向对应 Reflection，供反思树递归


class ReflectionOut(BaseModel):
    id: int
    content: str
    sim_time: datetime
    importance: float | None = None
    source_memory_ids: list[int] = []
    sources: list[ReflectionSourceOut] = []
    memory_id: int | None = None


class ReflectionListOut(BaseModel):
    total: int
    items: list[ReflectionOut]
