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
        "請正確回答並提供下面的資料快速配合驗證。\n\n"
        "⭐️ 手機號碼（打在上方）\n"
        "⭐️ LINE ID（打在下方）\n\n"
        "需符合圖片上的LINE ID 以及手機號碼 未顯示無法驗證"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    try:
        user_id = event.source.user_id
        user_text = event.message.text.strip()

        try:
            profile = line_bot_api.get_profile(user_id)
            display_name = profile.display_name
        except:
            display_name = "未命名"

        # 黑名單檢查
        black = Blacklist.query.filter_by(phone=user_text).first()
        if black:
            return  # 黑名單直接忽略

        # 輸入手機號碼
        if re.match(r"^09\d{8}$", user_text):
            phone = user_text
            w = Whitelist.query.filter_by(phone=phone).first()
            if w:
                created_time = w.created_at.strftime('%Y/%m/%d %H:%M:%S') if w.created_at else "未知時間"
                reply = (
                    f"📱 {w.phone}\n"
                    f"🧸 暱稱：{w.name or display_name}\n"
                    f"🔗 LINE ID：{w.line_id or '尚未填寫'}\n"
                    f"🕒 時間：{created_time}\n"
                    f"✅ 驗證成功，歡迎加入茗殿"
                )
            else:
                new_white = Whitelist(
                    phone=phone,
                    date=datetime.now().strftime("%Y-%m-%d"),
                    reason="首次驗證",
                    name=display_name
                )
                db.session.add(new_white)
                db.session.commit()
                reply = "📱 手機已登記！請接著輸入您的 LINE ID～"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        # 非手機號碼，視為 LINE ID 補充
        latest = (
            Whitelist.query
            .filter_by(name=display_name)
            .filter(Whitelist.line_id == None)
            .order_by(Whitelist.created_at.desc())
            .first()
        )
        if latest:
            latest.line_id = user_text
            db.session.commit()
            reply = (
                f"📱 {latest.phone}\n"
                f"🧸 暱稱：{latest.name or display_name}\n"
                f"🔗 LINE ID：{latest.line_id}\n"
                f"🕒 {latest.created_at.strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

    except Exception as e:
        traceback.print_exc()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❗ 發生錯誤，請稍後再試"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
