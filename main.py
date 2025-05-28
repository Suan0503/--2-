# 修正後 main.py（已驗證用戶不可再登記，輸入自己手機可查詢資訊）

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

ADMINS = ["U8f3cc921a9dd18d3e257008a34dd07c1"]
admin_mode = set()

class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    name = db.Column(db.String(255))
    line_id = db.Column(db.String(100))
    line_user_id = db.Column(db.String(255), unique=True)

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
        "➡️ \033[1m請輸入手機號碼進行驗證（含09開頭）\033[0m"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name

    # 已驗證的使用者
    existing = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing:
        if user_text == existing.phone:
            reply = (
                f"\ud83d\udcf1 {existing.phone}\n"
                f"\ud83c\udf38 暱稱：{existing.name or display_name}\n"
                f"       個人編號：\n"
                f"\ud83d\udd17 LINE ID：{existing.line_id or '未登記'}\n"
                f"\ud83d\udd52 {existing.created_at.strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"\u2705 驗證成功，歡迎加入茗殿"
            )
        else:
            reply = "\u26a0\ufe0f 你已驗證完成，請輸入手機號碼查看驗證資訊"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 黑名單封鎖
    if re.match(r"^09\\d{8}$", user_text):
        black = Blacklist.query.filter_by(phone=user_text).first()
        if black:
            return

        # 若手機已被使用
        repeated = Whitelist.query.filter_by(phone=user_text).first()
        if repeated:
            reply = "\u26a0\ufe0f 此手機號碼已被使用，請輸入正確的手機號碼"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        # 尚未登記，等待輸入 LINE ID
        temp_users[user_id] = {"phone": user_text, "name": display_name}
        reply = "\ud83d\udcf1 手機已登記，請接著輸入您的 LINE ID～"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 使用者輸入 LINE ID
    if user_id in temp_users and len(user_text) >= 4:
        record = temp_users[user_id]
        record["line_id"] = user_text
        temp_users[user_id] = record

        reply = (
            f"\ud83d\udcf1 {record['phone']}\n"
            f"\ud83c\udf38 暱稱：{record['name']}\n"
            f"       個人編號：\n"
            f"\ud83d\udd17 LINE ID：{record['line_id']}\n"
            f"請問以上資料是否正確？正確請回復 1"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 確認後存入資料庫
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
            f"\ud83d\udcf1 {new_user.phone}\n"
            f"\ud83c\udf38 暱稱：{new_user.name}\n"
            f"       個人編號：\n"
            f"\ud83d\udd17 LINE ID：{new_user.line_id}\n"
            f"\ud83d\udd52 {new_user.created_at.strftime('%Y/%m/%d %H:%M:%S')}\n"
            f"\u2705 驗證成功，歡迎加入茗殿"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        temp_users.pop(user_id)
        return

# 暫存記憶資料結構
# line_user_id => { phone, name, line_id }
temp_users = {}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
