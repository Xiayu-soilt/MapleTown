import time

from fastapi import APIRouter

from app.core.config import get_settings
from app.llm.client import llm

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/health")
async def llm_health():
    settings = get_settings()
    key = settings.deepseek_api_key
    masked = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "not-set"
    start = time.time()
    try:
        reply = await llm.chat(
            [{"role": "user", "content": "请只回复四个字：枫叶镇在线"}],
            temperature=0.1,
            max_tokens=16,
        )
        return {
            "ok": True,
            "latency_ms": int((time.time() - start) * 1000),
            "model": settings.deepseek_model,
            "key": masked,
            "reply": reply.strip()[:30],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "latency_ms": int((time.time() - start) * 1000),
            "model": settings.deepseek_model,
            "key": masked,
            "error": str(exc)[:300],
        }
