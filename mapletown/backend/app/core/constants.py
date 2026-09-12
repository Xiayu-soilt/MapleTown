import datetime as dt

SIM_START = dt.datetime(2026, 9, 14, 8, 0)

LOCATIONS = [
    "枫叶公寓",
    "枫语咖啡馆",
    "图书馆",
    "社区诊所",
    "满堂香面包房",
    "镇公园",
    "小学",
    "试验田",
    "律师事务所",
    "白日梦想工作室",
    "镇广场",
    "河堤步道",
    "老街市集",
    "枫林小径",
]

WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def sim_day_of(sim_time: dt.datetime) -> int:
    return (sim_time - SIM_START).days + 1


def is_sleeping_hour(hour: int) -> bool:
    return hour >= 23 or hour < 7
