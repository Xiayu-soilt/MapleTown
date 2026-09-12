"""S3 反思引擎单元测试（mock LLM，零网络依赖）。"""
import datetime as dt
from types import SimpleNamespace

import pytest

from app.engine.reflection import REFLECTION_IMPORTANCE_CAP, ReflectionEngine
from app.models.cognition import Memory, Reflection
from app.models.world import Resident, SimState, WorldEvent
from tests.conftest import T0


def _state(sim_time: dt.datetime = T0) -> SimState:
    return SimState(id=1, sim_time=sim_time, tick=1, speed=1, running=True, current_sim_day=1)


def _add_memory(db, rid, content, sim_time, importance=5.0, mtype="observation") -> Memory:
    m = Memory(
        resident_id=rid,
        type=mtype,
        content=content,
        sim_time=sim_time,
        last_access_sim_time=sim_time,
        importance=importance,
    )
    db.add(m)
    db.flush()
    return m


def _settings(threshold=100.0, min_memories=5, per_tick=2):
    return SimpleNamespace(
        reflection_threshold=threshold,
        reflection_min_memories=min_memories,
        reflection_per_tick=per_tick,
    )


def _script(payloads: list):
    """按次序消费的 fake chat_json，队列耗尽即抛错（暴露多余调用）。"""
    calls = {"n": 0}

    async def fake(messages, **kwargs):
        if calls["n"] >= len(payloads):
            raise AssertionError(f"unexpected LLM call #{calls['n']}")
        item = payloads[calls["n"]]
        calls["n"] += 1
        return item

    return fake, calls


# ---------- 阈值计算 ----------


def test_pending_stats_since_last_reflection(db, resident):
    t1 = T0
    t2 = T0 + dt.timedelta(hours=1)
    t3 = T0 + dt.timedelta(hours=2)
    _add_memory(db, resident.id, "旧记忆1", t1, importance=5.0)
    _add_memory(db, resident.id, "旧记忆2", t1, importance=5.0)
    db.add(
        Reflection(
            resident_id=resident.id,
            content="旧反思",
            source_memory_ids=[],
            sim_time=t1 + dt.timedelta(minutes=30),
        )
    )
    db.flush()
    _add_memory(db, resident.id, "新记忆", t2, importance=4.0)
    # 反思产生的记忆同样计入累积（论文：洞察会级联出更深的洞察）
    _add_memory(db, resident.id, "反思洞察", t3, importance=8.0, mtype="reflection")

    value, count = ReflectionEngine().pending_stats(db, resident.id)

    assert value == pytest.approx(12.0)
    assert count == 2


def test_pending_stats_no_reflection_yet(db, resident):
    _add_memory(db, resident.id, "m1", T0, importance=6.0)
    _add_memory(db, resident.id, "m2", T0, importance=None)  # 未打分不计入
    value, count = ReflectionEngine().pending_stats(db, resident.id)
    assert value == pytest.approx(6.0)
    assert count == 1


# ---------- 反思管线 ----------


async def test_reflect_persists_insights_with_sources(db, resident, monkeypatch):
    for i in range(6):
        _add_memory(db, resident.id, f"面包房日常{i}", T0 - dt.timedelta(hours=6 - i), importance=5.0)
    latest = db.query(Memory).order_by(Memory.id.desc()).first()
    fake, _ = _script(
        [
            {"questions": ["我最近为什么总觉得忙不过来？"]},
            {
                "insights": [
                    {"content": "新品研发占满了我的时间，该留出休息和陪朋友的时间", "source_ids": [latest.id], "importance": 10},
                ]
            },
        ]
    )
    monkeypatch.setattr("app.engine.reflection.llm.chat_json", fake)
    monkeypatch.setattr("app.engine.reflection.get_settings", lambda: _settings(min_memories=5))

    created = await ReflectionEngine().reflect(db, _state(), resident)

    assert len(created) == 1
    refl = created[0]
    assert refl.source_memory_ids == [latest.id]
    assert refl.memory_id is not None
    mem = db.get(Memory, refl.memory_id)
    assert mem.type == "reflection"
    assert mem.importance == REFLECTION_IMPORTANCE_CAP  # LLM 给 10，封顶 9
    assert mem.embedding_id == f"chroma:{mem.id}"  # 立即向量化，参与相关性检索
    events = db.query(WorldEvent).filter(WorldEvent.type == "reflect").all()
    assert len(events) == 1
    assert resident.name in events[0].content and "陷入了沉思" in events[0].content
    # 反思记忆计入下一轮累积（级联）
    value, count = ReflectionEngine().pending_stats(db, resident.id)
    assert count == 1 and value == pytest.approx(REFLECTION_IMPORTANCE_CAP)


