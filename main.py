from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent, FlexSendMessage, URIAction
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
from dotenv import load_dotenv
import os
import re
import traceback
import pytz
import random

print("🟢 啟動 main.py")

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
temp_users = {}  # 暫存用戶資料

GROUP_URLS = [
    "https://line.me/ti/p/g7TPO_lhAL",
    "https://line.me/ti/p/Q6-jrvhXbH",
    "https://line.me/ti/p/AKRUvSCLRC"
]

class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    name = db.Column(db.String(255))
    line_id = db.Column(db.String(100))
    line_user_id = db.Column(db.String(255), unique=True)

class Referral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    line_user_id = db.Column(db.String(255), unique=True)
    assigned_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def get_user_group_url(user_id):
    existing = Referral.query.filter_by(line_user_id=user_id).first()
    if existing:
        return existing.assigned_url
    else:
        url = random.choice(GROUP_URLS)
        new_entry = Referral(line_user_id=user_id, assigned_url=url)
        db.session.add(new_entry)
        db.session.commit()
        return url

@app.route("/")
def home():
    return "LINE Bot 運作中～🍵"

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
    msg = "歡迎加入🍵茗殿🍵\n請輸入手機號碼進行驗證（含09開頭）"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    print(f"[INPUT] {user_id}：{user_text}")

    tz = pytz.timezone("Asia/Taipei")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name

    existing = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing:
        if user_text == existing.phone:
            reply = (
                f"📱 {existing.phone}\n"
                f"🌸 暱稱：{existing.name or display_name}\n"
                f"       個人編號：{existing.id}\n"
                f"🔗 LINE ID：{existing.line_id or '無資料'}\n"
                f"⏰ 驗證時間：{existing.created_at.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S')}"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return
        else:
            send_function_menu(user_id)
            return

    if re.match(r"^09\\d{8}$", user_text):
        temp_users[user_id] = {"phone": user_text, "name": display_name, "line_id": ""}
        reply = "請輸入您的 LINE ID（不含@）"
    elif user_id in temp_users and not temp_users[user_id]["line_id"]:
        temp_users[user_id]["line_id"] = user_text
        data = temp_users[user_id]
        new = Whitelist(
            phone=data["phone"], name=data["name"], line_id=data["line_id"],
            date=now, line_user_id=user_id
        )
        db.session.add(new)
        db.session.commit()
        temp_users.pop(user_id, None)
        reply = "✅ 驗證完成！以下是功能選單："
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        send_function_menu(user_id)
        return
    else:
        reply = "請輸入正確手機號碼（09開頭）開始驗證流程～"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

def send_function_menu(user_id):
    group_url = get_user_group_url(user_id)
    bubble = {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🌟 功能選單", "weight": "bold", "size": "xl", "align": "center"},
                {"type": "separator", "margin": "md"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "spacing": "sm",
                    "contents": [
                        {"type": "button", "style": "primary", "action": {"type": "message", "label": "驗證資訊", "text": "驗證資訊"}},
                        {"type": "button", "style": "primary", "action": {"type": "message", "label": "每日班表", "text": "每日班表"}},
                        {"type": "button", "style": "primary", "action": {"type": "message", "label": "新品上架", "text": "新品上架"}},
                        {"type": "button", "style": "primary", "action": {"type": "uri", "label": "預約諮詢", "uri": group_url}},
                    ]
                }
            ]
        }
    }
    line_bot_api.push_message(user_id, FlexSendMessage(alt_text="功能選單", contents=bubble))
