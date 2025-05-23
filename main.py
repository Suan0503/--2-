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

# 載入 .env 環境變數
load_dotenv()

# Flask app 初始化
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# LINE 機器人金鑰
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 管理員 LINE ID 列表（請替換）
ADMINS = ["U你的LINEID"]  # <--- 請換成妳的 LINE 使用者 ID

# 資料表模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    line_user_id = db.Column(db.String(255), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(10), nullable=False, default='pending')  # white / black / pending
    verified_at = db.Column(db.DateTime, nullable=True)

with app.app_context():
    db.create_all()

# Google Sheets 備份函式（需替換 Sheet ID）
def append_to_sheet(phone_number, line_user_id, status, verified_at):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("你的 Google Sheet ID").sheet1  # <--- 請替換
    sheet.append_row([phone_number, line_user_id, status, str(verified_at)])

# 主頁測試
@app.route("/")
def home():
    return "LINE 機器人正在運行 🐣"

# LINE 回呼
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# 處理訊息事件
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    # 使用者查詢自己
    if user_text == "查詢":
        user = User.query.filter_by(line_user_id=user_id).first()
        if user:
            reply = f"✅ 你已驗證：{user.phone_number}\n狀態：{user.status}"
        else:
            reply = "你還沒有驗證手機唷～🥺"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 管理員指令區
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
                reply = f"{number} 資料已刪除 🗑"
            else:
                reply = f"{number} 不存在"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

    # 一般用戶驗證手機
    if re.match(r"^09\d{8}$", user_text):
        existing = User.query.filter_by(phone_number=user_text).first()
        if existing:
            if existing.status == "black":
                return  # 黑名單不回應
            elif existing.status == "white":
                reply = f"你已經驗證過囉～📱 {existing.phone_number}"
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

# 入口點
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
