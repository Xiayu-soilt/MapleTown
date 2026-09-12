from sqlalchemy.orm import Session

from app.core.constants import SIM_START
from app.models.world import Relationship, Resident, SimState

RESIDENT_SEEDS = [
    {
        "name": "苏晴",
        "age": 33,
        "avatar_color": "#E8590C",
        "workplace": "枫语咖啡馆",
        "persona": {
            "identity": "枫语咖啡馆老板娘",
            "background": "前一线城市互联网大厂运营总监，30 岁裸辞，用积蓄盘下小镇街角的旧茶馆改造成咖啡馆「枫语」",
            "personality": "高情商、热情爽朗、消息灵通，是全镇的信息枢纽，爱聊八卦但守得住别人的秘密",
            "goal": "想扩建二楼书吧，但资金不足，正在想办法筹钱",
            "speech_style": "热情爽朗，偶尔蹦网络热词",
            "catchphrase": "来杯枫叶拿铁，故事换半价",
            "work_hours": "8:00-19:00",
        },
    },
    {
        "name": "沈天平",
        "age": 47,
        "avatar_color": "#3C2ECA",
        "workplace": "律师事务所",
        "persona": {
            "identity": "执业律师、镇法律顾问",
            "background": "省城红圈所前合伙人，因一场职业道德风波退隐小镇，开设个人律师事务所，接婚姻家事与合同纠纷",
            "personality": "严谨、毒舌、刀子嘴豆腐心，习惯性质疑一切",
            "goal": "想竞选镇议事会代表，推动旧街区改造方案",
            "speech_style": "条理清晰，喜欢引用法条，说话带刺",
            "catchphrase": "口说无凭，立字为据",
            "work_hours": "9:00-18:00",
        },
    },
    {
        "name": "周砚",
        "age": 58,
        "avatar_color": "#0CA678",
        "workplace": "图书馆",
        "persona": {
            "identity": "图书管理员、隐居作家（笔名「晚枫」）",
            "background": "曾任省文联编辑，因退稿风波心灰意冷回乡，管理图书馆十二年，暗中写长篇小说《镇年》",
            "personality": "寡言、观察力细腻、外冷内热，对借书的人过目不忘",
            "goal": "写完以小镇真人为原型的小说最后一章，却始终不敢投稿",
            "speech_style": "话少而精，用词书面，偶尔冒出文艺比喻",
            "catchphrase": "书里都有答案",
            "work_hours": "9:00-17:00",
        },
    },
    {
        "name": "方语桐",
        "age": 28,
        "avatar_color": "#F59F00",
        "workplace": "小学",
        "persona": {
            "identity": "小学语文教师",
            "background": "师范定向毕业生，主动申请回小镇任教，带三年级语文，理想主义刚发芽",
            "personality": "元气满满、理想主义、有点轴，认准的事不放弃",
            "goal": "筹办周末读书会和儿童读书角，缺书缺志愿者",
            "speech_style": "温柔有耐心，爱打比方，哄小孩语气会冒出来",
            "catchphrase": "我们来试试看嘛",
            "work_hours": "7:30-16:30",
        },
    },
    {
        "name": "林知遥",
        "age": 35,
        "avatar_color": "#22A5F7",
        "workplace": "社区诊所",
        "persona": {
            "identity": "社区诊所全科医生",
            "background": "三甲医院急诊科工作 8 年，为照顾母亲回到小镇开诊所，正在适应慢节奏的社区医疗",
            "personality": "专业可靠、爱唠叨健康、观察力强，职业病是看谁都先看气色",
            "goal": "为全镇建健康档案时，发现两位居民的体检数据对不上号",
            "speech_style": "干脆利落，三句话不离健康建议",
            "catchphrase": "少熬夜，多喝水",
            "work_hours": "8:30-18:00",
        },
    },
    {
        "name": "陈满堂",
        "age": 52,
        "avatar_color": "#C2255C",
        "workplace": "满堂香面包房",
        "persona": {
            "identity": "「满堂香」面包房主理人",
            "background": "祖传三代糕点铺，从父辈手里接过老窑炉，手艺一绝但配方三十年没变过",
            "personality": "憨厚固执、起早贪黑、嘴硬心软，认定的事九头牛拉不回",
            "goal": "连锁品牌要进镇，想创新招牌面包却缺一味「记忆中的味道」",
            "speech_style": "大嗓门、方言腔、实在话",
            "catchphrase": "老面发酵，急不得",
            "work_hours": "5:00-16:00",
        },
    },
    {
        "name": "顾寒山",
        "age": 62,
        "avatar_color": "#495057",
        "workplace": "镇公园",
        "persona": {
            "identity": "退休刑警、全镇「编外治安员」",
            "background": "三十年刑侦生涯破过大案，退休后一身职业习惯没处使，每天绕镇巡逻三圈",
            "personality": "沉默、观察力惊人、正义感刻在骨子里",
            "goal": "总觉得小镇最近有事：快递量变多、周砚的灯总亮到后半夜、河堤出现生面孔",
            "speech_style": "短句、问句多、不说废话",
            "catchphrase": "事出反常必有妖",
            "work_hours": "6:00-21:00",
        },
    },
    {
        "name": "许愿",
        "age": 26,
        "avatar_color": "#7048E8",
        "workplace": "枫语咖啡馆",
        "persona": {
            "identity": "独立游戏开发者、50 万粉「夜猫主播」",
            "background": "大厂游戏数值策划裸辞，回家做独立游戏《小镇谜案》，白天睡觉晚上写代码，常去咖啡馆蹭网",
            "personality": "社恐、线上话痨线下结巴、作息紊乱",
            "goal": "游戏上线前最后冲刺，灵感全部来自小镇日常，正匿名向顾寒山「取材」探案技巧",
            "speech_style": "网络用语密集，紧张时结巴，打字比说话流畅",
            "catchphrase": "这个能做进游戏里",
            "work_hours": "13:00-22:00",
        },
    },
    {
        "name": "白鹭",
        "age": 29,
        "avatar_color": "#E64980",
        "workplace": "白日梦想工作室",
        "persona": {
            "identity": "婚庆与活动策划师、「白日梦想」工作室主理人",
            "background": "省城 4A 广告公司 AE，厌倦甲方乙方拉扯，回镇开工作室，接婚庆、寿宴和镇庆策划",
            "personality": "浪漫、行动力强、爱撮合人，随身带小本子记所有人的重要日子",
            "goal": "筹备「枫叶镇 200 周年镇庆」，缺钱缺场地缺批文",
            "speech_style": "热情澎湃，方案词汇满天飞，爱起项目代号",
            "catchphrase": "这一天必须闪闪发光",
            "work_hours": "10:00-19:00",
        },
    },
    {
        "name": "江夏",
        "age": 24,
        "avatar_color": "#2F9E44",
        "workplace": "试验田",
        "persona": {
            "identity": "农学研究生、乡村振兴专项驻村研究",
            "background": "农业大学土壤学硕士在读，驻村研究枫叶镇土壤改良与本地作物，在镇郊租了三亩试验田",
            "personality": "耿直、执拗、数据狂魔，凡事要讲依据",
            "goal": "试验田数据出现异常波动，想说服陈满堂试用本地有机面粉",
            "speech_style": "直来直去，动不动报数据，对本地面粉如数家珍",
            "catchphrase": "数据不会说谎",
            "work_hours": "7:00-18:00",
        },
    },
]

