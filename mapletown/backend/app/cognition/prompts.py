DECISION_SYSTEM = (
    "你是「枫叶镇」多智能体社会模拟中的居民决策大脑。"
    "严格根据居民的人设、当前状态、日程计划和最近记忆，做出真实、自然、有生活气息的决策，"
    "不要超出角色设定，不要编造记忆之外的重大事件。只输出合法 JSON。"
)

PLANNING_SYSTEM = (
    "你是「枫叶镇」居民的一日规划助手。根据人设、近期记忆和最近的思考，"
    "生成真实、有生活气息、可执行的日程。只输出合法 JSON。"
)

DIALOGUE_SYSTEM = (
    "你是「枫叶镇」多智能体社会模拟中的居民扮演引擎。"
    "用第一人称、口语化中文说话，严格贴合人设和你们的关系，"
    "不要旁白、不要解释。只输出合法 JSON。"
)

CONVERSATION_SUMMARY_SYSTEM = (
    "你是「枫叶镇」社会模拟的对话复盘引擎。根据两位居民的完整对话，"
    "分别以他们的第一人称视角提炼这次交流的收获，并评估关系变化。只输出合法 JSON。"
)

REFLECTION_SYSTEM = (
    "你是「枫叶镇」居民的内省反思引擎（Generative Agents 反思机制）。"
    "先从记忆中提炼值得深思的高层问题，再综合证据得出有洞察力的结论。只输出合法 JSON。"
)


def work_hint(persona: dict, workplace: str, hour: int, minute: int) -> str:
    now = hour + minute / 60
    try:
        start_str, end_str = [x.strip() for x in persona.get("work_hours", "9:00-17:00").split("-")]
        sh, sm = map(int, start_str.split(":"))
        eh, em = map(int, end_str.split(":"))
        if sh + sm / 60 <= now <= eh + em / 60:
            return f"按你的作息，此刻你通常在「{workplace}」忙自己的营生"
    except (ValueError, AttributeError):
        pass
    if 7 <= hour < 11:
        return "现在是上午，可以开始新一天的安排"
    if 11 <= hour < 14:
        return "现在是午间，可以去吃点东西或找人聊聊天"
    if 14 <= hour < 18:
        return "现在是下午，按自己的节奏安排"
    return "现在是晚间，可以自由安排：散步、去咖啡馆、找朋友，或早点回家"


def build_decision_prompt(
    *,
    name: str,
    age: int,
    persona: dict,
    sim_day: int,
    weekday: str,
    clock: str,
    hour: int,
    minute: int,
    location: str,
    activity: str,
    workplace: str,
    peers: list[dict],
    memory_lines: list[str],
    locations: list[str],
    plan_goal: str | None = None,
    plan_segment: str | None = None,
) -> str:
    p = persona or {}
    blocks = [
        f"现在是枫叶镇第 {sim_day} 天 {weekday} {clock}。",
        (
            f"你扮演：{name}，{p.get('identity', '')}（{age}岁）。\n"
            f"背景：{p.get('background', '')}\n"
            f"性格：{p.get('personality', '')}\n"
            f"近期目标：{p.get('goal', '')}\n"
            f"说话风格：{p.get('speech_style', '')}，口头禅：{p.get('catchphrase', '')}"
        ),
        f"当前状态：你在「{location}」，正在：{activity}。",
        work_hint(p, workplace, hour, minute),
    ]
    if plan_goal:
        blocks.append(f"你今天给自己定的计划：{plan_goal}")
    if plan_segment:
        blocks.append(
            f"当前时段的计划安排：{plan_segment}\n"
            "（尽量向计划靠拢；但如果实际情况与计划已经严重冲突，你可以在 JSON 里输出 "
            '"replan":true 和 "replan_reason":"30字内的调整理由"，系统会帮你重排今天剩余的安排）'
        )
    if peers:
        peer_text = "\n".join(f"- {q['name']}（{q['identity']}）：{q['activity']}" for q in peers)
        blocks.append(f"同一地点的人：\n{peer_text}")
    if memory_lines:
        memory_text = "\n".join(f"- {line}" for line in memory_lines)
        blocks.append(f"你最近的记忆（从新到旧）：\n{memory_text}")
    blocks.append(
        "请决定接下来 10 分钟的行动。可选 action：\n"
        "- move：换个地点（target_location 必须从以下选择：" + "、".join(locations) + "）\n"
        "- chat：和同一地点的某个人搭话（chat_with 填对方名字）\n"
        "- work：投入工作/营生\n"
        "- rest：放松休息\n"
        "- continue：保持现状\n"
        '输出 JSON：{"action":"...","target_location":"move时填","chat_with":"chat时填",'
        '"activity":"20字内的活动描述","reason":"30字内的理由",'
        '"replan":"仅当计划严重失效时输出true"}'
    )
    return "\n\n".join(blocks)


