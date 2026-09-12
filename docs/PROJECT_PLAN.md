# 枫叶镇 MapleTown — AI 小镇观测站

> 复现斯坦福爆火论文《Generative Agents: Interactive Simulacra of Human Behavior》并产品化的全栈 AI 项目。
> 一群有记忆、会反思、能自主规划的 AI 居民在小镇里生活，而你，是观测者、访谈者，也是导演。

---

## 1. 项目概述

### 1.1 一句话定位

**一个把论文级 Agent 认知架构（记忆流 / 检索 / 反思 / 规划）产品化的多智能体社会模拟平台**，用户可以围观 AI 居民的自主生活、翻看他们的记忆与内心、空降进小镇与居民对话、甚至作为导演改变小镇命运。

### 1.2 为什么这个项目值钱

| 维度 | 说明 |
|---|---|
| 理论深度 | 直接落地斯坦福 Generative Agents 论文的完整认知架构，不是"调 API"玩具 |
| 技术广度 | 记忆系统(RAG) + 多智能体编排 + 模拟时间引擎 + SSE 实时推送 + 全栈工程 |
| 演示效果 | AI 居民自主聊天、记仇、反思、办派对——面试现场演示极具冲击力 |
| 可解释性 | 独创"记忆观测器"：把 Agent 的黑盒认知过程（检索打分、反思过程）完整可视化 |
| 稀缺性 | 国内简历上做"行业套壳 LLM"的泛滥，做认知架构复现的凤毛麟角 |

### 1.3 面试一句话叙事

> "我复现了斯坦福 Generative Agents 论文并做了产品化：10 个 AI 居民在模拟小镇里自主生活，每个居民都有向量记忆流、重要性打分、三因子检索、周期性反思和日程规划。我把它做成了可观测平台——你能看到每个 Agent 的记忆、它的检索得分、它的反思链条，还能空降进去跟它对话，或者作为导演注入世界事件看整个社会如何反应。"

---

## 2. 理论基础（论文核心机制）

斯坦福 2023 年论文《Generative Agents》让 25 个 LLM 智能体在小村庄 Smallville 自主生活，涌现出办派对、传播八卦、建立关系等社会行为。其核心是五层认知架构，本项目全部实现：

| 机制 | 论文设计 | 本项目实现 |
|---|---|---|
| **记忆流 Memory Stream** | 所有观察/对话以自然语言存储，带时间戳与重要性分数 | SQLite 存结构化记忆 + Chroma 存向量，双写 |
| **检索 Retrieval** | `score = α·近期性 + β·重要性 + γ·相关性` 加权取 Top-K | 完整实现三因子打分，且**在 UI 上展示每条记忆的得分** |
| **反思 Reflection** | 累积重要性超阈值时，自动合成更高层洞察，作为新记忆入库 | 每 Agent 维护"重要性累积值"，触发反思 → 生成洞察 → 记忆树 |
| **规划 Planning** | 每日生成日程 → 分解到小时 → 被事件打断后重规划 | 每模拟日清晨生成日程 JSON，中断时 LLM 决策是否重规划 |
| **行动与对话** | 基于人设+记忆+计划决策行动；共处一地的 Agent 可开启多轮对话 | 每 tick 决策行动；同地点触发对话管线，逐轮生成并互相写入记忆 |

---

## 3. 功能规划

### 3.1 核心功能（P0）

**F1 模拟时间引擎（心跳）**
- 1 tick = 10 分钟模拟时间；默认 1 tick / 3 秒真实时间（可调 1x/2x/5x，可暂停）
- 一模拟日 = 144 ticks ≈ 7 分钟真实时间
- 后台 asyncio 循环驱动，时间、调度、状态全部事务化

**F2 居民认知系统（灵魂）**
- 10 名初始居民，每人：身份人设卡（性格/职业背景/目标/口头禅）+ 记忆流 + 日程 + 关系
- 每 tick：感知周围事件 → 三因子检索相关记忆 → 结合人设/计划/状态决策行动
- 行动类型：继续当前活动 / 移动 / 主动搭话 / 独处思考