async def test_reflect_filters_hallucinated_sources(db, resident, monkeypatch):
    for i in range(5):
        _add_memory(db, resident.id, f"日常{i}", T0 - dt.timedelta(hours=5 - i), importance=5.0)
    valid = db.query(Memory).order_by(Memory.id.desc()).first().id
    fake, _ = _script(
        [
            {"questions": ["q1", "q2"]},
            {
                "insights": [
                    {"content": "无据洞察应被丢弃", "source_ids": [99999]},
                    {"content": "有据洞察保留并剔除幻觉id", "source_ids": [99999, valid]},
                ]
            },
            {"insights": [{"content": "缺importance默认8", "source_ids": [valid]}]},
        ]
    )
    monkeypatch.setattr("app.engine.reflection.llm.chat_json", fake)
    monkeypatch.setattr("app.engine.reflection.get_settings", lambda: _settings(min_memories=5))

    created = await ReflectionEngine().reflect(db, _state(), resident)

    assert len(created) == 2
    assert created[0].source_memory_ids == [valid]
    assert created[0].content == "有据洞察保留并剔除幻觉id"
    assert created[1].source_memory_ids == [valid]
    assert db.get(Memory, created[1].memory_id).importance == 8.0


async def test_reflect_below_min_memories(db, resident, monkeypatch):
    for i in range(3):
        _add_memory(db, resident.id, f"m{i}", T0 - dt.timedelta(hours=i), importance=50.0)
    fake, calls = _script([])
    monkeypatch.setattr("app.engine.reflection.llm.chat_json", fake)
    monkeypatch.setattr("app.engine.reflection.get_settings", lambda: _settings(min_memories=5))

    assert await ReflectionEngine().reflect(db, _state(), resident) == []
    assert calls["n"] == 0
    assert db.query(Reflection).count() == 0


async def test_reflect_empty_questions_persists_nothing(db, resident, monkeypatch):
    for i in range(5):
        _add_memory(db, resident.id, f"m{i}", T0 - dt.timedelta(hours=i), importance=5.0)
    fake, _ = _script([{"questions": []}])
    monkeypatch.setattr("app.engine.reflection.llm.chat_json", fake)
    monkeypatch.setattr("app.engine.reflection.get_settings", lambda: _settings(min_memories=5))

    assert await ReflectionEngine().reflect(db, _state(), resident) == []
    assert db.query(Reflection).count() == 0


# ---------- tick 调度 ----------


async def test_check_and_run_respects_threshold(db, resident, monkeypatch):
    for i in range(4):
        _add_memory(db, resident.id, f"m{i}", T0 - dt.timedelta(hours=i), importance=5.0)  # 20 < 100
    async def fail_json(messages, **kwargs):
        raise AssertionError("LLM should not be called")

    monkeypatch.setattr("app.engine.reflection.llm.chat_json", fail_json)
    monkeypatch.setattr("app.engine.reflection.get_settings", lambda: _settings(threshold=100, min_memories=2))

    assert await ReflectionEngine().check_and_run(db, _state(), [resident]) == 0
    assert db.query(Reflection).count() == 0


async def test_check_and_run_skips_busy(db, resident, monkeypatch):
    for i in range(6):
        _add_memory(db, resident.id, f"m{i}", T0 - dt.timedelta(hours=i), importance=20.0)
    async def fail_json(messages, **kwargs):
        raise AssertionError("busy resident should be skipped")

    monkeypatch.setattr("app.engine.reflection.llm.chat_json", fail_json)
    monkeypatch.setattr("app.engine.reflection.get_settings", lambda: _settings(threshold=100, min_memories=5))

    assert await ReflectionEngine().check_and_run(db, _state(), [resident], busy_ids={resident.id}) == 0


async def test_check_and_run_per_tick_cap(db, resident, monkeypatch):
    b = Resident(
        name="顾寒山",
        age=55,
        persona={"identity": "刑警", "goal": "查明河堤的事"},
        workplace="律师事务所",
        current_activity="查案",
    )
    db.add(b)
    db.flush()
    for i in range(6):
        _add_memory(db, resident.id, f"m{i}", T0 - dt.timedelta(hours=i), importance=20.0)
        _add_memory(db, b.id, f"m{i}", T0 - dt.timedelta(hours=i), importance=20.0)
    # 空问题 → 每人只消耗 1 次提问调用
    fake, calls = _script([{"questions": []}, {"questions": []}])
    monkeypatch.setattr("app.engine.reflection.llm.chat_json", fake)
    monkeypatch.setattr(
        "app.engine.reflection.get_settings",
        lambda: _settings(threshold=100, min_memories=5, per_tick=1),
    )

    done = await ReflectionEngine().check_and_run(db, _state(), [resident, b])

    assert done == 1  # per_tick=1：只处理第一个居民
    assert calls["n"] == 1
