from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
import os
import re

app = Flask(__name__)

# 環境變數
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 資料庫設定
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# 管理員 ID（可填多個）
ADMINS = ["U1234567890abcdef1234567890abcdef"]  # 換成妳自己的 user_id

# 使用者模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    line_user_id = db.Column(db.String(255), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(10), nullable=False, default='pending')  # white / black / pending
    verified_at = db.Column(db.DateTime, nullable=True)

with app.app_context():
    db.create_all()

@app.route("/")
def home():
    return "LINE Bot 正在運行 🍬"

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

    # 管理指令（只有管理員能用）
    if user_id in ADMINS:

        if user_text.startswith("/查 "):
            number = user_text[3:].strip()
            user = User.query.filter_by(phone_number=number).first()
            if not user:
                reply = f"{number} 尚未驗證"
            else:
                reply = f"{number} 狀態：{user.status}，LINE ID：{user.line_user_id}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        elif user_text.startswith("/封鎖 "):
            number = user_text[4:].strip()
            user = User.query.filter_by(phone_number=number).first()
            if not user:
                reply = f"{number} 尚未註冊，無法封鎖"
            else:
                user.status = "black"
                db.session.commit()
                reply = f"{number} 已加入黑名單 ❌"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        elif user_text.startswith("/解鎖 "):
            number = user_text[4:].strip()
            user = User.query.filter_by(phone_number=number).first()
            if not user:
                reply = f"{number} 尚未註冊"
            else:
                user.status = "white"
                user.verified_at = datetime.now()
                db.session.commit()
                reply = f"{number} 已解除封鎖 ✅"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        elif user_text.startswith("/重設 "):
            number = user_text[4:].strip()
            user = User.query.filter_by(phone_number=number).first()
            if not user:
                reply = f"{number} 不存在唷"
            else:
                db.session.delete(user)
                db.session.commit()
                reply = f"{number} 資料已刪除 🗑"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

    # 手機號碼驗證流程（非管理員也能觸發）
    if re.match(r"^09\d{8}$", user_text):
        existing = User.query.filter_by(phone_number=user_text).first()

        if existing:
            if existing.status == "black":
                return  # 黑名單靜音
            elif existing.status == "white":
                reply = f"你已在白名單囉💎\n手機號碼：{existing.phone_number}"
            else:
                existing.status = "white"
                existing.verified_at = datetime.now()
                db.session.commit()
                reply = f"驗證成功！手機號碼 {user_text} 已加入白名單 🎉"
        else:
            new_user = User(
                line_user_id=user_id,
                phone_number=user_text,
                status="white",
                verified_at=datetime.now()
            )
            db.session.add(new_user)
            db.session.commit()
            reply = f"驗證成功！手機號碼 {user_text} 已加入白名單 🎉"
    else:
        reply = "請輸入有效的手機號碼（格式：09XXXXXXXX）📱"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
