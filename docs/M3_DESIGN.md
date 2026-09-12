# M3 架构设计：日程规划 + 反思引擎 + Agent 间完整对话

> 里程碑目标：让居民从"被动反应式决策"升级为"有计划、会复盘、能深度社交"的认知体。
> 论文对应：Generative Agents 的 Planning / Reflection / Dialogue 三大机制。

---

## 1. 目标与验收标准

| 验收项 | 标准 |
|---|---|
| 日程规划 | 每个居民每天清晨生成当日日程；决策时参考当前时段计划；计划偏离可被 LLM 主动标记重规划 |
| 反思引擎 | 记忆累积重要性超阈值时自动触发，生成带溯源的洞察（反思树），洞察作为新记忆参与后续检索 |
| 完整对话 | 对话持久化到 `conversations`/`conversation_turns` 表；话题枯竭自然结束；结束后生成双方视角总结记忆 + LLM 驱动的关系更新 |
| 可观测 | 规划/反思/对话全程产生事件流；新增 4 个查询 API |
| 成本 | 每模拟日新增 LLM 调用 < 100K tokens（约 ¥0.5） |

## 2. 现状基线（M2 完成后）

- tick 流程：时间推进 → 睡眠结算 → 三因子检索 → LLM 并发决策 → 应用行动 → 简版对话（`simple_exchange`，固定 6 轮）→ 观察记忆入库 → 批量打分+向量化 → Token 落库
- `Plan` / `Reflection` / `Conversation` / `ConversationTurn` 表已建，**全部未使用**
- 对话关系更新是固定 `+0.04`，无情感极性
- 决策 prompt 只有：人设 / 当前状态 / 同地点的人 / 检索记忆

## 3. 总体架构

```
                        ┌─────────────────────────────────────────┐
                        │              TickEngine                  │
                        │        (每 tick = 模拟 10 分钟)            │
                        └─────────────────────────────────────────┘
                                          │
   ┌──────────────┬───────────────┬──────┴──────────┬────────────────┬──────────────┐
   │ 1 时间推进    │ 2 清晨规划      │ 3 检索+决策      │ 4 应用行动      │ 5 对话管线    │ 6 反思检查
   │ 跨天/跨小时   │ PlanningEngine │ 决策prompt注入    │ (move/chat/..) │ DialogueEngine│ ReflectionEngine
   │              │ (错峰≤3人/tick)│ 当前时段计划      │                │ (≤2组/tick)   │ (≤2人/tick)
   └──────────────┴───────────────┴─────────────────┴────────────────┴──────────────┘
                                          │
              ┌───────────────────────────┴───────────────────────────┐
              │                    MemoryStreamService                  │
              │   SQLite(结构化记忆) ⇄ Chroma(向量)  三因子检索          │
              │   type: action/observation/conversation/reflection     │
              └───────────────────────────────────────────────────────┘
```

三个新引擎全部**复用 M2 的记忆流与检索能力**（规划参考近期记忆、反思检索证据、对话按对象检索），形成认知闭环：**规划 → 行动 → 记忆 → 反思 → 更好的规划**。

---

## 4. 子系统一：PlanningEngine 日程规划

### 4.1 数据模型（零 DDL，复用现有 `plans` 表）

```json
// plans.hourly 存 segments 结构
{
  "daily_goal": "完成草莓蛋糕新品试做，晚上去公园散步放松",
  "segments": [
    {"start": "07:00", "end": "08:00", "activity": "起床、晨练、简单早餐"},
    {"start": "08:00", "end": "12:00", "activity": "在满堂香面包房试做草莓蛋糕新品"},
    {"start": "12:00", "end": "13:30", "activity": "午餐+午休"},
    {"start": "13:30", "end": "17:30", "activity": "新品试吃反馈收集，联系白鸽策划活动"},
    {"start": "17:30", "end": "19:30", "activity": "晚饭+去镇公园散步"},
    {"start": "19:30", "end": "23:00", "activity": "整理配方笔记，早点休息"}
  ]
}
```

### 4.2 触发与错峰

