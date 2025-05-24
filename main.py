from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
from dotenv import load_dotenv
import os
import re

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 讀取 .env 環境變數
load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# LINE 設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 管理員列表（改成自己的 LINE ID）
ADMINS = ["U你的LINEID"]

# 資料表
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
    phone = db.Column(db.String(20))
    reason = db.Column(db.Text)

with app.app_context():
    db.create_all()

# Google Sheet 備份
def append_to_sheet(phone_number, line_user_id, status, verified_at):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("你的 Google Sheet ID").sheet1
    sheet.append_row([phone_number, line_user_id, status, str(verified_at)])

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

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    if user_text == "查詢":
        user = User.query.filter_by(line_user_id=user_id).first()
        if user:
            reply = f"✅ 你已驗證：{user.phone_number}\n狀態：{user.status}"
        else:
            reply = "你還沒驗證手機喔～🥺"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 管理員指令
    if user_id in ADMINS:
        if user_text.startswith("/查 "):
            number = user_text[3:].strip()
            user = User.query.filter_by(phone_number=number).first()
            reply = f"{number} 狀態：{user.status}, ID: {user.line_user_id}" if user else f"{number} 尚未驗證"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        elif user_text.startswith("/封鎖 "):
            number = user_text[4:].strip()
            user = User.query.filter_by(phone_number=number).first()
            if user:
                user.status = "black"
                db.session.commit()
                reply = f"{number} 已加入黑名單 ❌"
            else:
                reply = f"{number} 尚未註冊"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        elif user_text.startswith("/解鎖 "):
            number = user_text[4:].strip()
            user = User.query.filter_by(phone_number=number).first()
            if user:
                user.status = "white"
                user.verified_at = datetime.now()
                db.session.commit()
                reply = f"{number} 已解除封鎖 ✅"
            else:
                reply = f"{number} 尚未註冊"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        elif user_text.startswith("/重設 "):
            number = user_text[4:].strip()
            user = User.query.filter_by(phone_number=number).first()
            if user:
                db.session.delete(user)
                db.session.commit()
                reply = f"{number} 已刪除資料 🗑"
            else:
                reply = f"{number} 不存在"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        elif user_text.startswith("/拉黑 "):
            parts = user_text.split(" ", 2)
            if len(parts) < 3:
                reply = "格式錯誤！請使用：/拉黑 手機號 原因"
            else:
                phone, reason = parts[1], parts[2]
                db.session.add(Blacklist(
                    date=datetime.now().strftime("%Y-%m-%d"),
                    phone=phone,
                    reason=reason
                ))
                db.session.commit()
                reply = f"{phone} 已加入黑名單\n理由：{reason}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        elif user_text.startswith("/白單 "):
            parts = user_text.split(" ", 2)
            if len(parts) < 3:
                reply = "格式錯誤！請使用：/白單 手機號 原因"
            else:
                phone, reason = parts[1], parts[2]
                db.session.add(Whitelist(
                    date=datetime.now().strftime("%Y-%m-%d"),
                    phone=phone,
                    reason=reason
                ))
                db.session.commit()
                reply = f"{phone} 已加入白名單\n理由：{reason}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        elif user_text.startswith("/查單 "):
            phone = user_text.split(" ", 1)[1]
            b = Blacklist.query.filter_by(phone=phone).first()
            w = Whitelist.query.filter_by(phone=phone).first()
            if b:
                reply = f"🔴 黑名單\n日期：{b.date}\n理由：{b.reason}"
            elif w:
                reply = f"🟢 白名單\n日期：{w.date}\n理由：{w.reason}"
            else:
                reply = f"{phone} 不在任何名單中"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

    # 使用者驗證手機
    if re.match(r"^09\d{8}$", user_text):
        existing = User.query.filter_by(phone_number=user_text).first()
        if existing:
            if existing.status == "black":
                return
            elif existing.status == "white":
                reply = f"你已驗證過囉～📱 {existing.phone_number}"
            else:
                existing.status = "white"
                existing.verified_at = datetime.now()
                db.session.commit()
                reply = f"驗證成功！{user_text} 已加入白名單 🎉"
        else:
            user = User(
                line_user_id=user_id,
                phone_number=user_text,
                status="white",
                verified_at=datetime.now()
            )
            db.session.add(user)
            db.session.commit()
            append_to_sheet(user_text, user_id, "white", user.verified_at)
            reply = f"驗證成功！{user_text} 已加入白名單 🎉"
    else:
        reply = "請輸入正確格式手機號碼（例如：09XXXXXXXX）📱"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
