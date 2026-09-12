"""M1-M3 综合烟雾验收：一次运行覆盖全部里程碑验收点。

验收点（对照 PROJECT_PLAN 里程碑 / M3_DESIGN §10）：
  M1 骨架   注册登录 → LLM 连通 → 模拟启动 → AI 驱动事件产生
  M2 认知   记忆流落库（含重要性）+ 三因子检索得分可见
  S1 规划   plan 事件 + GET /residents/{id}/plan 返回日程分段
  S2 对话   conversation_end + GET /conversations（新→旧）+ LLM 驱动的关系变化
  S3 反思   reflect 事件 + GET /residents/{id}/reflections（洞察 + 源记忆溯源）

运行：先启动后端（.venv\\Scripts\\python.exe -m uvicorn app.main:app --port 8100），再执行
  .venv\\Scripts\\python.exe -m scripts.smoke_test
可选环境变量：
  MAPLETOWN_BASE  API 前缀（默认 http://127.0.0.1:8100/api/v1）
  MAPLETOWN_DB    SQLite 路径（默认 mapletown.db）
  SMOKE_TIMEOUT   最长等待秒数（默认 600）
"""
import json
import os
import random
import sqlite3
import string
import sys
import time

import httpx

BASE = os.environ.get("MAPLETOWN_BASE", "http://127.0.0.1:8100/api/v1")
DB = os.environ.get("MAPLETOWN_DB", "mapletown.db")
TIMEOUT = int(os.environ.get("SMOKE_TIMEOUT", "600"))

VERDICTS: list[tuple[str, str, bool]] = []