**F3 Agent 间对话**
- 共处一地且至少一方决定搭话 → 开启对话
- 每轮：说话者检索"与当前话题相关的记忆 + 与对方的历史" → 生成回应
- 对话结束写入双方记忆流（各自视角），更新亲密度
- 最多 12 轮防死循环

**F4 小镇全景 + 实时事件流**
- 16-bit 像素风 SVG 小镇地图（320×200 游戏像素，程序化逐像素绘制）：14 个地点——枫叶公寓、枫语咖啡馆、图书馆、社区诊所、满堂香面包房、镇公园、小学、试验田、律师事务所、白日梦想工作室、镇广场（喷泉）、河堤步道（河流/小鸭/观景台）、老街市集（摊位/货箱）、枫林小径（秋日枫林）
- 居民为像素小人精灵（走路摆动动画），随行动在地图上移动
- 昼夜光照系统：随模拟时间自动切换白天/黄昏/夜晚三场景（夜晚建筑亮灯 + 路灯光晕）
- 地图支持滚轮缩放、拖拽平移、分区快捷导航（镇中心/老街市集/河堤步道/枫林小径/镇公园）
- SSE 推送实时事件流："苏晴 在咖啡馆和阿凯聊起了画展"

**F5 记忆观测器（杀手级演示功能）**
- 居民详情页展示完整记忆流：时间/类型/重要性/内容
- **检索演示框**：输入任意 query，实时显示该居民记忆的三因子得分排序过程
- 反思树：洞察节点 → 展开溯源到它由哪些源记忆合成

**F6 空降对话**
- 用户以"神秘访客"身份出现在某地点与居民对话（SSE 流式）
- 居民用"人设 + 对用户的既有记忆 + 当前状态"回应
- 对话内容写入居民记忆流——**居民会记住你，下次提起你**

### 3.2 增值功能（P1）

**F7 社交图谱**：亲密度 = 对话频次 + 记忆提及频次 + LLM 情感打分综合；ECharts 力导向图，边宽=亲密度，可看随时间的演化曲线

**F8 小镇日报**：每模拟日结束，"编辑 Agent"汇总当日事件流生成报纸（头版标题 + 要闻 + 花边八卦 + 天气），报纸风排版

**F9 导演模式**：注入世界事件（"明天全镇停电"、"广场出现流浪猫"），居民感知后自然调整行为；可调模拟速度/暂停

**F10 仪表盘**：事件数、对话数、反思数、Token 成本曲线、居民活跃度热力图

### 3.3 居民设定（10 人，职业背景 × 故事种子 × 关系钩子）

