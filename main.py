from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent, FlexSendMessage
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
from dotenv import load_dotenv
import os
import re
import traceback
import pytz
import random

load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

ADMINS = ["U8f3cc921a9dd18d3e257008a34dd07c1"]
temp_users = {}  # line_user_id => { phone, name, line_id }
redirect_links = {
    "a": "https://line.me/ti/p/g7TPO_lhAL",
    "b": "https://line.me/ti/p/Q6-jrvhXbH",
    "c": "https://line.me/ti/p/AKRUvSCLRC"
}
assigned_redirect = {}  # line_user_id => one of a/b/c

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
    msg = (
        "歡迎加入🍵茗殿🍵\n"
        "請正確按照步驟提供資料配合快速驗證\n\n"
        "➡️ 請輸入手機號碼進行驗證（含09開頭）"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    tz = pytz.timezone("Asia/Taipei")
    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name

    existing = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing:
        if user_text == existing.phone:
            reply = (
                f"📱 {existing.phone}\n"
                f"🌸 暱稱：{existing.name or display_name}\n"
                f"       個人編號：{existing.id}\n"
                f"🔗 LINE ID：{existing.line_id or '未登記'}\n"
                f"🕒 {existing.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            push_flex_menu(user_id)
        else:
            reply = "⚠️ 你已驗證完成，請輸入手機號碼查看驗證資訊"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if re.match(r"^09\d{8}$", user_text):
        black = Blacklist.query.filter_by(phone=user_text).first()
        if black:
            return
        repeated = Whitelist.query.filter_by(phone=user_text).first()
        if repeated and repeated.line_user_id:
            reply = "⚠️ 此手機號碼已被使用，請輸入正確的手機號碼"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        temp_users[user_id] = {"phone": user_text, "name": display_name}
        reply = "📱 手機已登記，請接著輸入您的 LINE ID～"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if user_id in temp_users and len(user_text) >= 4:
        record = temp_users[user_id]
        record["line_id"] = user_text
        temp_users[user_id] = record

        reply = (
            f"📱 {record['phone']}\n"
            f"🌸 暱稱：{record['name']}\n"
            f"       個人編號：待驗證後產生\n"
            f"🔗 LINE ID：{record['line_id']}\n"
            f"請問以上資料是否正確？資料一經送出無法修改，如正確請回復 1"
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
            f"       個人編號：{saved_id}\n"
            f"🔗 LINE ID：{data['line_id']}\n"
            f"🕒 {created_time}\n"
            f"✅ 驗證成功，歡迎加入茗殿"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        temp_users.pop(user_id)
        push_flex_menu(user_id)
        return

def push_flex_menu(user_id):
    if user_id not in assigned_redirect:
        assigned_redirect[user_id] = random.choice(["a", "b", "c"])
    consult_url = redirect_links[assigned_redirect[user_id]]

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "✅ 功能選單", "weight": "bold", "size": "lg", "margin": "md"},
                {"type": "separator", "margin": "md"},
                {
                    "type": "button",
                    "action": {"type": "message", "label": "驗證資訊", "text": "驗證資訊"},
                    "style": "primary",
                    "margin": "md"
                },
                {
                    "type": "button",
                    "action": {"type": "uri", "label": "每日班表", "uri": "https://line.me/ti/p/@linebot"},
                    "style": "primary",
                    "margin": "md"
                },
                {
                    "type": "button",
                    "action": {"type": "uri", "label": "新品上架", "uri": "https://line.me/ti/p/@linebot"},
                    "style": "primary",
                    "margin": "md"
                },
                {
                    "type": "button",
                    "action": {"type": "uri", "label": "預約諮詢", "uri": consult_url},
                    "style": "primary",
                    "margin": "md"
                }
            ]
        }
    }
    line_bot_api.push_message(user_id, FlexSendMessage(alt_text="功能選單", contents=bubble))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
