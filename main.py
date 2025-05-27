from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
from dotenv import load_dotenv
import os
import re

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

class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    名稱 = db.Column(db.String(255))  # 中文欄位要一致

class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    名稱 = db.Column(db.String(255))

with app.app_context():
    db.create_all()

@app.route("/")
def home():
    return "LINE Bot 正常運作中～🍵"

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
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
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    # 管理員模式開關
    if user_id in ADMINS:
        if user_text == "/管理員 ON":
            admin_mode.add(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 已開啟管理員模式"))
            return
        elif user_text == "/管理員 OFF":
            admin_mode.discard(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❎ 已關閉管理員模式"))
            return

    # 管理員指令操作區
    if user_id in admin_mode:
        if user_text == "/指令":
            help_msg = (
                "🔧 管理員指令：\n"
                "• /新增 電話 白名單/黑名單\n"
                "• /修改 電話\n"
                "• /黑名單 電話 (轉移白→黑)\n"
                "• 直接輸入電話查詢其資訊"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_msg))
            return

        if user_text.startswith("/新增"):
            try:
                _, phone, kind = user_text.split()
                profile = line_bot_api.get_profile(user_id)
                name = profile.display_name
                if kind == "白名單":
                    db.session.add(Whitelist(date=datetime.now().strftime("%Y-%m-%d"), phone=phone, reason="管理員新增", 名稱=name))
                elif kind == "黑名單":
                    db.session.add(Blacklist(date=datetime.now().strftime("%Y-%m-%d"), phone=phone, reason="管理員新增", 名稱=name))
                db.session.commit()
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"✅ {phone} 已新增至 {kind}"))
            except:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❗ 格式錯誤：/新增 電話 白名單/黑名單"))
            return

        if user_text.startswith("/黑名單"):
            try:
                _, phone = user_text.split()
                w = Whitelist.query.filter_by(phone=phone).first()
                if w:
                    db.session.delete(w)
                    db.session.add(Blacklist(date=datetime.now().strftime("%Y-%m-%d"), phone=phone, reason="轉移白名單", 名稱=w.名稱))
                    db.session.commit()
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🔁 {phone} 已轉為黑名單"))
                else:
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"查無此白名單：{phone}"))
            except:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❗ 指令錯誤，格式為 /黑名單 手機號"))
            return

        # 查詢資料
        if re.match(r"^09\d{8}$", user_text):
            b = Blacklist.query.filter_by(phone=user_text).first()
            w = Whitelist.query.filter_by(phone=user_text).first()
            if b:
                reply = f"🔴 黑名單\n🕒 {b.date}\n📱 {b.phone}\n🧸 {b.名稱 or '無'}\n📵 {b.reason}"
            elif w:
                reply = f"🟢 白名單\n🕒 {w.date}\n📱 {w.phone}\n🧸 {w.名稱 or '無'}\n📖 {w.reason}"
            else:
                reply = f"❓ 查無此號碼：{user_text}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

    # 一般使用者流程
    if re.match(r"^09\d{8}$", user_text):
        phone = user_text
        try:
            profile = line_bot_api.get_profile(user_id)
            display_name = profile.display_name
        except:
            display_name = "未命名"

        black = Blacklist.query.filter_by(phone=phone).first()
        if black:
            return  # 不回應黑名單

        white = Whitelist.query.filter_by(phone=phone).first()
        if white:
            reply = f"📱 {phone}\n✅ 已經驗證完成！\n🧸 暱稱：{white.名稱 or display_name}\n🕒 時間：{white.created_at.strftime('%Y/%m/%d %H:%M:%S')}"
        else:
            new_white = Whitelist(
                date=datetime.now().strftime("%Y-%m-%d"),
                phone=phone,
                reason="自動加入",
                名稱=display_name
            )
            db.session.add(new_white)
            db.session.commit()
            reply = f"✅ 驗證成功！\n📱 {phone}\n🧸 暱稱：{display_name}\n🕒 {new_white.created_at.strftime('%Y/%m/%d %H:%M:%S')}"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
