from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
from dotenv import load_dotenv
import os
import re

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
admin_mode_users = set()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    line_user_id = db.Column(db.String(255), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(10), nullable=False, default='pending')
    verified_at = db.Column(db.DateTime, nullable=True)
    nickname = db.Column(db.String(100), nullable=True)

class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)

class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)

with app.app_context():
    db.create_all()

@app.route("/")
def home():
    return "LINE Bot 正常運作中～🍓"

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(FollowEvent)
def handle_follow(event):
    welcome = (
        "歡迎加入🍵茗殿🍵\n\n"
        "請正確回答並提供下面的資料快速配合驗證。\n\n"
        "⭐️ 手機號碼（請打在最上方）\n"
        "⭐️ LINE ID（請打在下方）\n"
        "⭐️ line主頁>右上角設定>個人檔案（點進去之後截圖回傳）\n\n"
        "需符合圖片上的LINE ID 以及手機號碼，未顯示無法驗證"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    # 管理員模式開關
    if user_text == "/管理員 ON":
        if user_id in ADMINS:
            admin_mode_users.add(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🛠️ 已進入管理員模式"))
        return

    if user_text == "/管理員 OFF":
        if user_id in admin_mode_users:
            admin_mode_users.remove(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 已退出管理員模式"))
        return

    # 管理員指令區（未來可擴充）

    # ✅ 手機驗證區段
    if re.match(r"^09\d{8}$", user_text):
        # 黑名單擋下，不回應
        if Blacklist.query.filter_by(phone=user_text).first():
            return

        # 驗證過程
        existing_by_id = User.query.filter_by(line_user_id=user_id).first()
        existing_by_phone = User.query.filter_by(phone_number=user_text).first()

        # 綁定保護
        if existing_by_phone and existing_by_phone.line_user_id != user_id:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 此號碼已由其他帳號驗證過，無法重複綁定 ❌"))
            return

        if existing_by_id:
            if existing_by_id.status == "white":
                vtime = existing_by_id.verified_at.strftime("%Y/%m/%d %H:%M")
                reply = f"📱 {existing_by_id.phone_number}\n✅ 已經驗證完成！\n🕒 時間：{vtime}"
            else:
                existing_by_id.phone_number = user_text
                existing_by_id.status = "white"
                existing_by_id.verified_at = datetime.now()
                if not existing_by_id.nickname:
                    profile = line_bot_api.get_profile(user_id)
                    existing_by_id.nickname = profile.display_name
                db.session.commit()
                vtime = existing_by_id.verified_at.strftime("%Y/%m/%d %H:%M")
                reply = f"✅ 驗證成功！\n📱 {user_text}\n🕒 時間：{vtime}"
        else:
            profile = line_bot_api.get_profile(user_id)
            new_user = User(
                line_user_id=user_id,
                phone_number=user_text,
                status="white",
                verified_at=datetime.now(),
                nickname=profile.display_name
            )
            db.session.add(new_user)
            db.session.commit()
            vtime = new_user.verified_at.strftime("%Y/%m/%d %H:%M")
            reply = f"✅ 驗證成功！\n📱 {user_text}\n🕒 時間：{vtime}"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
