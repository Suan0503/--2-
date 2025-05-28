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

# 暫存使用者輸入流程資料
temp_users = {}

# 白名單資料表
class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    name = db.Column(db.String(255))
    line_id = db.Column(db.String(100))
    line_user_id = db.Column(db.String(255), unique=True)

# 黑名單資料表
class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    name = db.Column(db.String(255))

with app.app_context():
    db.create_all()

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

    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name

    # 判斷是否為已驗證用戶
    existing = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing:
        if user_text == existing.phone:
            reply = (
                f"📱 {existing.phone}\n"
                f"🧸 暱稱：{existing.name or display_name}\n"
                f"       個人編號：\n"
                f"🔗 LINE ID：{existing.line_id or '未登記'}\n"
                f"🕒 {existing.created_at.strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿"
            )
        else:
            reply = "⚠️ 你已驗證完成，請輸入手機號碼查看驗證資訊"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 使用者輸入的是手機號碼
    if re.match(r"^09\d{8}$", user_text):
        # 黑名單檢查
        if Blacklist.query.filter_by(phone=user_text).first():
            return

        # 手機已被使用
        if Whitelist.query.filter_by(phone=user_text).first():
            reply = "⚠️ 此手機號碼已被使用，請輸入正確的手機號碼"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        # 登記進暫存流程
        temp_users[user_id] = {"phone": user_text, "name": display_name}
        reply = "📱 手機已登記，請接著輸入您的 LINE ID～"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 使用者輸入 LINE ID
    if user_id in temp_users and len(user_text) >= 4:
        record = temp_users[user_id]
        record["line_id"] = user_text
        temp_users[user_id] = record
        reply = (
            f"📱 {record['phone']}\n"
            f"🧸 暱稱：{record['name']}\n"
            f"       個人編號：\n"
            f"🔗 LINE ID：{record['line_id']}\n"
            f"請問以上資料是否正確？正確請回復 1"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 確認後儲存資料
    if user_text == "1" and user_id in temp_users:
        data = temp_users[user_id]
        new_user = Whitelist(
            phone=data["phone"],
            name=data["name"],
            line_id=data["line_id"],
            date=datetime.now().strftime("%Y-%m-%d"),
            line_user_id=user_id
        )
        db.session.add(new_user)
        db.session.commit()

        reply = (
            f"📱 {new_user.phone}\n"
            f"🧸 暱稱：{new_user.name}\n"
            f"       個人編號：\n"
            f"🔗 LINE ID：{new_user.line_id}\n"
            f"🕒 {new_user.created_at.strftime('%Y/%m/%d %H:%M:%S')}\n"
            f"✅ 驗證成功，歡迎加入茗殿"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        temp_users.pop(user_id)
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
