from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, FollowEvent
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
from dotenv import load_dotenv
import os
import re
import traceback
import pytz
import random
from pytz import timezone

load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

temp_users = {}

class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    name = db.Column(db.String(255))
    line_id = db.Column(db.String(100))
    line_user_id = db.Column(db.String(255), unique=True)

class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    name = db.Column(db.String(255))

class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    line_user_id = db.Column(db.String(255))
    date = db.Column(db.String(20))
    amount = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

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
    expire_time = "23:59"
    if amount == 0:
        text = "很可惜沒中獎呢～明天再試試看吧\U0001F319"
        color = "#999999"
    else:
        text = f"\U0001F381 恭喜你抽中 {amount} 元折價券"
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
                    {"type": "text", "text": "\U0001F4C5 每日抽獎結果", "weight": "bold", "size": "lg"},
                    {"type": "text", "text": f"用戶：{display_name}", "size": "sm", "color": "#888888"},
                    {"type": "text", "text": f"日期：{today_str}", "size": "sm", "color": "#888888"},
                    {"type": "separator"},
                    {"type": "text", "text": text, "size": "xl", "weight": "bold", "color": color, "align": "center", "margin": "md"},
                    {"type": "text", "text": f"\U0001F552 有效至：今日 {expire_time}", "size": "sm", "color": "#999999", "align": "center"}
                ]
            }
        }
    )

def choose_link():
    group = [
        "https://line.me/ti/p/g7TPO_lhAL",
        "https://line.me/ti/p/Q6-jrvhXbH",
        "https://line.me/ti/p/AKRUvSCLRC"
    ]
    return group[hash(os.urandom(8)) % len(group)]

def get_function_menu_flex():
    now = datetime.now(timezone("Asia/Taipei"))
    today_str = now.strftime("\U0001F4C5 %m/%d")
    return FlexSendMessage(
        alt_text="功能選單",
        contents={
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": today_str, "size": "md", "color": "#AAAAAA", "align": "end"}
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": "✨ 功能選單 ✨", "weight": "bold", "size": "lg", "align": "center"},
                    {"type": "separator"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "lg",
                        "spacing": "sm",
                        "contents": [
                            {"type": "button", "action": {"type": "message", "label": "📱 驗證資訊", "text": "驗證資訊"}, "style": "primary", "color": "#00C37E"},
                            {"type": "button", "action": {"type": "uri", "label": "📅 每日班表", "uri": "https://t.me/+XgwLCJ6kdhhhZDE1"}, "style": "link"},
                            {"type": "button", "action": {"type": "message", "label": "🎁 每日抽獎", "text": "每日抽獎"}, "style": "primary", "color": "#FF9900"},
                            {"type": "button", "action": {"type": "uri", "label": "📬 預約諮詢", "uri": choose_link()}, "style": "primary", "color": "#B889F2"}
                        ]
                    }
                ]
            }
        }
    )