def build_planning_prompt(
    *,
    name: str,
    age: int,
    persona: dict,
    sim_day: int,
    weekday: str,
    memory_lines: list[str],
    last_reflection: str | None,
    from_time: str | None = None,
) -> str:
    p = persona or {}
    span_start = from_time or "07:00"
    blocks = [
        f"今天是枫叶镇第 {sim_day} 天，{weekday}。",
        (
            f"你扮演：{name}，{p.get('identity', '')}（{age}岁）。\n"
            f"背景：{p.get('background', '')}\n"
            f"作息：{p.get('work_hours', '9:00-17:00')}\n"
            f"近期目标：{p.get('goal', '')}"
        ),
    ]
    if memory_lines:
        memory_text = "\n".join(f"- {line}" for line in memory_lines)
        blocks.append(f"你近期的记忆（从新到旧）：\n{memory_text}")
    if last_reflection:
        blocks.append(f"你最近的一次思考：{last_reflection}")
    blocks.append(
        f"请规划你今天从 {span_start} 到 23:00 的日程，要符合人设、贴合近期记忆（比如继续没做完的事、"
        "回应最近的思考），周末/工作日作息自然区分。\n"
        '输出 JSON：{"daily_goal":"一句话概括今天","segments":['
        '{"start":"HH:MM","end":"HH:MM","activity":"30字内的安排"}]}\n'
        "要求：5~8 个时间段；工作日的上班时段应安排在工作的场所；"
        "时间段之间可以留白（留白=自由活动），不必完全连续。"
    )
    return "\n\n".join(blocks)


def build_dialogue_prompt(
    *,
    speaker_name: str,
    speaker_persona: dict,
    listener_name: str,
    listener_identity: str,
    location: str,
    history: list[dict],
    memory_lines: list[str],
    sim_time_str: str,
) -> str:
    p = speaker_persona or {}
    lines = [
        f"现在是{sim_time_str}，地点：{location}。",
        (
            f"你是 {speaker_name}（{p.get('identity', '')}，性格：{p.get('personality', '')}，"
            f"目标：{p.get('goal', '')}，说话风格：{p.get('speech_style', '')}）。"
        ),
        f"你正在和 {listener_name}（{listener_identity}）面对面聊天。",
    ]
    if memory_lines:
        lines.append("你最近的相关记忆：\n" + "\n".join(f"- {m}" for m in memory_lines))
    if history:
        chat_log = "\n".join(f"{h['speaker']}：{h['content']}" for h in history)
        lines.append(f"目前的对话：\n{chat_log}")
    else:
        lines.append("对话刚开始，由你先开口。")
    lines.append(
        "请输出 JSON：{\"line\":\"不超过50字的自然口语\",\"still_interested\":true 或 false}\n"
        "still_interested 判断：话题聊得投机、还有话说为 true；"
        "话题已经聊尽、有事要走或兴致缺缺为 false。"
    )
    return "\n\n".join(lines)


def build_conversation_summary_prompt(
    *,
    a_name: str,
    a_identity: str,
    b_name: str,
    b_identity: str,
    location: str,
    sim_time_str: str,
    history: list[dict],
) -> str:
    chat_log = "\n".join(f"{h['speaker']}：{h['content']}" for h in history)
    return "\n\n".join(
        [
            f"{sim_time_str}，{a_name}（{a_identity}）和 {b_name}（{b_identity}）在「{location}」聊了天。",
            f"完整对话：\n{chat_log}",
            "请分别以两人的第一人称视角复盘这次交流，并评估关系变化。输出 JSON：\n"
            f'{{"a_summary":"{a_name}的视角，以「你和{b_name}…」开头的完整句子，50字内，'
            "提炼聊了什么、达成了什么约定或感受\",\n"
            f'"b_summary":"{b_name}的视角，以「你和{a_name}…」开头，50字内",'
            '"closeness_delta":-0.15~0.15的小数（交流让彼此更亲近为正、产生隔阂为负，'
            '幅度与交流深度成正比，日常寒暄约0.03）,\n'
            '"sentiment":"positive / neutral / negative 之一（这次对话的整体情感基调）"}'
        ]
    )


def build_reflection_questions_prompt(*, name: str, identity: str, memory_lines: list[str]) -> str:
    listing = "\n".join(f"- {line}" for line in memory_lines)
    return "\n\n".join(
        [
            f"你扮演：{name}（{identity}）。以下是你近期的记忆（编号: 内容，从旧到新）：\n{listing}",
            "请以第一人称视角，从这些记忆中提炼 2~3 个值得深思的高层问题——"
            "关于人际关系的变化、自身状态的起伏、近期经历的规律或未解的困惑，"
            "不要提琐碎的事实性问题。",
            '输出 JSON：{"questions": ["问题1", "问题2", "问题3"]}',
        ]
    )


def build_reflection_insights_prompt(
    *,
    name: str,
    identity: str,
    question: str,
    evidence_lines: list[str],
) -> str:
    listing = "\n".join(f"- {line}" for line in evidence_lines)
    return "\n\n".join(
        [
            f"你扮演：{name}（{identity}）。",
            f"你正在思考的问题是：{question}",
            f"相关的记忆证据（编号: 内容）：\n{listing}",
            "请综合上述证据，以第一人称得出 1~2 条具体、有洞察力的结论"
            "（点出规律、因果或关系变化，贴合证据，不要泛泛而谈），"
            "并标注支撑该结论的记忆编号。",
            '输出 JSON：{"insights": [{"content": "结论", "source_ids": [编号], '
            '"importance": 1到10的数}]}（importance 表示这条洞察对你的重要程度）',
        ]
    )


def build_importance_prompt(memories: list[dict]) -> str:
    listing = "\n".join(f"{m['id']}: {m['content']}" for m in memories)
    return (
        "你是记忆重要性评估器。对下列每条居民记忆，按 1-10 打分：\n"
        "10=人生大事/重大冲突/重要关系变化，7=有意义的社交互动，4=日常活动，1=琐碎小事。\n\n"
        f"{listing}\n\n"
        '输出 JSON：{"scores":[{"id":记忆id,"score":分数}]}'
    )
