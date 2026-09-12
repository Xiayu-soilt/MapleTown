import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# 必须在 huggingface_hub 首次导入前设置：国内网络走镜像 + 禁用 xet 传输（hf-mirror 下 xet 会 401）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    database_url: str = "sqlite:///./mapletown.db"

    jwt_secret: str = "change-me"
    access_token_expire_minutes: int = 1440

    tick_seconds: float = 3.0
    sim_minutes_per_tick: int = 10

    llm_concurrency: int = 5
    llm_timeout: float = 90.0
    daily_token_budget: int = 3_000_000

    # 记忆三因子检索：score = α·recency + β·importance + γ·relevance
    embedding_provider: str = "auto"  # auto | fastembed | hashing
    chroma_dir: str = "./chroma_data"
    retrieval_alpha: float = 1.0
    retrieval_beta: float = 1.0
    retrieval_gamma: float = 1.0
    retrieval_candidates: int = 32
    recency_decay_per_hour: float = 0.995

    # M3 日程规划
    plan_per_tick: int = 3

    # M3 对话引擎
    dialogue_max_turns: int = 8
    dialogue_per_tick: int = 2

    # M3 反思引擎
    reflection_threshold: float = 120.0
    reflection_min_memories: int = 20
    reflection_per_tick: int = 2

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