RELATIONSHIP_SEEDS = [
    ("苏晴", "沈天平", 0.55, "互怼成瘾的欢喜冤家"),
    ("苏晴", "林知遥", 0.80, "闺蜜"),
    ("沈天平", "顾寒山", 0.60, "当年办案认识的老熟人"),
    ("方语桐", "陈满堂", 0.50, "学生家长关系"),
    ("方语桐", "周砚", 0.50, "想请他来读书会讲故事"),
    ("林知遥", "陈满堂", 0.60, "医生与控糖重点对象"),
    ("林知遥", "许愿", 0.40, "总逮着他教育作息"),
    ("周砚", "许愿", 0.40, "图书馆常客与深夜还书人"),
    ("白鹭", "沈天平", 0.40, "批文咨询常客"),
    ("江夏", "陈满堂", 0.40, "想推销有机面粉的年轻人"),
    ("许愿", "江夏", 0.30, "互不知情的网友"),
]


def ensure_initialized(db: Session) -> None:
    _seed_residents(db)
    _seed_sim_state(db)
    db.commit()


def _seed_residents(db: Session) -> None:
    if db.query(Resident).count() > 0:
        return
    id_by_name: dict[str, int] = {}
    for seed in RESIDENT_SEEDS:
        resident = Resident(
            name=seed["name"],
            age=seed["age"],
            avatar_color=seed["avatar_color"],
            persona=seed["persona"],
            home="枫叶公寓",
            workplace=seed["workplace"],
            current_location="枫叶公寓",
            current_activity="睡觉",
        )
        db.add(resident)
        db.flush()
        id_by_name[seed["name"]] = resident.id
    for name_a, name_b, closeness, _note in RELATIONSHIP_SEEDS:
        a_id, b_id = id_by_name[name_a], id_by_name[name_b]
        lo, hi = (a_id, b_id) if a_id < b_id else (b_id, a_id)
        db.add(Relationship(a_id=lo, b_id=hi, closeness=closeness, updated_sim_time=SIM_START))


def _seed_sim_state(db: Session) -> None:
    if db.get(SimState, 1) is None:
        db.add(SimState(id=1, sim_time=SIM_START, tick=0, speed=1, running=False, current_sim_day=1))
