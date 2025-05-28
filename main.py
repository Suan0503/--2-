from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
from dotenv import load_dotenv
import os
import re
import traceback

load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    name = db.Column(db.String(255))

class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    line_id = db.Column(db.String(50))
    reason = db.Column(db.Text)
    name = db.Column(db.String(255))

with app.app_context():
    db.create_all()

pending_verification = {}  # user_id: (phone, line_id, name)

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
        "歡迎加入🍵茗殿🍵\n\n"
        "請正確按照步驟提供資料配合快速驗證\n\n"
        "➡️ **請輸入手機號碼進行驗證（含09開頭）**"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_id = event.source.user_id
        user_text = event.message.text.strip()
        profile = line_bot_api.get_profile(user_id)
        display_name = profile.display_name

        # 黑名單直接忽略
        if re.match(r"^09\d{8}$", user_text):
            phone = user_text
            if Blacklist.query.filter_by(phone=phone).first():
                return

            if Whitelist.query.filter_by(phone=phone).first():
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="此手機號碼已被使用 請輸入正確的手機號碼"))
                return

            pending_verification[user_id] = {"phone": phone, "line_id": None, "name": display_name}
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📱 手機已登記，請接著輸入您的 LINE ID～"))
            return

        # 接收 LINE ID
        if user_id in pending_verification and not pending_verification[user_id].get("line_id"):
            pending_verification[user_id]["line_id"] = user_text
            phone = pending_verification[user_id]["phone"]
            name = pending_verification[user_id]["name"]
            reply = (
                f"📱 {phone}\n"
                f"🧸 暱稱：{name}\n"
                f"🔗 LINE ID：{user_text}\n"
                f"請問以上資料是否正確？\n正確請回覆 1"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        # 確認輸入 1
        if user_text == "1" and user_id in pending_verification:
            data = pending_verification.pop(user_id)
            new_white = Whitelist(
                date=datetime.now().strftime("%Y-%m-%d"),
                phone=data["phone"],
                line_id=data["line_id"],
                reason="驗證完成",
                name=data["name"]
            )
            db.session.add(new_white)
            db.session.commit()
            reply = (
                f"📱 {new_white.phone}\n"
                f"🧸 暱稱：{new_white.name}\n"
                f"       個人編號：\n"
                f"🔗 LINE ID：{new_white.line_id}\n"
                f"🕒 {new_white.created_at.strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

    except Exception as e:
        traceback.print_exc()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❗ 發生錯誤，請稍後再試"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