- 触发条件：清醒时段（07:00 后）且该居民当日（`sim_day`）无 Plan → 加入规划队列
- **补规划机制**：不设窗口上界——模拟从午后恢复时，错过清晨的居民仍会补生成"从当前时间起"的剩余日程，避免整天无计划
- **错峰策略**：每 tick 最多规划 3 人（并发 gather，共享 LLM 信号量），10 个居民在 3–4 个 tick 内全部完成规划，避免单 tick 阻塞
- 规划完成后 emit 事件（type=`plan`，如"陈满堂规划了今天：完成草莓蛋糕新品试做"）

### 4.3 规划 Prompt 设计

输入上下文（一次调用生成全天日程）：
- 人设（职业/作息 work_hours/性格/目标）
- 星期几（周末 vs 工作日行为差异）
- **近期高重要性记忆 top-5**（三因子检索 query="昨天的经历和未完成的事"）→ 计划有连续性
- **最近一条反思**（如有）→ "昨天的思考影响了今天的安排"（论文闭环）

输出 JSON：`{"daily_goal": "...", "segments": [...]}`（约束：段必须覆盖 07:00–23:00，时间格式 HH:MM，活动 ≤30 字）

### 4.4 计划注入决策

`build_decision_prompt` 新增两个块：
```
你今天的计划：{daily_goal}
当前时段计划：{14:00-17:30 在面包房试做新品}
（若与现状不符）提示：你此刻偏离了计划——{现状} vs {计划}
```

决策 JSON 新增可选字段（P1，可裁剪）：
```json
{"action": "...", "replan": true, "replan_reason": "遇到突发状况"}
```
- 引擎收到 `replan=true` 时，为该居民重新生成**从当前时间起**的剩余日程（不重排已完成时段），每人每天最多 1 次重规划，防止规划抖动

### 4.5 成本

10 人 × 1 次/天 × (输入 700 + 输出 400) ≈ **11K tokens/模拟日**，可忽略。

---

## 5. 子系统二：DialogueEngine 对话管线升级

### 5.1 生命周期状态机

```
initiated ──► turn 1..N（交替发言）──► 话题枯竭 / 达上限 ──► 收尾管线 ──► ended
                │
                └─ 每 2 轮评估继续意愿（并入发言调用的 JSON 字段）
```

### 5.2 发言生成（升级现有逻辑）

一次 LLM 调用同时产出台词 + 继续意愿（省一次独立检测调用）：
```json
{"line": "诶你上次说的那个馅料，我试了！", "still_interested": true}
```
- 结束条件（任一满足）：双方任意一轮 `still_interested=false` 连续出现 / 达到最大 8 轮 / 台词为空
- 发言 prompt 复用现有结构：人设 + 对话历史 + **按"与对方相关"检索的记忆**（M2 已支持）

### 5.3 收尾管线（1 次调用，三种产物）

对话结束后一次 LLM 调用，输出：
```json
{
  "a_summary": "你和白鸽在镇广场聊了草莓蛋糕新品和周末活动策划，她答应帮忙宣传",
  "b_summary": "你和陈满堂聊了新品试吃，你答应在活动上帮他搭宣传位",
  "closeness_delta": 0.06,
  "sentiment": "positive"
}
```
- 双视角总结分别写入双方记忆流（type=`conversation`，重要性由后续批量打分给出）
- 关系更新：`closeness_delta ∈ [-0.15, +0.15]`（引擎内 clamp），`sentiment` 存入 Relationship 表——**取代现有固定 +0.04**

### 5.4 持久化（启用闲置表）

- `conversations`：每轮创建，status `ongoing` → `ended`
- `conversation_turns`：每句话一行（speaker_id/turn_no/content）→ 支撑"对话围观"页与 M6 日报素材

### 5.5 成本

约 10 组对话/模拟日 × 7 轮 × 450 tokens ≈ **32K tokens/模拟日**。

---

## 6. 子系统三：ReflectionEngine 反思引擎

### 6.1 触发机制（论文：累积重要性阈值）

