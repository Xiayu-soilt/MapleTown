"""S4 API 路由测试：conversations / reflections（零网络依赖，get_db 注入测试库）。"""
import datetime as dt

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import conversations, residents
from app.db.session import get_db
from app.models.cognition import Conversation, ConversationTurn, Memory, Reflection
from app.models.world import Resident
from tests.conftest import T0


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(conversations.router, prefix="/api/v1")
    app.include_router(residents.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def pair(db):
    a = Resident(name="陈满堂", age=52, persona={"identity": "面包房老板"}, workplace="满堂香面包房")
    b = Resident(name="白鸽", age=32, persona={"identity": "活动策划"}, workplace="白日梦想工作室")
    db.add_all([a, b])
    db.flush()
    return a, b


def _make_conversation(db, participants, sim_time, location="镇广场", turns=0, a_summary=None, b_summary=None):
    conv = Conversation(
        sim_time=sim_time,
        location=location,
        status="ended",
        participants=[p.id for p in participants],
        a_summary=a_summary,
        b_summary=b_summary,
    )
    db.add(conv)
    db.flush()
    for i in range(turns):
        speaker = participants[i % len(participants)]
        db.add(
            ConversationTurn(
                conversation_id=conv.id,
                turn_no=i + 1,
                speaker_id=speaker.id,
                content=f"第{i + 1}句",
            )
        )
    db.flush()
    return conv


# ---------- /conversations ----------


def test_conversations_list_and_detail(db, client, pair):
    a, b = pair
    conv = _make_conversation(
        db,
        [a, b],
        T0,
        turns=4,
        a_summary="你和白鸽聊了镇庆策划",
        b_summary="你和陈满堂聊了面包供应",
    )

    resp = client.get("/api/v1/conversations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["id"] == conv.id
    assert item["status"] == "ended"
    assert item["sim_day"] == 1  # T0 == SIM_START
    assert item["turn_count"] == 4
    assert {p["name"] for p in item["participants"]} == {"陈满堂", "白鸽"}
    assert item["a_summary"] == "你和白鸽聊了镇庆策划"

    detail = client.get(f"/api/v1/conversations/{conv.id}").json()
    assert [t["turn_no"] for t in detail["turns"]] == [1, 2, 3, 4]
    assert [t["speaker_name"] for t in detail["turns"]] == ["陈满堂", "白鸽", "陈满堂", "白鸽"]
    assert detail["turns"][0]["content"] == "第1句"

    assert client.get("/api/v1/conversations/9999").status_code == 404


def test_conversations_day_and_resident_filters(db, client, pair):
    a, b = pair
    c = Resident(name="顾寒山", age=62, persona={"identity": "退休刑警"}, workplace="枫叶公寓")
    db.add(c)
    db.flush()
    day1 = _make_conversation(db, [a, b], T0, turns=2)
    day2 = _make_conversation(db, [a, c], T0 + dt.timedelta(days=1), turns=2)

    assert [x["id"] for x in client.get("/api/v1/conversations").json()] == [day2.id, day1.id]  # 新→旧

    only_day1 = client.get("/api/v1/conversations", params={"day": 1}).json()
    assert [x["id"] for x in only_day1] == [day1.id]

    only_b = client.get("/api/v1/conversations", params={"resident_id": b.id}).json()
    assert [x["id"] for x in only_b] == [day1.id]

    both_a = client.get("/api/v1/conversations", params={"resident_id": a.id}).json()
    assert {x["id"] for x in both_a} == {day1.id, day2.id}


# ---------- /residents/{id}/reflections ----------


def test_reflections_with_source_tree_link(db, client, resident):
    m1 = Memory(resident_id=resident.id, type="observation", content="在广场看到白鸽发传单", sim_time=T0, last_access_sim_time=T0, importance=4.0)
    m2 = Memory(resident_id=resident.id, type="action", content="开始整理配送清单", sim_time=T0, last_access_sim_time=T0, importance=5.0)
    db.add_all([m1, m2])
    db.flush()

    # 第一次反思：源自 m1，洞察写入记忆流为 memR1
    mem_r1 = Memory(resident_id=resident.id, type="reflection", content="白鸽的镇庆宣传在加速", sim_time=T0 + dt.timedelta(hours=1), last_access_sim_time=T0, importance=8.0)
    db.add(mem_r1)
    db.flush()
    r1 = Reflection(resident_id=resident.id, content="白鸽的镇庆宣传在加速", source_memory_ids=[m1.id], sim_time=T0 + dt.timedelta(hours=1), memory_id=mem_r1.id)
    db.add(r1)

    # 第二次反思：源自 m2 和第一次反思的记忆（反思的反思）→ 前端可递归
    mem_r2 = Memory(resident_id=resident.id, type="reflection", content="我在用清单工作掩盖对镇庆合作的犹豫", sim_time=T0 + dt.timedelta(hours=2), last_access_sim_time=T0, importance=9.0)
    db.add(mem_r2)
    db.flush()
    r2 = Reflection(resident_id=resident.id, content="我在用清单工作掩盖对镇庆合作的犹豫", source_memory_ids=[m2.id, mem_r1.id], sim_time=T0 + dt.timedelta(hours=2), memory_id=mem_r2.id)
    db.add(r2)
    db.flush()

    resp = client.get(f"/api/v1/residents/{resident.id}/reflections")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    top, bottom = data["items"]  # 新→旧

    assert top["id"] == r2.id
    assert top["importance"] == 9.0
    assert top["memory_id"] == mem_r2.id
    sources = {s["id"]: s for s in top["sources"]}
    assert sources[m2.id]["type"] == "action"
    assert sources[m2.id]["reflection_id"] is None
    assert sources[mem_r1.id]["type"] == "reflection"
    assert sources[mem_r1.id]["reflection_id"] == r1.id  # 反思树递归链路

    assert bottom["id"] == r1.id
    assert [s["id"] for s in bottom["sources"]] == [m1.id]

    assert client.get("/api/v1/residents/999/reflections").status_code == 404


def test_reflections_empty_for_fresh_resident(db, client, resident):
    resp = client.get(f"/api/v1/residents/{resident.id}/reflections")
    assert resp.status_code == 200
    assert resp.json() == {"total": 0, "items": []}