| 居民 | 年龄 | 职业与背景 | 性格 | 故事种子 | 关系钩子 |
|---|---|---|---|---|---|
| 苏晴 | 33 | 咖啡馆「枫语」老板娘；前互联网大厂运营总监，裸辞盘下街角旧茶馆改造而成 | 高情商、消息灵通、全镇信息枢纽 | 想扩建二楼书吧但资金不足 | 与沈天平互怼成瘾；林知遥的闺蜜 |
| 沈天平 | 47 | 执业律师（兼职镇法律顾问）；省城红圈所前合伙人，因风波退隐小镇开个人工作室 | 严谨、毒舌、刀子嘴豆腐心 | 想竞选镇议事会代表，推动旧街区改造 | 每天准时出现在枫语咖啡馆"找茬" |
| 周砚 | 58 | 图书管理员；曾任省文联编辑，笔名"晚枫"的隐居作家 | 寡言、观察力细腻、外冷内热 | 暗写 12 年的长篇小说《镇年》以小镇真人为原型，不敢投稿 | 察觉许愿总在深夜还书 |
| 方语桐 | 28 | 小学语文教师；师范定向生，主动申请回镇任教 | 元气、理想主义、有点轴 | 筹办周末读书会和儿童读书角，缺书缺志愿者 | 想请周砚出山讲故事；陈满堂的孙子在她班里 |
| 林知遥 | 35 | 社区诊所全科医生；三甲医院急诊科 8 年，为照顾母亲回镇 | 专业可靠、爱唠叨健康 | 建全镇健康档案时发现两位居民的数据"对不上号" | 陈满堂是控糖重点对象；逮许愿教育作息 |
| 陈满堂 | 52 | 「满堂香」面包房主理人；祖传三代糕点铺，接手父辈老窑炉 | 憨厚固执、起早贪黑 | 连锁品牌要进镇，创新招牌面包缺一味"记忆中的味道" | 江夏的有机面粉或是转机 |
| 顾寒山 | 62 | 退休刑警（全镇"编外治安员"）；30 年刑侦生涯，退休后每天绕镇巡逻三圈 | 沉默、观察力惊人、正义感刻在骨子里 | 总觉得小镇"最近有事"：快递量变多、周砚的灯亮到后半夜、河堤出现生面孔 | 沈天平的老熟人；居民见他都下意识站直 |
| 许愿 | 26 | 独立游戏开发者；大厂数值策划裸辞，线上 50 万粉"夜猫主播"，白天睡觉晚上码代码 | 社恐、线上话痨线下结巴 | 独立游戏《小镇谜案》上线前冲刺，灵感全部来自小镇日常 | 匿名向顾寒山"取材"探案技巧；向周砚借悬疑小说 |
| 白鹭 | 29 | 婚庆与活动策划师；省城 4A 广告公司 AE，厌倦甲乙方拉扯回镇开"白日梦想"工作室 | 浪漫、行动力强、爱撮合人 | 策划"枫叶镇 200 周年镇庆"，缺钱缺场地缺批文 | 拉沈天平咨询批文流程；盯上全镇单身青年 |
| 江夏 | 24 | 农学研究生（乡村振兴专项）；农业大学土壤学硕士在读，驻村研究土壤改良，租了三亩试验田 | 耿直、执拗、数据狂魔 | 试验田数据出现异常波动；想说服陈满堂用本地有机面粉 | 与许愿是网友（互不知情） |

**四条暗线设计（涌现引擎）**：

- **经济链**：江夏的有机面粉 → 陈满堂的创新面包 → 苏晴咖啡馆的下午茶套餐
- **信息链**：苏晴（人情情报）+ 顾寒山（异常观察）+ 周砚（借书记录）三源交汇，八卦会自己传播
- **情感线**：沈天平 × 苏晴欢喜冤家；许愿 × 江夏匿名网友互不知情
- **秘密线**：周砚的小说原型 / 林知遥的体检疑点 / 许愿的匿名取材

**替补席（可替换或扩展）**：岳巧枝（54，非遗竹编手艺人，传承焦虑）、夏天佑（31，民宿老板兼户外向导，自来熟）、唐小满（38，快递驿站站长，小镇物流枢纽）、聂风（40，理发师，手艺+情报二合一）

---

## 4. 技术架构

### 4.1 技术栈

| 层 | 选型 | 理由 |
|---|---|---|
| 后端框架 | Python 3.10 + FastAPI | 异步、SSE 友好、自动文档 |
| ORM/数据库 | SQLAlchemy 2.0 + SQLite（可切 MySQL） | 记忆/事件结构化存储 |
| 向量库 | Chroma（本地持久化） | 记忆流向量检索，零运维 |
| LLM | DeepSeek API（OpenAI 兼容） | 用户已确认提供秘钥；**前缀缓存**天然适配"人设固定前缀"，省钱 |
| 编排 | LangChain + 原生 Agent Loop | 提示词模板管理 + 流式调用 |
| Embedding | 本地 BGE (bge-small-zh) 或 API | 免费优先 |
| 实时推送 | SSE (sse-starlette) | 事件流/对话流 |
| 前端 | Vue3 + Vite + Element Plus + Pinia | 组件全、上手快 |
| 可视化 | ECharts + 手绘 SVG 地图 | 关系图谱/成本曲线/小镇地图 |
| 测试 | pytest + httpx | 接口回归 |