```
trigger_value = SUM(importance) WHERE resident_id=我 AND sim_time > 上次反思时间 AND importance IS NOT NULL
触发条件：trigger_value ≥ 120（配置项 reflection_threshold）
```
- 不需要新表：上次反思时间从 `reflections` 表取该居民最近一条的 `sim_time`
- 反思产生的记忆同样计入累积（论文特性：洞察会级联出更深的洞察）

### 6.2 反思管线（3 次 LLM 调用，模仿论文两步法）

```
① 取材：上次反思以来的记忆（≤100 条，<20 条则跳过）
② 提问：LLM 从记忆中提炼 2~3 个"值得深思的高层问题"
   （例："我最近为什么总觉得疲惫？" / "我和方语桐的关系在怎么变化？"）
③ 求证：每个问题 → 三因子检索 top-8 相关记忆
④ 合成：LLM 综合证据生成 2~3 条洞察，每条带 source 记忆 id 溯源
⑤ 入库：Memory(type="reflection") + Reflection(content, source_memory_ids)
⑥ 事件：emit type=reflect（"周韶陷入了沉思：……"）——观测价值最高的时刻
```

### 6.3 反思树（M5 观测器的数据基础）

`Reflection.source_memory_ids` 指向源记忆；源记忆本身也可能是反思（反思的反思）→ 前端可递归展开溯源链。

### 6.4 调度约束

- 仅清醒、不在对话中的居民可反思；每 tick 最多 2 人（错峰）
- 单次反思管线 3 调用 ≈ 2.5K tokens，预计 10~15 次触发/模拟日 ≈ **40K tokens/模拟日**

---

## 7. tick 流程整合（新顺序）

```
1. 时间推进（跨天 → 清晨规划标记）
2. 睡眠结算（23:00–07:00）
3. 【M3】清晨规划：为无当日计划的居民生成日程（≤3 人/tick，并发）
4. 感知 + 三因子检索（M2 已有）
5. 【M3】决策 prompt 注入：当前时段计划 + 偏离提示；决策可选 replan 标志
6. LLM 并发决策 → 应用行动（现有）
7. 【M3】对话管线：≤2 组/tick，完整生命周期 + 收尾三产物
8. 观察记忆入库（现有）
9. 批量重要性打分 + 向量化（现有）
10.【M3】反思检查：累积值超阈值的居民（≤2 人/tick）跑反思管线
11. Token 落库、事件广播（现有）
```

错峰后的单 tick 耗时预估：决策 10 并发（~15s）+ 对话 2 组（~15s）+ 规划/反思（~10s，仅特定 tick）≈ **20–40s/tick**，与 M2 观测一致，不恶化。

---

## 8. API 与配置变更

### 新增 API（观测用）

| Method | Path | 说明 |
|---|---|---|
| GET | `/residents/{id}/plan?day=` | 当日日程（含 daily_goal + segments） |
| GET | `/residents/{id}/reflections?limit=` | 反思列表（含 source_memory_ids 溯源） |
| GET | `/conversations?limit=&day=` | 对话列表 |
| GET | `/conversations/{id}` | 对话详情（含全部 turns） |

### 新增配置（`.env`）

```
REFLECTION_THRESHOLD=120        # 反思触发累积阈值
REFLECTION_MIN_MEMORIES=20      # 触发反思的最低新记忆数
DIALOGUE_MAX_TURNS=8            # 对话轮次上限
DIALOGUE_PER_TICK=2             # 每 tick 对话组数上限
PLAN_PER_TICK=3                 # 每 tick 规划人数上限
```

### 事件类型扩展

`plan` / `reflect` / `conversation_end`（含双方视角摘要，供前端时间线渲染）

## 9. 测试计划

| 层 | 用例 |
|---|---|
| 单元 | segments 时段匹配函数；反思阈值计算（含"反思计入累积"）；对话结束条件矩阵；closeness clamp 负值；双视角总结解析容错 |
| 单元(mock LLM) | 规划 JSON 解析（畸形 segment 容错）；replan 只保留未来时段；反思管线记忆写入 + source_ids 正确 |
| 集成 | 烟雾测试：跑若干 tick 后断言——当日 Plan 存在、conversation_turns 有记录、反思触发后 Reflection 表有溯源、事件流含 plan/reflect 事件 |
| 人工 | 观察事件时间线：居民行为是否贴合日程；反思内容是否有洞察感 |

