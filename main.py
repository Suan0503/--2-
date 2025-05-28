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

temp_users = {}  # 暫存記憶資料結構

class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    name = db.Column(db.String(255))
    line_id = db.Column(db.String(100))
    line_user_id = db.Column(db.String(255), unique=True, nullable=True)

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

    existing_user = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing_user:
        if user_text == existing_user.phone:
            reply = (
                f"📱 {existing_user.phone}\n"
                f"🧸 暱稱：{existing_user.name or display_name}\n"
                f"       個人編號：\n"
                f"🔗 LINE ID：{existing_user.line_id or '未登記'}\n"
                f"🕒 {existing_user.created_at.strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿"
            )
        else:
            reply = "⚠️ 你已驗證完成，請輸入手機號碼查看驗證資訊"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if re.match(r"^09\d{8}$", user_text):
        black = Blacklist.query.filter_by(phone=user_text).first()
        if black:
            return

        white = Whitelist.query.filter_by(phone=user_text).first()
        if white:
            if white.line_user_id:
                reply = "⚠️ 此手機號碼已被使用，請輸入正確的手機號碼"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
                return
            else:
                temp_users[user_id] = {"phone": user_text, "name": display_name, "existing": white}
                reply = "📱 手機已登記，請接著輸入您的 LINE ID～"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
                return
        else:
            temp_users[user_id] = {"phone": user_text, "name": display_name, "existing": None}
            reply = "📱 手機已登記，請接著輸入您的 LINE ID～"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

    if user_id in temp_users and len(user_text) >= 4:
        temp_users[user_id]["line_id"] = user_text
        r = temp_users[user_id]
        reply = (
            f"📱 {r['phone']}\n"
            f"🧸 暱稱：{r['name']}\n"
            f"       個人編號：\n"
            f"🔗 LINE ID：{r['line_id']}\n"
            f"請問以上資料是否正確？正確請回復 1"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if user_text == "1" and user_id in temp_users:
        r = temp_users[user_id]
        if r["existing"]:
            r["existing"].line_id = r["line_id"]
            r["existing"].line_user_id = user_id
            db.session.commit()
            result = r["existing"]
        else:
            result = Whitelist(
                phone=r["phone"],
                name=r["name"],
                line_id=r["line_id"],
                line_user_id=user_id,
                date=datetime.now().strftime("%Y-%m-%d")
            )
            db.session.add(result)
            db.session.commit()

        reply = (
            f"📱 {result.phone}\n"
            f"🧸 暱稱：{result.name}\n"
            f"       個人編號：\n"
            f"🔗 LINE ID：{result.line_id}\n"
            f"🕒 {result.created_at.strftime('%Y/%m/%d %H:%M:%S')}\n"
            f"✅ 驗證成功，歡迎加入茗殿"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        temp_users.pop(user_id)
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
