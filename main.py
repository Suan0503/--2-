# -*- coding: utf-8 -*-
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

ADMINS = {"U8f3cc921a9dd18d3e257008a34dd07c1"}
admin_mode = set()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    line_user_id = db.Column(db.String(255), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(10), nullable=False, default='pending')
    verified_at = db.Column(db.DateTime, nullable=True)

class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    reason = db.Column(db.Text)
    nickname = db.Column(db.String(255))

class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    reason = db.Column(db.Text)
    nickname = db.Column(db.String(255))

with app.app_context():
    db.create_all()

@app.route("/")
def home():
    return "LINE Bot 運作中～♥"

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
    welcome = (
        "歡迎加入🍵茗殿🍵\n\n"
        "請正確回答並提供下面的資料快速配合驗證。\n\n"
        "⭐️ line主頁>右上角設定>個人檔案（點進去之後截圖回傳）\n"
        "⭐️ 手機號碼：\n"
        "⭐️ LINE ID：\n\n"
        "需符合圖片上的LINE ID 以及手機號碼 未顯示無法驗證"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name

    # 管理員模式開關
    if user_id in ADMINS:
        if user_text == "/管理員 ON":
            admin_mode.add(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage("🔓 已進入管理員模式"))
            return
        elif user_text == "/管理員 OFF":
            admin_mode.discard(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage("🔒 已離開管理員模式"))
            return

    # 管理員模式下指令
    if user_id in admin_mode:
        if user_text == "/指令":
            cmds = (
                "📋 管理員指令列表：\n"
                "• /修改 電話 ➜ 修改資料\n"
                "• /新增 電話 白名單/黑名單 ➜ 手動新增\n"
                "• /黑名單 電話 ➜ 白轉黑\n"
                "• 直接輸入電話 ➜ 查詢黑白名單"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=cmds))
            return

        if re.match(r"^/修改 \\d{10}$", user_text):
            phone = user_text[4:]
            b = Blacklist.query.filter_by(phone=phone).first()
            w = Whitelist.query.filter_by(phone=phone).first()
            if w:
                msg = f"🟢 白名單\n時間：{w.date}\n暱稱：{w.nickname}\n電話：{w.phone}\n原因：{w.reason}"
            elif b:
                msg = f"🔴 黑名單\n時間：{b.date}\n暱稱：{b.nickname}\n電話：{b.phone}\n原因：{b.reason}"
            else:
                msg = "查無資料"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return

        if re.match(r"^/新增 \\d{10} (白名單|黑名單)$", user_text):
            phone, typ = user_text.split(" ")[1:3]
            if typ == "白名單":
                db.session.add(Whitelist(date=datetime.now().strftime("%Y-%m-%d"), phone=phone, reason="手動新增", nickname=display_name))
            else:
                db.session.add(Blacklist(date=datetime.now().strftime("%Y-%m-%d"), phone=phone, reason="手動新增", nickname=display_name))
            db.session.commit()
            line_bot_api.reply_message(event.reply_token, TextSendMessage(f"{phone} 已加入{typ}"))
            return

        if re.match(r"^/黑名單 \\d{10}$", user_text):
            phone = user_text[5:]
            white = Whitelist.query.filter_by(phone=phone).first()
            if white:
                db.session.delete(white)
                db.session.commit()
                db.session.add(Blacklist(date=datetime.now().strftime("%Y-%m-%d"), phone=phone, reason="白轉黑", nickname=white.nickname))
                db.session.commit()
                line_bot_api.reply_message(event.reply_token, TextSendMessage(f"{phone} 已轉入黑名單"))
            else:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(f"{phone} 不在白名單中"))
            return

        if re.match(r"^09\\d{8}$", user_text):
            phone = user_text
            b = Blacklist.query.filter_by(phone=phone).first()
            w = Whitelist.query.filter_by(phone=phone).first()
            if w:
                msg = f"🟢 白名單\n時間：{w.date}\n暱稱：{w.nickname}\n電話：{w.phone}\n原因：{w.reason}"
            elif b:
                msg = f"🔴 黑名單\n時間：{b.date}\n暱稱：{b.nickname}\n電話：{b.phone}\n原因：{b.reason}"
            else:
                msg = f"❓ {phone} 不在任何名單中"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return

    # 一般用戶處理
    if re.match(r"^09\\d{8}$", user_text):
        phone = user_text
        b = Blacklist.query.filter_by(phone=phone).first()
        if b:
            return  # 黑名單不回應

        w = Whitelist.query.filter_by(phone=phone).first()
        if not w:
            db.session.add(Whitelist(
                date=datetime.now().strftime("%Y-%m-%d"),
                phone=phone,
                reason="自動加入",
                nickname=display_name
            ))
            db.session.commit()

        success_msg = (
            f"✅ 驗證成功 感謝哥哥配合\n📱 {phone}\n"
            f"✈️ 想直接看每日班表也可以領取唷：\n👉 https://t.me/+XgwLCJ6kdhhhZDE1"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=success_msg))
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