## 10. 实施步骤（每步独立可验证）

| 步骤 | 内容 | 验证方式 |
|---|---|---|
| S1 | PlanningEngine + 决策注入 + `/plan` API | 烟雾测试看事件流出现 plan 事件、决策 reason 引用计划 |
| S2 | DialogueEngine 升级（持久化/枯竭/双视角/LLM 关系更新）+ `/conversations` API | conversation_turns 表有数据、关系增量不再是固定值 |
| S3 | ReflectionEngine + `/reflections` API | 手动调低阈值跑 tick，观察反思事件与溯源 |
| S4 | 单测补全 + 烟雾测试扩展 + 文档更新 | pytest 全绿 + 端到端通过 |

## 11. 风险与应对

| 风险 | 应对 |
|---|---|
| 规划 JSON 畸形（时间格式/覆盖空洞） | 解析容错 + 空洞时段视为"自由活动"，不阻塞主流程 |
| 对话轮次变多导致 tick 拉长 | 每 tick 2 组上限 + 轮次上限 8 + 意愿字段提前终止 |
| 反思风暴（级联触发） | 每 tick ≤2 人 + 阈值可配置 + 反思记忆重要性封顶 9 |
| 重规划抖动 | 每人每天 ≤1 次 replan |
| LLM 调用失败 | 三个引擎全部 try/except 降级：无计划 → 纯情境决策；对话失败 → 保留已生成轮次直接 ended；反思失败 → 阈值累积值保留待下次 |

## 12. 实施状态（S1-S4 落地记录）

全部四个步骤已完成，`pytest` 38 个测试全绿，`scripts/smoke_test.py` 为 M1-M3 综合验收脚本（单次运行覆盖三引擎验收点，退出码表征结果）。

| 步骤 | 状态 | 落地要点与设计偏差 |
|---|---|---|
| S1 规划引擎 | ✅ | PlanningEngine + `/residents/{id}/plan` API + plan 事件。**偏差**：取消 09:00 规划窗口上界——改为清醒时段（07:00 后）随时补规划，晚于 09:00 只规划剩余时段；规避"暂停恢复后错过清晨窗口则整天无计划"的缺陷 |
| S2 对话引擎 | ✅ | 生命周期状态机（ongoing/ended）+ 单次 LLM 调用同时产出对话行与 still_interested 枯竭信号 + 双视角总结（a_summary/b_summary）+ closeness_delta（±0.15 截断）+ sentiment 持久化。新增 `GET /conversations`、`GET /conversations/{id}` |
| S3 反思引擎 | ✅ | 阈值触发（累积重要性 ≥120）+ 两步管线（提问→三因子检索取证→合成）+ `GET /residents/{id}/reflections` 反思树。**偏差**：Reflection 表增加 `memory_id` 列建立双向链（洞察本体即 Memory(type=reflection)，源记忆若也是反思可经 reflection_id 递归）；累积计算用 `sim_time >= since`（而非 `>`）使同刻落库的反思记忆计入下一轮累积，实现论文级联洞察 |
| S4 集成收尾 | ✅ | API 路由测试（conversations/reflections，含过滤与反思树递归链路断言）；三个烟雾测试合并为 `scripts/smoke_test.py`；修复 conversations/reflections 列表接口多余的 `reversed()` 导致旧→新排序缺陷 |

### 反思级联示例（真实运行观测）

```
沈天平 反思#3 (imp=9.0)：我反复「开始」核对旧街区产权文件……却始终没有完成稿
  源[action#77/#125/#133/#137/#170] 行动记忆 5 条
白鹭 反思#5 (imp=8.0)：我的行动模式是'先堵门、再要底'，但沈天平的逻辑是'先签字、再谈流程'
  源[conversation#53/#72/#82] + [action#143]
```

双视角反思对同一批对话形成互补洞察（一方反思自身程序固执，另一方反思战术被动），是"涌现"最直观的验收证据。
