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

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    line_user_id = db.Column(db.String(255), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(10), nullable=False, default='pending')
    verified_at = db.Column(db.DateTime, nullable=True)

class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    reason = db.Column(db.Text)

class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    名稱 = db.Column(db.String(255))  # LINE 顯示名稱

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
    welcome = "🎉 歡迎加入！\n請輸入手機號碼（09開頭）進行驗證📱"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name

    if re.match(r"^09\d{8}$", user_text):
        phone = user_text

        # 黑名單檢查
        black = Blacklist.query.filter_by(phone=phone).first()
        if black:
            reply = f"❌ 此號碼已被封鎖\n📵 理由：{black.reason}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        # 白名單檢查
        white = Whitelist.query.filter_by(phone=phone).first()
        existing_user = User.query.filter_by(line_user_id=user_id).first()

        if white:
            if existing_user:
                reply = f"✅ 你已驗證：{existing_user.phone_number}\n🕒 驗證時間：{existing_user.verified_at.strftime('%Y/%m/%d %H:%M:%S')}"
            else:
                new_user = User(
                    line_user_id=user_id,
                    phone_number=phone,
                    status="white",
                    verified_at=datetime.now()
                )
                db.session.add(new_user)
                db.session.commit()
                reply = f"✅ 驗證成功！\n📱 {phone}\n🕒 {new_user.verified_at.strftime('%Y/%m/%d %H:%M:%S')}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        # 若不在白名單 → 自動新增進白名單與使用者表
        new_white = Whitelist(
            date=datetime.now().strftime("%Y-%m-%d"),
            phone=phone,
            reason="自動加入",
            名稱=display_name
        )
        db.session.add(new_white)

        new_user = User(
            line_user_id=user_id,
            phone_number=phone,
            status="white",
            verified_at=datetime.now()
        )
        db.session.add(new_user)
        db.session.commit()

        reply = f"✅ 驗證成功！\n📱 {phone}\n🧸 暱稱：{display_name}\n🕒 {new_user.verified_at.strftime('%Y/%m/%d %H:%M:%S')}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
