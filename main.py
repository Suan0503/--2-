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
                    {"type": "text", "text": "📅 每日抽獎結果", "weight": "bold", "size": "lg"},
                    {"type": "text", "text": f"用戶：{display_name}", "size": "sm", "color": "#888888"},
                    {"type": "text", "text": f"日期：{today_str}", "size": "sm", "color": "#888888"},
                    {"type": "separator"},
                    {"type": "text", "text": text, "size": "xl", "weight": "bold", "color": color, "align": "center", "margin": "md"},
                    {"type": "text", "text": f"🕒 有效至：今日 {expire_time}", "size": "sm", "color": "#999999", "align": "center"}
                ]
            }
        }
    )

def choose_link():
    import hashlib
    group = [
        "https://line.me/ti/p/g7TPO_lhAL",
        "https://line.me/ti/p/Q6-jrvhXbH",
        "https://line.me/ti/p/AKRUvSCLRC"
    ]
    return group[hash(os.urandom(8)) % len(group)]

def get_function_menu_flex():
    now = datetime.now(timezone("Asia/Taipei"))
    today_str = now.strftime("📅 %m/%d")
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

@app.route("/")
def home():
    return "LINE Bot 正常運作中～🍵"

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        print("❗ callback 發生例外：", e)
        traceback.print_exc()
        abort(500)
    return "OK"

@handler.add(FollowEvent)
def handle_follow(event):
    msg = ("歡迎加入🍵茗殿🍵\n請輸入手機號碼進行驗證（含09開頭）")
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    tz = pytz.timezone("Asia/Taipei")
    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name

    if user_text == "每日抽獎":
        today_str = datetime.now(tz).strftime("%Y-%m-%d")
        if has_drawn_today(user_id, Coupon):
            coupon = Coupon.query.filter_by(line_user_id=user_id, date=today_str).first()
            flex = get_today_coupon_flex(user_id, display_name, coupon.amount)
            line_bot_api.reply_message(event.reply_token, flex)
            return
        amount = draw_coupon()
        save_coupon_record(user_id, amount, Coupon, db)
        flex = get_today_coupon_flex(user_id, display_name, amount)
        line_bot_api.reply_message(event.reply_token, flex)
        return

    if user_text == "驗證資訊":
        existing = Whitelist.query.filter_by(line_user_id=user_id).first()
        if existing:
            reply = (
                f"📱 {existing.phone}\n"
                f"🌸 暱稱：{existing.name or display_name}\n"
                f"個人編號：{existing.id}\n"
                f"🔗 LINE ID：{existing.line_id or '未登記'}\n"
                f"🕒 {existing.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿"
            )
            line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply), get_function_menu_flex()])
            return
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 尚未驗證，請輸入手機號碼開始驗證流程"))
            return

    existing = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 你已驗證完成，請輸入手機號碼查看驗證資訊"))
        return

    if re.match(r"^09\d{8}$", user_text):
        black = Blacklist.query.filter_by(phone=user_text).first()
        if black:
            return
        repeated = Whitelist.query.filter_by(phone=user_text).first()
        if repeated and repeated.line_user_id:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 此手機號碼已被使用，請輸入正確的手機號碼"))
            return
        temp_users[user_id] = {"phone": user_text, "name": display_name}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📱 手機已登記，請接著輸入您的 LINE ID～"))
        return

    if user_id in temp_users and len(user_text) >= 4:
        record = temp_users[user_id]
        record["line_id"] = user_text
        temp_users[user_id] = record
        reply = (
            f"📱 {record['phone']}\n"
            f"🌸 暱稱：{record['name']}\n"
            f"個人編號：待驗證後產生\n"
            f"🔗 LINE ID：{record['line_id']}\n"
            f"請問以上資料是否正確？正確請回復 1"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if user_text == "1" and user_id in temp_users:
        data = temp_users[user_id]
        now = datetime.now(tz)
        existing_record = Whitelist.query.filter_by(phone=data["phone"]).first()
        if existing_record:
            existing_record.line_user_id = user_id
            existing_record.line_id = data["line_id"]
            existing_record.name = data["name"]
            db.session.commit()
            saved_id = existing_record.id
            created_time = existing_record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')
        else:
            new_user = Whitelist(
                phone=data["phone"],
                name=data["name"],
                line_id=data["line_id"],
                date=now.strftime("%Y-%m-%d"),
                created_at=now,
                line_user_id=user_id
            )
            db.session.add(new_user)
            db.session.commit()
            saved_id = new_user.id
            created_time = now.strftime('%Y/%m/%d %H:%M:%S')
        reply = (
            f"📱 {data['phone']}\n"
            f"🌸 暱稱：{data['name']}\n"
            f"個人編號：{saved_id}\n"
            f"🔗 LINE ID：{data['line_id']}\n"
            f"🕒 {created_time}\n"
            f"✅ 驗證成功，歡迎加入茗殿"
        )
        line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply), get_function_menu_flex()])
        temp_users.pop(user_id)
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
