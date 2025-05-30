# draw_utils.py
import random
from datetime import datetime, timedelta

def draw_coupon():
    # 根據機率設定抽獎結果
    r = random.random()
    if r < 0.02:
        return 300
    elif r < 0.06:
        return 200
    elif r < 0.40:
        return 100
    else:
        return 0

def is_same_day(t1, t2):
    return t1.date() == t2.date()

def get_reset_time():
    # 每日重置時間設為 00:00
    now = datetime.now()
    reset_time = datetime(now.year, now.month, now.day)
    return reset_time
