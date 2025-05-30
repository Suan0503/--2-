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
import pytz

print("\U0001F7E2 進入 main.py 開始啟動 Flask")

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
    name = db.Column(db.String(255))
    line_id = db.Column(db.String(100))
    line_user_id = db.Column(db.String(255), unique=True)

@app.route("/")
def home():
    return "LINE Bot 正常運作中～\U0001F375"

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
        "歡迎加入\U0001F375茗殿\U0001F375\n"
        "請正確按照步驟提供資料配合快速驗證\n\n"
        "➡️ 請輸入手機號碼進行驗證（含09開頭）"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    tz = pytz.timezone("Asia/Taipei")
    now = datetime.now(tz)
    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name

    existing = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing:
        if user_text == existing.phone:
            reply = (
                f"\U0001F4F1 {existing.phone}\n"
                f"\U0001F338 暱稱：{existing.name or display_name}\n"
                f"       個人編號：{existing.id}\n"
                f"\U0001F517 LINE ID：{existing.line_id or '無資料'}\n"
                f"⏰ 驗證時間：{existing.created_at.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            reply = "✅ 你已完成驗證，不需再次輸入。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if re.match(r"^09\d{8}$", user_text):
        temp_users[user_id] = {"phone": user_text, "name": display_name, "line_id": ""}
        reply = "請輸入您的 LINE ID（不含@）"

    elif user_id in temp_users and not temp_users[user_id]["line_id"]:
        temp_users[user_id]["line_id"] = user_text
        data = temp_users[user_id]
        reply = (
            f"\U0001F4F1 {data['phone']}\n"
            f"\U0001F338 暱稱：{data['name']}\n"
            f"       個人編號：待驗證後產生\n"
            f"\U0001F517 LINE ID：{data['line_id']}\n"
            f"請確認資料正確，若正確請回覆 1 完成驗證"
        )

    elif user_text == "1" and user_id in temp_users:
        data = temp_users[user_id]
        new = Whitelist(
            phone=data["phone"], name=data["name"], line_id=data["line_id"],
            date=now.strftime("%Y-%m-%d"), line_user_id=user_id, created_at=now
        )
        db.session.add(new)
        db.session.commit()
        reply = (
            f"\U0001F4F1 {data['phone']}\n"
            f"\U0001F338 暱稱：{data['name']}\n"
            f"       個人編號：{new.id}\n"
            f"\U0001F517 LINE ID：{data['line_id']}\n"
            f"⏰ 驗證時間：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"✅ 驗證成功，歡迎加入茗殿～"
        )
        temp_users.pop(user_id, None)
    else:
        reply = "請先輸入手機號碼（09開頭）來開始驗證流程～"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
