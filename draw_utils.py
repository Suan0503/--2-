import random
from datetime import datetime
from pytz import timezone
from linebot.models import FlexSendMessage

def draw_coupon():
    chance = random.random()
    if chance < 0.02:
        return 300
    elif chance < 0.06:
        return 200
    elif chance < 0.40:
        return 100
    else:
        return 0

def has_drawn_today(user_id, CouponModel):
    tz = timezone("Asia/Taipei")
    today = datetime.now(tz).date()
    return CouponModel.query.filter_by(line_user_id=user_id, date=str(today)).first()

def save_coupon_record(user_id, amount, CouponModel, db):
    tz = timezone("Asia/Taipei")
    today = datetime.now(tz).date()
    new_coupon = CouponModel(
        line_user_id=user_id,
        amount=amount,
        date=str(today),
        created_at=datetime.now(tz)
    )
    db.session.add(new_coupon)
    db.session.commit()
    return new_coupon

def get_today_coupon_flex(user_id, display_name, amount):
    now = datetime.now(timezone("Asia/Taipei"))
    today_str = now.strftime("%Y/%m/%d")
    emoji_date = f"📅 {now.strftime('%m/%d')}"
    expire_time = "23:59"

    if amount == 0:
        text = "很可惜沒中獎呢～明天再試試看吧🌙"
        color = "#999999"
    else:
        text = f"🎁 恭喜你抽中 {amount} 元折價券"
        color = "#FF9900"

    return FlexSendMessage(
        alt_text="每日抽獎結果",
        contents={
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": emoji_date,
                        "weight": "bold",
                        "size": "lg"
                    },
                    {
                        "type": "text",
                        "text": f"用戶：{display_name}",
                        "size": "sm",
                        "color": "#888888"
                    },
                    {
                        "type": "text",
                        "text": f"日期：{today_str}",
                        "size": "sm",
                        "color": "#888888"
                    },
                    {"type": "separator"},
                    {
                        "type": "text",
                        "text": text,
                        "size": "xl",
                        "weight": "bold",
                        "color": color,
                        "align": "center",
                        "margin": "md"
                    },
                    {
                        "type": "text",
                        "text": f"🕒 有效至：今日 {expire_time}",
                        "size": "sm",
                        "color": "#999999",
                        "align": "center"
                    }
                ]
            }
        }
    )
