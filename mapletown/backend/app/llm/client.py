import asyncio
import json
import logging
import re

from openai import AsyncOpenAI

from app.core.config import get_settings

logger = logging.getLogger("mapletown.llm")


def parse_json_loose(text: str | None) -> dict | list:
    """容错解析 LLM 返回的 JSON：处理代码块围栏、前后杂质。"""
    if not text:
        raise ValueError("empty llm response")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    for open_char, close_char in (("{", "}"), ("[", "]")):
        start = cleaned.find(open_char)
        end = cleaned.rfind(close_char)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"cannot parse json: {cleaned[:120]}")


class LLMClient:
    """DeepSeek 客户端封装：并发限流 + 用量统计 + JSON 容错解析。"""

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.deepseek_model
        self._client = AsyncOpenAI(
            api_key=settings.deepseek_api_key or "EMPTY",
            base_url=settings.deepseek_base_url,
            timeout=settings.llm_timeout,
            max_retries=2,
        )
        self._semaphore = asyncio.Semaphore(max(1, settings.llm_concurrency))
        self.usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
        self._flushed = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 800,
        json_mode: bool = False,
    ) -> str:
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        async with self._semaphore:
            response = await self._client.chat.completions.create(**kwargs)
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.usage["calls"] += 1
            self.usage["prompt_tokens"] += usage.prompt_tokens or 0
            self.usage["completion_tokens"] += usage.completion_tokens or 0
        return response.choices[0].message.content or ""

    async def chat_json(
        self,
        messages: list[dict],
        temperature: float = 0.4,
        max_tokens: int = 512,
    ) -> dict | list:
        content = await self.chat(messages, temperature=temperature, max_tokens=max_tokens, json_mode=True)
        return parse_json_loose(content)

    def take_usage_delta(self) -> dict[str, int]:
        delta = {key: self.usage[key] - self._flushed[key] for key in self.usage}
        self._flushed = dict(self.usage)
        return delta


llm = LLMClient()
