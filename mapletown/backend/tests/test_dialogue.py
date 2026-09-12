"""S2 对话引擎单元测试（mock LLM，零网络依赖）。"""
import datetime as dt
from types import SimpleNamespace

import pytest

from app.engine.dialogue import CLOSENESS_DELTA_LIMIT, DialogueEngine
from app.models.cognition import Conversation, ConversationTurn, Memory
from app.models.world import Relationship, SimState, WorldEvent
from tests.conftest import T0


def _state(sim_time: dt.datetime = T0) -> SimState:
    return SimState(id=1, sim_time=sim_time, tick=1, speed=1, running=True, current_sim_day=1)


@pytest.fixture
def pair(db):
    from app.models.world import Resident

    a = Resident(
        name="陈满堂",
        age=45,
        persona={"identity": "面包房老板", "goal": "做好面包"},
        workplace="满堂香面包房",
        current_location="满堂香面包房",
        current_activity="招呼客人",
    )
    b = Resident(
        name="白鸽",
        age=32,
        persona={"identity": "活动策划", "goal": "策划小镇活动"},
        workplace="白日梦想工作室",
        current_location="满堂香面包房",
        current_activity="买面包",
    )
    db.add_all([a, b])
    db.flush()
    return a, b


def _script(speak_payloads: list[dict | Exception], finalize_payload: dict | Exception):
    """构造按次序消费的 fake chat_json：先消费发言轮，最后一次是收尾调用。"""
    calls = {"n": 0}
    queue = list(speak_payloads) + [finalize_payload]

    async def fake_chat_json(messages, **kwargs):
        item = queue[calls["n"]]
        calls["n"] += 1
        if isinstance(item, Exception):
            raise item
        return item

    return fake_chat_json, calls


# ---------- 完整生命周期：持久化 + 三产物 ----------


async def test_run_persists_and_finalizes(db, pair, monkeypatch):
    a, b = pair
    speak = [
        {"line": "白鸽来啦，尝尝新出炉的草莓酥？", "still_interested": True},
        {"line": "哇正合我意！周末活动能不能搭个试吃位？", "still_interested": True},
        {"line": "没问题，再聊聊细节。", "still_interested": False},
        {"line": "好呀，我下午过去找你。", "still_interested": False},
    ]
    finalize = {
        "a_summary": "你和白鸽在面包房聊了新品试吃，她答应周末活动帮你搭宣传位",
        "b_summary": "你和陈满堂聊了草莓酥，约好下午去面包房敲活动细节",
        "closeness_delta": 0.06,
        "sentiment": "positive",
    }
    fake, _ = _script(speak, finalize)
    monkeypatch.setattr("app.engine.dialogue.llm.chat_json", fake)

    conv = await DialogueEngine().run(db, _state(), a, b)

    # 持久化：会话行 + 轮次行
    assert conv.status == "ended"
    assert conv.participants == [a.id, b.id]
    turns = db.query(ConversationTurn).filter_by(conversation_id=conv.id).order_by(ConversationTurn.turn_no).all()
    assert len(turns) == 4
    assert [t.speaker_id for t in turns] == [a.id, b.id, a.id, b.id]
    assert turns[0].content == speak[0]["line"]

    # 双视角总结写入双方记忆流
    mem_a = db.query(Memory).filter(Memory.resident_id == a.id, Memory.type == "conversation").all()
    mem_b = db.query(Memory).filter(Memory.resident_id == b.id, Memory.type == "conversation").all()
    assert len(mem_a) == 1 and finalize["a_summary"] in mem_a[0].content
    assert len(mem_b) == 1 and finalize["b_summary"] in mem_b[0].content
    assert conv.a_summary == finalize["a_summary"]
    assert conv.b_summary == finalize["b_summary"]

    # LLM 驱动的关系更新（非固定值）
    rel = db.query(Relationship).filter(Relationship.a_id == a.id, Relationship.b_id == b.id).one()
    assert rel.closeness == pytest.approx(0.3 + 0.06)
    assert rel.sentiment == "positive"

    # 事件流：逐轮 chat + 收尾 conversation_end
    events = db.query(WorldEvent).filter(WorldEvent.type == "conversation_end").all()
    assert len(events) == 1
    assert a.name in events[0].content and b.name in events[0].content
    assert db.query(WorldEvent).filter(WorldEvent.type == "chat").count() == 4


# ---------- 结束条件矩阵 ----------


async def test_exhaustion_ends_after_two_consecutive_disinterest(db, pair, monkeypatch):
    a, b = pair
    speak = [
        {"line": "今天天气不错。", "still_interested": False},
        {"line": "是啊，还行。", "still_interested": False},
        {"line": "不该出现的第三句", "still_interested": True},
    ]
    fake, _ = _script(speak, {})
    monkeypatch.setattr("app.engine.dialogue.llm.chat_json", fake)

    await DialogueEngine().run(db, _state(), a, b)

    assert db.query(ConversationTurn).count() == 2  # 第三轮不再生成


