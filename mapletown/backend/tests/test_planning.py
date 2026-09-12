"""S1 日程规划引擎单元测试（mock LLM，零网络依赖）。"""
import datetime as dt

import pytest

from app.engine.planning import PlanningEngine, clean_segments
from app.models.cognition import Plan
from app.models.world import SimState
from tests.conftest import T0


def _state(sim_time: dt.datetime) -> SimState:
    return SimState(id=1, sim_time=sim_time, tick=1, speed=1, running=True, current_sim_day=1)


def _make_plan(db, rid, segments, day=1, replanned=False, goal="老计划"):
    plan = Plan(
        resident_id=rid,
        sim_day=day,
        daily_goal=goal,
        hourly={"segments": segments, "replanned": replanned},
        updated_at=T0,
    )
    db.add(plan)
    db.flush()
    return plan


# ---------- clean_segments / current_segment ----------


def test_clean_segments_drops_invalid():
    raw = [
        {"start": "08:00", "end": "07:00", "activity": "时间倒挂"},  # end <= start
        {"start": "abc", "end": "10:00", "activity": "时间畸形"},
        {"start": "09:00", "end": "10:00", "activity": ""},  # 空活动
        {"start": "10:00", "end": "11:00", "activity": "正常段"},
        "not-a-dict",
    ]
    out = clean_segments(raw)
    assert len(out) == 1
    assert out[0]["activity"] == "正常段"


def test_current_segment_match_and_gap(db, resident):
    engine = PlanningEngine()
    plan = _make_plan(
        db,
        resident.id,
        [
            {"start": "08:00", "end": "10:00", "activity": "晨练"},
            {"start": "12:00", "end": "13:00", "activity": "午餐"},
        ],
    )
    assert engine.current_segment(plan, T0.replace(hour=9))["activity"] == "晨练"
    assert engine.current_segment(plan, T0.replace(hour=11)) is None  # 计划留白
    assert engine.current_segment(None, T0) is None


# ---------- generate ----------


async def test_generate_persists_plan(db, resident, monkeypatch):
    state = _state(T0)

    async def fake_chat_json(messages, **kwargs):
        return {
            "daily_goal": "推出草莓蛋糕新品",
            "segments": [
                {"start": "07:00", "end": "08:00", "activity": "晨练早餐"},
                {"start": "08:00", "end": "12:00", "activity": "面包房试做新品"},
                {"start": "13:00", "end": "17:00", "activity": "收集试吃反馈"},
            ],
        }

    monkeypatch.setattr("app.engine.planning.llm.chat_json", fake_chat_json)

    plan = await PlanningEngine().generate(db, state, resident)

    assert plan is not None
    assert plan.daily_goal == "推出草莓蛋糕新品"
    assert len(plan.hourly["segments"]) == 3
    assert plan.hourly["replanned"] is False
    # 事件已写入
    from app.models.world import WorldEvent

    events = db.query(WorldEvent).filter(WorldEvent.type == "plan").all()
    assert len(events) == 1
    assert resident.name in events[0].content


async def test_generate_all_bad_segments_returns_none(db, resident, monkeypatch):
    state = _state(T0)

    async def fake_chat_json(messages, **kwargs):
        return {"daily_goal": "x", "segments": [{"start": "bad", "end": "worse", "activity": "y"}]}

    monkeypatch.setattr("app.engine.planning.llm.chat_json", fake_chat_json)

    plan = await PlanningEngine().generate(db, state, resident)

    assert plan is None
    assert db.query(Plan).count() == 0


# ---------- replan ----------


async def test_replan_keeps_past_and_flags_once(db, resident, monkeypatch):
    engine = PlanningEngine()
    now = T0.replace(hour=14)  # 14:00
    state = _state(now)
    _make_plan(
        db,
        resident.id,
        [
            {"start": "08:00", "end": "12:00", "activity": "上午的原计划"},
            {"start": "14:00", "end": "18:00", "activity": "下午的原计划"},
        ],
    )

    async def fake_chat_json(messages, **kwargs):
        prompt = messages[1]["content"]
        assert "只重排当前之后" in prompt
        return {
            "daily_goal": "调整后的目标",
            "segments": [{"start": "14:30", "end": "18:00", "activity": "新的下午安排"}],
        }

    monkeypatch.setattr("app.engine.planning.llm.chat_json", fake_chat_json)

    plan = await engine.replan(db, state, resident, "面包房临时停电")

    segments = plan.hourly["segments"]
    assert plan.hourly["replanned"] is True
    assert {"start": "08:00", "end": "12:00", "activity": "上午的原计划"} in segments  # 过去保留
    assert {"start": "14:30", "end": "18:00", "activity": "新的下午安排"} in segments
    assert all(s["activity"] != "下午的原计划" for s in segments)

    # 第二次 replan 被拒绝（1 次/日）
    assert await engine.replan(db, state, resident, "再改一次") is None


async def test_replan_without_plan_returns_none(db, resident):
    assert await PlanningEngine().replan(db, _state(T0), resident, "没有计划") is None


# ---------- ensure_daily_plans 错峰与补规划 ----------


async def test_ensure_daily_plans_stagger_and_skip(db, resident, monkeypatch):
    engine = PlanningEngine()
    called: list[int] = []

    async def fake_chat_json(messages, **kwargs):
        called.append(1)
        return {
            "daily_goal": "g",
            "segments": [{"start": "07:00", "end": "23:00", "activity": "全天"}],
        }

    monkeypatch.setattr("app.engine.planning.llm.chat_json", fake_chat_json)

    await engine.ensure_daily_plans(db, _state(T0), [resident])  # 08:00，清醒时段
    assert len(called) == 1
    assert engine.get_plan(db, resident.id, 1) is not None

    # 已有计划不会重复生成
    await engine.ensure_daily_plans(db, _state(T0), [resident])
    assert len(called) == 1

    # 07:00 前不规划（睡觉时段）
    await engine.ensure_daily_plans(db, _state(T0.replace(hour=6)), [resident])
    assert len(called) == 1


async def test_late_start_plans_from_now(db, resident, monkeypatch):
    """模拟从午后恢复：补规划只覆盖当前之后的时段。"""
    spans: list[str | None] = []

    async def fake_chat_json(messages, **kwargs):
        content = messages[1]["content"]
        marker = "请规划你今天从 "
        start = content.find(marker)
        end = content.find(" 到 23:00", start)
        spans.append(content[start + len(marker) : end] if start != -1 else None)
        return {
            "daily_goal": "g",
            "segments": [{"start": "14:00", "end": "18:00", "activity": "下午安排"}],
        }

    monkeypatch.setattr("app.engine.planning.llm.chat_json", fake_chat_json)

    await PlanningEngine().ensure_daily_plans(db, _state(T0.replace(hour=14)), [resident])

    assert spans == ["14:00"]
    plan = PlanningEngine().get_plan(db, resident.id, 1)
    assert plan is not None
    assert plan.hourly["segments"][0]["start"] == "14:00"