### 4.2 系统架构图（文字版）

```
┌───────────────────── 前端 Vue3 SPA ─────────────────────┐
│  登录 | 仪表盘 | 小镇全景(SVG+SSE) | 居民详情(记忆观测器)  │
│  社交图谱 | 小镇日报 | 空降对话(SSE) | 导演面板           │
└────────────────── REST + SSE /api/v1 ──────────────────┘
                          │
┌───────────────────── FastAPI 后端 ──────────────────────┐
│  路由层: auth / sim / residents / events / chat / news  │
│  服务层:                                               │
│   ├── TickEngine   模拟时间引擎(asyncio 心跳+调度)      │
│   ├── CognitiveCore 认知核心(检索打分/行动决策)         │
│   ├── ReflectionEngine 反思引擎(累积阈值触发)            │
│   ├── PlanningEngine  日程规划(每日生成+中断重规划)      │
│   ├── DialogueEngine  Agent间对话(逐轮生成+记忆互写)    │
│   └── NewspaperAgent 小镇日报(每日汇总)                 │
│  存储层: SQLite(结构化) + Chroma(向量) + EventBus(SSE)  │
└────────────────────────────────────────────────────────┘
        │                        │                  │
   DeepSeek LLM             本地 BGE           前缀缓存自动命中
```

### 4.3 Tick 引擎流水线（每 tick 执行）

```
1. 时间推进      sim_time += 10min；处理跨天逻辑（清晨规划/日报）
2. 感知阶段      每个 Agent 获取同地点事件 + 全镇广播事件
3. 对话判定      共处一地 → 判定是否开启/继续对话（有对话优先推进）
4. 行动决策      无对话中的 Agent：三因子检索 → LLM 决策行动（并发，信号量限流）
5. 记忆入库      新观察写入记忆流（LLM 重要性打分 1-10 + 向量化，惰性嵌入）
6. 反思检查      累积重要性 > 150 的居民触发反思管线
7. 事件广播      本 tick 产生的世界事件 → SSE 推送前端
```

### 4.4 认知核心：检索打分公式（论文核心，UI 可视化）

```
retrieve_score(memory, query, now) =
      α × 0.99^(Δ模拟小时)          # 近期性：指数衰减
    + β × importance(memory)        # 重要性：入库时 LLM 打分 1-10，归一化
    + γ × cosine_sim(emb(memory), emb(query))  # 相关性：向量余弦
默认 α=β=γ=1.0（论文值），前端"检索演示框"展示每条记忆三项分与总分
```

### 4.5 成本控制（工程亮点，面试谈资）

- **前缀缓存**：人设+系统指令作为稳定前缀，DeepSeek 自动缓存命中价格 1/10
- **惰性嵌入**：记忆写入时仅打分，向量嵌入在首次被检索时计算（可选）
- **并发限流**：asyncio.Semaphore 控制 LLM 并发 + 指数退避重试
- **预算熔断**：单日 Token 超预算自动暂停模拟，仪表盘展示成本曲线
- 预估：10 居民 × 144 tick ≈ 1440 次决策调用/模拟日 ≈ **¥3~4/模拟日**（含对话与反思）

---

## 5. 数据模型设计

