from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.exceptions import InvalidSignatureError

from flask_sqlalchemy import SQLAlchemy
import os
import re

app = Flask(__name__)

# LINE BOT 設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 資料庫設定 (SQLite)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# 使用者模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    line_user_id = db.Column(db.String(255), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)

# 初始化資料庫（第一次運行用）
with app.app_context():
    db.create_all()

@app.route("/")
def home():
    return "LINE BOT 正在運行中 🍬"

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

    # 判斷是否為手機號碼（簡單檢查）
    if re.match(r"^09\d{8}$", user_text):
        existing_user = User.query.filter_by(line_user_id=user_id).first()
        if existing_user:
            reply = "你已經驗證過囉～💖\n手機號碼：" + existing_user.phone_number
        else:
            new_user = User(line_user_id=user_id, phone_number=user_text)
            db.session.add(new_user)
            db.session.commit()
            reply = f"手機號碼 {user_text} 驗證成功囉～🎉"
    else:
        reply = "請輸入有效的手機號碼唷（格式：09XXXXXXXX）📱"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply)
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