async def test_max_turns_cap(db, pair, monkeypatch):
    a, b = pair
    monkeypatch.setattr(
        "app.engine.dialogue.get_settings",
        lambda: SimpleNamespace(dialogue_max_turns=3),
    )
    speak = [{"line": f"第{i}句", "still_interested": True} for i in range(10)]
    fake, _ = _script(speak, {"a_summary": "s", "b_summary": "s", "closeness_delta": 0.01, "sentiment": "neutral"})
    monkeypatch.setattr("app.engine.dialogue.llm.chat_json", fake)

    await DialogueEngine().run(db, _state(), a, b)

    assert db.query(ConversationTurn).count() == 3


async def test_empty_line_ends_without_finalize(db, pair, monkeypatch):
    a, b = pair
    speak = [{"line": "", "still_interested": True}]
    fake, calls = _script(speak, {})
    monkeypatch.setattr("app.engine.dialogue.llm.chat_json", fake)

    await DialogueEngine().run(db, _state(), a, b)

    assert db.query(ConversationTurn).count() == 0
    assert calls["n"] == 1  # 台词为空 → 不再调用收尾
    assert db.query(Memory).filter(Memory.type == "conversation").count() == 0


async def test_speak_failure_keeps_generated_turns(db, pair, monkeypatch):
    """发言中途 LLM 失败：保留已生成轮次，直接 ended。"""
    a, b = pair
    speak = [
        {"line": "第一句", "still_interested": True},
        RuntimeError("llm down"),
    ]
    finalize = {
        "a_summary": "你和白鸽简短聊了两句",
        "b_summary": "你和陈满堂简短聊了两句",
        "closeness_delta": 0.02,
        "sentiment": "neutral",
    }
    fake, _ = _script(speak, finalize)
    monkeypatch.setattr("app.engine.dialogue.llm.chat_json", fake)

    conv = await DialogueEngine().run(db, _state(), a, b)

    assert conv.status == "ended"
    assert db.query(ConversationTurn).count() == 1


# ---------- 收尾容错：clamp / 降级 ----------


async def test_closeness_delta_clamped_both_sides(db, pair, monkeypatch):
    a, b = pair
    for raw, expected in ((0.9, CLOSENESS_DELTA_LIMIT), (-0.9, -CLOSENESS_DELTA_LIMIT)):
        db.query(Relationship).delete()
        db.query(Conversation).delete()
        db.query(ConversationTurn).delete()
        fake, _ = _script(
            [{"line": "聊聊", "still_interested": False}, {"line": "嗯。", "still_interested": False}],
            {"a_summary": "s1", "b_summary": "s2", "closeness_delta": raw, "sentiment": "weird"},
        )
        monkeypatch.setattr("app.engine.dialogue.llm.chat_json", fake)
        await DialogueEngine().run(db, _state(), a, b)
        rel = db.query(Relationship).one()
        assert rel.closeness == pytest.approx(0.3 + expected)
        assert rel.sentiment == "neutral"  # 非法 sentiment 回退 neutral


async def test_finalize_failure_degrades_gracefully(db, pair, monkeypatch):
    a, b = pair
    fake, _ = _script(
        [{"line": "今天生意如何？", "still_interested": False}, {"line": "还不错。", "still_interested": False}],
        RuntimeError("finalize failed"),
    )
    monkeypatch.setattr("app.engine.dialogue.llm.chat_json", fake)

    conv = await DialogueEngine().run(db, _state(), a, b)

    # 降级总结来自对话原文，关系小幅拉近
    assert conv.a_summary and "白鸽" in conv.a_summary and "聊了天" in conv.a_summary
    assert conv.b_summary and "陈满堂" in conv.b_summary
    mem_a = db.query(Memory).filter(Memory.resident_id == a.id, Memory.type == "conversation").all()
    assert len(mem_a) == 1
    rel = db.query(Relationship).one()
    assert rel.closeness == pytest.approx(0.32)
    assert db.query(WorldEvent).filter(WorldEvent.type == "conversation_end").count() == 1


async def test_finalize_garbage_summary_falls_back(db, pair, monkeypatch):
    a, b = pair
    fake, _ = _script(
        [{"line": "去公园走走？", "still_interested": True}, {"line": "好，一起。", "still_interested": False}],
        {"unexpected": "格式跑偏"},
    )
    monkeypatch.setattr("app.engine.dialogue.llm.chat_json", fake)

    conv = await DialogueEngine().run(db, _state(), a, b)

    assert "聊了天" in conv.a_summary and "聊了天" in conv.b_summary
    rel = db.query(Relationship).one()
    assert rel.closeness == pytest.approx(0.32)
