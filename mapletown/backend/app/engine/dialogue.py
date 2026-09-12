import logging

from sqlalchemy.orm import Session

from app.cognition import prompts
from app.cognition.memory_stream import memory_stream
from app.core.config import get_settings
from app.llm.client import llm
from app.models.cognition import Conversation, ConversationTurn
from app.models.world import Resident, SimState
from app.services.events import emit_event
from app.services.social import update_relationship

logger = logging.getLogger("mapletown.dialogue")

CLOSENESS_DELTA_LIMIT = 0.15
VALID_SENTIMENTS = {"positive", "neutral", "negative"}


class DialogueEngine:
    """完整对话管线（论文 Dialogue 机制的产品化）：

    生命周期：initiated → 逐轮发言（每次调用同时产出台词 + 继续意愿）
    → 话题枯竭 / 达上限 / 台词为空 → 收尾管线（1 次调用产出三产物）→ ended。

    - 持久化：conversations（ongoing → ended）+ conversation_turns（逐句落库）
    - 枯竭检测：双方连续 2 个 still_interested=false 即自然结束，避免硬切
    - 收尾三产物：双视角总结（写入双方记忆流）+ closeness_delta + sentiment
    """

    async def run(self, db: Session, state: SimState, a: Resident, b: Resident) -> Conversation:
        settings = get_settings()
        conv = Conversation(
            sim_time=state.sim_time,
            location=a.current_location,
            status="ongoing",
            participants=[a.id, b.id],
        )
        db.add(conv)
        db.flush()

        history: list[dict] = []
        disinterest_streak = 0
        for i in range(settings.dialogue_max_turns):
            speaker, listener = (a, b) if i % 2 == 0 else (b, a)
            result = await self._speak(db, state, speaker, listener, history)
            if result is None:
                break
            line, interested = result
            if not line:
                break
            db.add(
                ConversationTurn(
                    conversation_id=conv.id,
                    turn_no=i + 1,
                    speaker_id=speaker.id,
                    content=line,
                )
            )
            history.append({"speaker": speaker.name, "content": line})
            emit_event(
                db,
                state,
                "chat",
                f"{speaker.name} 对 {listener.name} 说：「{line}」",
                participants=[speaker.id, listener.id],
                location=conv.location,
            )
            disinterest_streak = disinterest_streak + 1 if not interested else 0
            if disinterest_streak >= 2:
                break

        conv.status = "ended"
        a.current_activity = f"刚和{b.name}聊完天"
        b.current_activity = f"刚和{a.name}聊完天"
        await self._finalize(db, state, conv, a, b, history)
        return conv

    async def _speak(
        self,
        db: Session,
        state: SimState,
        speaker: Resident,
        listener: Resident,
        history: list[dict],
    ) -> tuple[str, bool] | None:
        """生成一句台词与继续意愿。LLM 失败返回 None（保留已生成轮次，对话直接结束）。"""
        listener_identity = (listener.persona or {}).get("identity", "")
        try:
            memory_lines = await memory_stream.retrieve_contents(
                db,
                speaker.id,
                f"和{listener.name}（{listener_identity}）聊天",
                k=6,
                now_sim=state.sim_time,
            )
        except Exception:
            memory_lines = [m.content for m in memory_stream.recent(db, speaker.id, limit=6)]
        try:
            data = await llm.chat_json(
                [
                    {"role": "system", "content": prompts.DIALOGUE_SYSTEM},
                    {
                        "role": "user",
                        "content": prompts.build_dialogue_prompt(
                            speaker_name=speaker.name,
                            speaker_persona=speaker.persona or {},
                            listener_name=listener.name,
                            listener_identity=listener_identity,
                            location=speaker.current_location,
                            history=history,
                            memory_lines=memory_lines,
                            sim_time_str=state.sim_time.strftime("%m月%d日 %H:%M"),
                        ),
                    },
                ],
                temperature=0.9,
                max_tokens=200,
            )
        except Exception:
            logger.exception("dialogue line failed for %s", speaker.name)
            return None
        if not isinstance(data, dict):
            return None
        line = str(data.get("line") or "").strip().strip('"“”').split("\n")[0][:80]
        interested = str(data.get("still_interested", "true")).strip().lower() != "false"
        return line, interested

    async def _finalize(
        self,
        db: Session,
        state: SimState,
        conv: Conversation,
        a: Resident,
        b: Resident,
        history: list[dict],
    ) -> None:
        """收尾管线：一次 LLM 调用产出双视角总结 + 关系增量 + 情感极性。

        失败时降级：总结退化为对话摘要拼接，关系按日常寒暄小幅拉近，不阻塞主流程。
        """
        if not history:
            return

        a_summary = b_summary = ""
        delta = 0.02
        sentiment = "neutral"
        try:
            data = await llm.chat_json(
                [
                    {"role": "system", "content": prompts.CONVERSATION_SUMMARY_SYSTEM},
                    {
                        "role": "user",
                        "content": prompts.build_conversation_summary_prompt(
                            a_name=a.name,
                            a_identity=(a.persona or {}).get("identity", ""),
                            b_name=b.name,
                            b_identity=(b.persona or {}).get("identity", ""),
                            location=conv.location,
                            sim_time_str=conv.sim_time.strftime("%m月%d日 %H:%M"),
                            history=history,
                        ),
                    },
                ],
                temperature=0.3,
                max_tokens=400,
            )
            if isinstance(data, dict):
                a_summary = str(data.get("a_summary") or "").strip()[:120]
                b_summary = str(data.get("b_summary") or "").strip()[:120]
                try:
                    delta = max(
                        -CLOSENESS_DELTA_LIMIT,
                        min(CLOSENESS_DELTA_LIMIT, float(data.get("closeness_delta", delta))),
                    )
                except (TypeError, ValueError):
                    pass
                if str(data.get("sentiment") or "").lower() in VALID_SENTIMENTS:
                    sentiment = str(data["sentiment"]).lower()
        except Exception:
            logger.exception("conversation finalize failed, degrading gracefully")

        if not a_summary:
            brief = "；".join(f"{h['speaker']}说：{h['content']}" for h in history[:2])
            a_summary = f"你和{b.name}在{conv.location}聊了天：{brief}"[:120]
        if not b_summary:
            brief = "；".join(f"{h['speaker']}说：{h['content']}" for h in history[:2])
            b_summary = f"你和{a.name}在{conv.location}聊了天：{brief}"[:120]

        conv.a_summary = a_summary
        conv.b_summary = b_summary
        db.flush()
        memory_stream.add(db, a.id, a_summary, "conversation", state.sim_time)
        memory_stream.add(db, b.id, b_summary, "conversation", state.sim_time)
        update_relationship(db, a.id, b.id, delta=delta, sim_time=state.sim_time, sentiment=sentiment)
        emit_event(
            db,
            state,
            "conversation_end",
            f"{a.name} 和 {b.name} 聊完了。{a.name}的收获：{a_summary} {b.name}的收获：{b_summary}",
            participants=[a.id, b.id],
            location=conv.location,
        )


dialogue_engine = DialogueEngine()
