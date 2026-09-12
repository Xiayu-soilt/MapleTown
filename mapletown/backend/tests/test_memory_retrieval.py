"""M2 记忆流三因子检索单元测试（hashing 嵌入 + Ephemeral Chroma，零网络依赖）。"""
import datetime as dt

import pytest

from app.cognition.memory_stream import memory_stream
from app.cognition.vector_store import vector_store
from tests.conftest import T0


def _add(db, rid, content, sim_time, importance=None):
    m = memory_stream.add(db, rid, content, "action", sim_time)
    if importance is not None:
        m.importance = importance
    return m


async def _vectorize(db, memories):
    await vector_store.upsert(
        [{"id": m.id, "resident_id": m.resident_id, "content": m.content} for m in memories]
    )


async def test_recency_favors_recent(db, resident):
    old = _add(db, resident.id, "整理了厨房储物柜", T0 - dt.timedelta(hours=48), importance=5)
    new = _add(db, resident.id, "清点完今日的面粉库存", T0, importance=5)
    await _vectorize(db, [old, new])

    rows = await memory_stream.retrieve(db, resident.id, "今天的例行事务", k=5, now_sim=T0)

    assert [m.id for m, _ in rows][:2] == [new.id, old.id]


async def test_importance_weighting(db, resident):
    trivial = _add(db, resident.id, "walked past the square fountain", T0, importance=1)
    major = _add(db, resident.id, "walked past the square statue", T0, importance=10)
    await _vectorize(db, [trivial, major])

    rows = await memory_stream.retrieve(db, resident.id, "town square walk", k=5, now_sim=T0)

    assert rows[0][0].id == major.id


async def test_relevance_ranking(db, resident):
    cake = _add(db, resident.id, "学会了做草莓奶油蛋糕", T0, importance=5)
    tax = _add(db, resident.id, "整理完一摞报税的旧文件", T0, importance=5)
    await _vectorize(db, [cake, tax])

    rows = await memory_stream.retrieve(db, resident.id, "草莓蛋糕怎么做的", k=5, now_sim=T0)

    assert rows[0][0].id == cake.id
    assert rows[0][1]["relevance"] > rows[-1][1]["relevance"]


async def test_factor_breakdown_shape(db, resident):
    m = _add(db, resident.id, "在公园喂了鸽子", T0, importance=7)
    await _vectorize(db, [m])

    rows = await memory_stream.retrieve(db, resident.id, "公园里的事", k=5, now_sim=T0)

    factors = rows[0][1]
    assert set(factors) == {"recency", "importance", "relevance", "score"}
    assert 0 <= factors["recency"] <= 1
    assert factors["importance"] == pytest.approx(0.7)
    assert factors["recency"] == pytest.approx(1.0)  # 刚写入，衰减为 0 小时


async def test_last_access_refreshed_on_retrieval(db, resident):
    m = _add(db, resident.id, "买了一张公园年票", T0, importance=5)
    await _vectorize(db, [m])

    later = T0 + dt.timedelta(hours=10)
    await memory_stream.retrieve(db, resident.id, "公园年票", k=5, now_sim=later)

    assert m.last_access_sim_time == later


async def test_retrieval_on_empty_stream(db, resident):
    rows = await memory_stream.retrieve(db, resident.id, "随便什么", k=5, now_sim=T0)
    assert rows == []


async def test_fallback_when_vector_store_empty(db, resident):
    """向量库为空时，检索退化为最近记忆（保证主流程不中断）。"""
    m1 = _add(db, resident.id, "最早的一条记忆", T0 - dt.timedelta(hours=2), importance=5)
    m2 = _add(db, resident.id, "最新的一条记忆", T0, importance=5)

    rows = await memory_stream.retrieve(db, resident.id, "任何查询", k=5, now_sim=T0)

    ids = [m.id for m, _ in rows]
    assert m1.id in ids and m2.id in ids


async def test_score_pending_vectorizes(db, resident, monkeypatch):
    m = _add(db, resident.id, "和棋友老周下了一盘围棋", T0)

    async def fake_chat_json(messages, **kwargs):
        return {"scores": [{"id": m.id, "score": 8}]}

    monkeypatch.setattr("app.cognition.memory_stream.llm.chat_json", fake_chat_json)

    count = await memory_stream.score_pending(db)

    assert count == 1
    assert m.importance == 8.0
    assert m.embedding_id == f"chroma:{m.id}"
    hits = await vector_store.query(resident.id, "围棋对局", top_k=5)
    assert any(h["memory_id"] == m.id for h in hits)
    assert all(0 <= h["relevance"] <= 1 for h in hits)


async def test_recency_decay_value(db, resident):
    m = _add(db, resident.id, "一次久远的旅行", T0 - dt.timedelta(hours=10), importance=5)
    await _vectorize(db, [m])

    rows = await memory_stream.retrieve(db, resident.id, "旅行的回忆", k=5, now_sim=T0)

    assert rows[0][1]["recency"] == pytest.approx(0.995**10, rel=1e-6)