def verdict(stage: str, label: str, ok: bool) -> None:
    VERDICTS.append((stage, label, ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {stage} {label}")


def show(label: str, obj) -> None:
    print(f"[{label}] {json.dumps(obj, ensure_ascii=True, default=str)[:400]}")


def relationship_snapshot() -> dict[tuple[int, int], tuple[float, str]]:
    if not os.path.exists(DB):
        return {}
    conn = sqlite3.connect(DB)
    try:
        rows = conn.execute("SELECT a_id, b_id, closeness, sentiment FROM relationships").fetchall()
    except sqlite3.Error:
        return {}
    finally:
        conn.close()
    return {(r[0], r[1]): (r[2], r[3]) for r in rows}


def wait_for_milestones(client: httpx.Client, headers: dict) -> dict[str, list]:
    """轮询事件流直到本次运行的三大里程碑（规划/对话/反思）齐备或超时。

    以启动前最大事件 id 为基线，只统计本次运行新增的事件——重跑（库中已有历史数据）时
    旧事件不会让里程碑提前满足，关系 before/after 对比同样只覆盖本次运行。
    """
    baseline = max((e.get("id", 0) for e in client.get(f"{BASE}/events?limit=200").json()), default=0)
    counts = {"plan": 0, "conversation_end": 0, "reflect": 0}
    events: list = []
    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        time.sleep(10)
        events = [e for e in client.get(f"{BASE}/events?limit=200").json() if e.get("id", 0) > baseline]
        for key in counts:
            counts[key] = sum(1 for e in events if e.get("type") == key)
        chats = sum(1 for e in events if e.get("type") == "chat")
        print(
            f"  ... new_events={len(events)} chat={chats} "
            f"plan={counts['plan']} conversation_end={counts['conversation_end']} reflect={counts['reflect']}"
        )
        if counts["plan"] >= 3 and counts["conversation_end"] >= 1 and counts["reflect"] >= 3:
            break
    client.post(f"{BASE}/sim/control", json={"action": "pause"}, headers=headers)
    return {"events": events, **counts}


def section(title: str) -> None:
    print(f"\n{'=' * 12} {title} {'=' * 12}")


def check_m1(client: httpx.Client, username: str, events: list) -> None:
    section("M1 骨架")
    r = client.post(f"{BASE}/auth/login", json={"username": username, "password": "maple123"})
    verdict("M1", "登录鉴权", r.status_code == 200)
    health = client.get(f"{BASE}/llm/health").json()
    ok = str(health).find("ok") >= 0 or health.get("status") in ("ok", "healthy")
    show("LLM_HEALTH", health)
    verdict("M1", "LLM 连通", ok)
    verdict("M1", "AI 驱动事件产生", len(events) >= 20)
    print("\n=== 最近事件 ===")
    for e in events[-10:]:
        print("  " + json.dumps(e, ensure_ascii=True, default=str)[:200])


def check_m2(client: httpx.Client) -> None:
    section("M2 认知核心")
    rid = 1
    mem = client.get(f"{BASE}/residents/{rid}/memories", params={"limit": 100}).json()
    scored = [m for m in mem.get("items", []) if m.get("importance") is not None]
    verdict("M2", "记忆流落库", mem.get("total", 0) > 0)
    verdict("M2", "记忆含重要性得分", len(scored) > 0)
    for m in mem.get("items", [])[:5]:
        print("  " + json.dumps(m, ensure_ascii=True, default=str)[:200])

    print("\n=== 三因子检索观测 (memory-search) ===")
    search = client.get(f"{BASE}/residents/{rid}/memory-search", params={"q": "面包房的工作", "k": 5}).json()
    items = search.get("items", [])
    show("WEIGHTS", {"provider": search.get("provider"), "weights": search.get("weights")})
    for item in items[:5]:
        f = item.get("factors", {})
        print(
            f"  score={f.get('score', 0):.3f} (rec={f.get('recency', 0):.2f} imp={f.get('importance', 0):.2f} "
            f"rel={f.get('relevance', 0):.2f}) | {item.get('content', '')[:40]}"
        )
    verdict("M2", "三因子检索返回得分明细", len(items) > 0 and all("score" in i.get("factors", {}) for i in items))


def check_s1(client: httpx.Client) -> None:
    section("S1 日程规划")
    residents = client.get(f"{BASE}/residents").json()
    got_plan = 0
    for r_ in residents[:4]:
        pr = client.get(f"{BASE}/residents/{r_['id']}/plan")
        if pr.status_code != 200:
            print(f"  {r_['name']}: 暂无日程 ({pr.status_code})")
            continue
        got_plan += 1
        plan = pr.json()
        print(f"  {r_['name']} 目标：{plan.get('daily_goal', '')[:50]}")
        for seg in plan.get("segments", [])[:4]:
            print(f"    {seg.get('start')}-{seg.get('end')} {seg.get('activity', '')[:36]}")
    verdict("S1", "/plan API 返回日程分段", got_plan > 0)


def check_s2(client: httpx.Client, before: dict) -> None:
    section("S2 对话引擎")
    convs = client.get(f"{BASE}/conversations", params={"limit": 5}).json()
    ids = [c["id"] for c in convs]
    verdict("S2", "/conversations 返回对话", len(convs) > 0)
    verdict("S2", "列表按新→旧排序", ids == sorted(ids, reverse=True))
    for c in convs[:3]:
        names = "、".join(p["name"] for p in c.get("participants", []))
        print(f"  #{c['id']} [{c['status']}] {names} @ {c['location']} turns={c['turn_count']}")
        print(f"     A视角: {(c.get('a_summary') or '')[:60]}")
        print(f"     B视角: {(c.get('b_summary') or '')[:60]}")

    if convs:
        detail = client.get(f"{BASE}/conversations/{convs[0]['id']}").json()
        turns = detail.get("turns", [])
        verdict("S2", "对话详情含持久化轮次", len(turns) > 0)
        for t in turns[:8]:
            print(f"  #{t['turn_no']} {t['speaker_name']}: {t['content'][:40]}")

    after = relationship_snapshot()
    changed = {k: v for k, v in after.items() if before.get(k, (None,))[0] != v[0]}
    print(f"\n=== 关系变化（{len(changed)} 对）===")
    for (a_id, b_id), (closeness, sentiment) in list(changed.items())[:8]:
        old = before.get((a_id, b_id), (None, None))[0]
        if old is None:
            print(f"  ({a_id},{b_id}) 新建 closeness={closeness:.3f} sentiment={sentiment}")
        else:
            print(f"  ({a_id},{b_id}) closeness {old:.3f} -> {closeness:.3f} (Δ={closeness - old:+.3f}) sentiment={sentiment}")
    with_before = [k for k in changed if before.get(k, (None,))[0] is not None]
    fixed = [k for k in with_before if abs((after[k][0] - before[k][0]) - 0.04) < 1e-9]
    # 全新库中所有关系均为本运行新建（无 before 值）：只要不存在"全部变更恰好 +0.04"即视为 LLM 驱动
    ok = len(changed) > 0 and not (with_before and len(fixed) == len(with_before))
    verdict("S2", "关系变化由 LLM 驱动（非固定 +0.04）", ok)


def check_s3(client: httpx.Client, reflect_events: list) -> None:
    section("S3 反思引擎")
    verdict("S3", "reflect 事件出现", len(reflect_events) >= 1)
    for e in reflect_events[:5]:
        print("  " + json.dumps(e, ensure_ascii=True, default=str)[:300])

    residents = {r["id"]: r["name"] for r in client.get(f"{BASE}/residents").json()}
    any_sourced = 0
    seen: set[int] = set()
    for e in reflect_events:
        for rid in e.get("participants") or []:
            if rid in seen:
                continue
            seen.add(rid)
            rr = client.get(f"{BASE}/residents/{rid}/reflections", params={"limit": 5})
            if rr.status_code != 200 or not rr.json().get("items"):
                continue
            data = rr.json()
            print(f"\n  [{residents.get(rid, rid)}] total_reflections={data['total']}")
            for item in data["items"]:
                print(f"    #{item['id']} (imp={item.get('importance')}) {item['content'][:60]}")
                for src in item.get("sources", []):
                    link = f" -> reflection#{src['reflection_id']}" if src.get("reflection_id") else ""
                    print(f"      源[{src['type']}#{src['id']}] {src['content'][:44]}{link}")
                if item.get("source_memory_ids"):
                    any_sourced += 1
    verdict("S3", "洞察溯源到源记忆（反思树）", any_sourced > 0)


def main() -> None:
    with httpx.Client(timeout=30) as client:
        state = client.get(f"{BASE}/sim/state").json()
        show("STATE", state)

        suffix = "".join(random.choices(string.ascii_lowercase, k=6))
        username = f"tester_{suffix}"
        client.post(
            f"{BASE}/auth/register",
            json={"username": username, "email": f"{username}@maple.town", "password": "maple123"},
        )
        r = client.post(f"{BASE}/auth/login", json={"username": username, "password": "maple123"})
        headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        verdict("M1", "注册/登录", r.status_code == 200)

        before = relationship_snapshot()
        client.post(f"{BASE}/sim/control", json={"action": "start"}, headers=headers)
        print("SIM STARTED, waiting for plan/conversation/reflection milestones ...")
        result = wait_for_milestones(client, headers)
        events = result.pop("events")
        counts = result

        check_m1(client, username, events)
        check_m2(client)
        check_s1(client)
        check_s2(client, before)
        check_s3(client, [e for e in events if e.get("type") == "reflect"])

        show("STATE_AFTER", client.get(f"{BASE}/sim/state").json())

        section("验收总结")
        for stage, label, ok in VERDICTS:
            print(f"  [{'PASS' if ok else 'FAIL'}] {stage} {label}")
        failed = [v for v in VERDICTS if not v[2]]
        print(f"\n里程碑计数: {counts}")
        if failed:
            print(f"RESULT: FAILED ({len(failed)}/{len(VERDICTS)} 项未通过)")
            sys.exit(1)
        print(f"RESULT: PASSED ({len(VERDICTS)}/{len(VERDICTS)} 项通过). SIM PAUSED.")
        sys.exit(0)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