```sql
-- 认证
users(id, username, email, hashed_password, created_at)

-- 居民
residents(id, name, avatar, persona_json,      -- 身份/性格/背景/目标/口头禅
          home, workplace, current_location, current_activity)

-- 记忆流（核心表）
memories(id, resident_id,
         type,            -- observation/conversation/reflection/user_chat
         content, sim_time, importance,   -- LLM 打分 1-10
         embedding_id,    -- Chroma 中的向量 id
         last_access_sim_time,            -- 近期性衰减用
         created_at)

-- 反思（记忆树的父节点）
reflections(id, resident_id, content, source_memory_ids_json, sim_time)

-- 日程
plans(id, resident_id, sim_day, daily_goal, hourly_json, updated_at)

-- 世界事件（小镇时间线 = SSE 事件流来源）
world_events(id, tick, sim_time, type,       -- move/chat/act/system/director
             content, participants_json, location)

-- Agent 对话
conversations(id, sim_time, location, status)   -- ongoing/ended
conversation_turns(id, conversation_id, turn_no, speaker_id, content)

-- 空降对话（用户↔居民）
user_chats(id, resident_id, user_id, role, content, sim_time)

-- 关系（社交图谱）
relationships(id, a_id, b_id, closeness REAL, sentiment, updated_sim_time)

-- 模拟状态（单行）
sim_state(id, sim_time, tick, speed, running, current_sim_day)

-- 成本
token_usage(id, sim_day, calls, prompt_tokens, completion_tokens, cost)

-- 小镇日报
newspapers(id, sim_day, title, content_json, created_at)
```

**向量库设计**：Chroma 单 collection `memories`，metadata 带 `resident_id`（检索时过滤），比每居民一个 collection 更省资源——这是可以在面试里讲的取舍。

---

## 6. API 设计（前缀 /api/v1）

```
# 认证
POST /auth/register            POST /auth/login          GET /auth/me

# 模拟控制
POST /sim/control              # {action: start|pause|speed, value}
GET  /sim/state

# 居民与认知观测
GET  /residents                # 列表+当前状态
GET  /residents/{id}           # 档案+当前活动+计划
GET  /residents/{id}/memories?type=&page=     # 记忆流（分页）
POST /residents/{id}/retrieve  # 检索演示：传入query返回打分排序的记忆 ⭐
GET  /residents/{id}/reflections               # 反思树
GET  /residents/{id}/relationships             # 该居民的关系

# 小镇时间线
GET  /events?limit=            GET /stream/feed          # SSE 实时事件流
GET  /conversations             GET /conversations/{id}   # 对话围观

# 空降对话
POST /chat/{resident_id}/stream # SSE 流式对话（带记忆上下文）

# 导演模式
POST /director/events          # {type, content, location}

# 日报与统计
GET  /newspaper/latest          GET /newspaper?day=
GET  /stats                     # 仪表盘聚合数据
```

---

## 7. 前端页面设计

| 页面 | 路由 | 核心内容 |
|---|---|---|
| 登录/注册 | /login /register | 背景图 10s 轮播渐变 + 枫叶 Logo（红橙渐变、15° 倾斜） |
| 仪表盘 | / | 统计卡片 + Token 成本曲线 + 居民活跃热力图 |
| 小镇全景 | /town | SVG 地图 + 居民移动动画 + 右侧 SSE 实时事件流 + 模拟控制条 |
| 居民详情 | /resident/:id | 档案卡 + Tab：记忆流 / 反思树 / 当日计划 / 关系 |
| 社交图谱 | /graph | ECharts 力导向图（边宽=亲密度）+ 演化时间轴 |
| 小镇日报 | /newspaper | 报纸排版风：头版/要闻/花边/天气 |
| 空降对话 | /chat | 居民选择 + SSE 流式对话 + 右侧"TA 想起的记忆"实时展示 |
| 对话围观 | /conversations | Agent 对话回放/直播 |
| 导演面板 | /director | 事件注入 + 速度控制 + 居民管理 |

**设计基调**：暖色小镇风（红橙渐变主色呼应枫叶 Logo）、大字号可读性优先、卡片化布局。

---

## 8. 项目目录结构

```
mapletown/
├── docs/PROJECT_PLAN.md
├── backend/
│   ├── requirements.txt  .env.example
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口 + CORS + 路由挂载
│   │   ├── core/config.py  security.py
│   │   ├── db/session.py
│   │   ├── models/                  # user/resident/memory/plan/event/...
│   │   ├── schemas/
│   │   ├── api/routes/              # auth/sim/residents/events/chat/news/director
│   │   ├── engine/
│   │   │   ├── tick_engine.py       # 模拟时间引擎（心跳循环）
│   │   │   ├── perception.py        # 感知：同地点事件聚合
│   │   │   ├── decision.py          # 行动决策
│   │   │   ├── dialogue.py          # Agent 间对话管线
│   │   │   ├── reflection.py        # 反思引擎
│   │   │   ├── planning.py          # 日程规划
│   │   │   └── newspaper.py         # 日报 Agent
│   │   ├── cognition/
│   │   │   ├── memory_stream.py     # 记忆流写入/打分/惰性嵌入
│   │   │   ├── retriever.py         # 三因子检索 ⭐
│   │   │   └── prompts.py           # 全部提示词集中管理
│   │   ├── llm/client.py            # DeepSeek 封装 + 重试 + 用量统计
│   │   └── services/                # 业务编排层
│   ├── scripts/seed_residents.py    # 8 居民初始化
│   └── tests/
├── frontend/
│   └── src/{api, stores, router, views, components/...}
└── README.md
```

---

## 9. 开发里程碑

| 阶段 | 内容 | 验收标准 | 状态 |
|---|---|---|---|
| M1 | 后端骨架 + 数据模型 + Tick 引擎（无 LLM 随机行动版） | 模拟时间流动，居民随机移动产生事件 | ✅ 完成（已接入 DeepSeek，行动由 LLM 驱动） |
| M2 | 认知核心：记忆流 + 重要性打分 + 三因子检索 | 居民行动由记忆驱动；检索接口返回得分明细 | ✅ 完成（Chroma + fastembed/bge-small-zh，`GET /residents/{id}/memory-search` 返回三因子得分分解，9 个单元测试） |
| M3 | 规划 + 反思 + Agent 对话 | 居民按日程生活、产生反思洞察、自主聊天 | ✅ 完成（三引擎落地：清晨/补规划 + 决策注入 + replan；对话持久化 + 枯竭检测 + 双视角总结 + LLM 关系更新；反思阈值触发 + 两步管线 + 反思树溯源；38 个单元测试 + `scripts/smoke_test.py` M1-M3 综合验收） |
| M4 | 前端骨架 + 登录 + 小镇全景 + SSE 事件流 | 浏览器实时看到小镇动态 | ✅ 完成（Vue3+Vite+Element Plus+Pinia；登录/注册页背景 10s 轮播渐变+可点指示点+枫叶 Logo；SVG 手绘小镇地图 11 地点+居民移动动画；SSE 实时事件流（LIVE 指示+事件类型标签）；模拟控制条启停/1x-2x-5x 变速；Vite 代理转发 API 免 CORS） |
| M5 | 记忆观测器 + 空降对话 + 社交图谱 | 核心演示链路全通 | ⬜ |
| M6 | 日报 + 导演模式 + 仪表盘 + pytest + README | 完整可交付 | ⬜ |

---

## 10. 风险与应对

| 风险 | 应对 |
|---|---|
| LLM 成本失控 | 预算熔断 + 前缀缓存 + 速度可调 + 居民数可配 |
| API 并发限制 | Semaphore 限流 + 指数退避重试 |
| 记忆膨胀 | 反思即压缩 + last_access 衰减 + 分页 |
| 对话死循环 | 最大轮次限制 + 话题枯竭检测 |
| 模拟时间不一致 | 全局单调 sim_time，tick 事务化推进 |
| Agent 行为同质化 | 人设卡差异度调优 + 温度分层（决策 0.4 / 对话 0.8 / 反思 0.3） |

---

## 11. 待用户确认事项

1. **DeepSeek API Key**（你已说会提供）——填入 `backend/.env`
2. Embedding 方案：默认本地 BGE（免费，首次下载约 100MB），可换 SiliconFlow API
3. 项目名「枫叶镇 MapleTown」是否满意？居民人设可随时改
4. 认证模块保留（JWT 登录注册），保证项目"完整前后端"成色
