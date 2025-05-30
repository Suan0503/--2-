print("🟢 進入 main.py 開始啟動 Flask")
from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent, ImageMessage
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
from dotenv import load_dotenv
import os
import re
import traceback
import pytz
import tempfile
import requests
import pytesseract
from PIL import Image

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
temp_users = {}  # line_user_id => { phone, name, line_id }

class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    name = db.Column(db.String(255))
    line_id = db.Column(db.String(100))
    line_user_id = db.Column(db.String(255), unique=True)

class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    name = db.Column(db.String(255))

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
        "歡迎加入🍵華橋店🍵\n"
        "請正確按照步驟提供資料配合快速驗證\n\n"
        "➡️ 請輸入手機號碼進行驗證（含09開頭）"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    print(f"[INPUT] User ID: {user_id}, Text: {user_text}")

    tz = pytz.timezone("Asia/Taipei")
    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name

    existing = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing:
        if user_text == existing.phone:
            reply = (
                f"📱 {existing.phone}\n"
                f"🌸 暱稱：{existing.name or display_name}\n"
                f"       個人編號：{existing.id}\n"
                f"🔗 LINE ID：{existing.line_id or '未登記'}\n"
                f"🕒 {existing.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入華橋"
            )
        else:
            reply = "⚠️ 你已驗證完成，請輸入手機號碼查看驗證資訊"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if re.match(r"^09\d{8}$", user_text):
        black = Blacklist.query.filter_by(phone=user_text).first()
        if black:
            return
        repeated = Whitelist.query.filter_by(phone=user_text).first()
        if repeated and repeated.line_user_id:
            reply = "⚠️ 此手機號碼已被使用，請輸入正確的手機號碼"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return
        temp_users[user_id] = {"phone": user_text, "name": display_name}
        reply = "📱 手機已登記，請接著輸入您的 LINE ID～"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if user_id in temp_users and len(user_text) >= 4:
        record = temp_users[user_id]
        record["line_id"] = user_text
        temp_users[user_id] = record
        reply = (
            f"📱 {record['phone']}\n"
            f"🌸 暱稱：{record['name']}\n"
            f"       個人編號：待驗證後產生\n"
            f"🔗 LINE ID：{record['line_id']}\n"
            f"📷 請對照描述內容截圖帶入\n確認無誤後請傳送圖片"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    if user_id not in temp_users:
        return
    message_content = line_bot_api.get_message_content(event.message.id)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tf:
        for chunk in message_content.iter_content():
            tf.write(chunk)
        temp_path = tf.name

    img = Image.open(temp_path)
    ocr_text = pytesseract.image_to_string(img, lang="eng+chi_tra")
    print(f"[OCR] {ocr_text}")

    phone_match = re.search(r"09\d{8}", ocr_text)
    line_id_match = re.search(r"ID[:\uff1a\s]*([a-zA-Z0-9_\-]+)", ocr_text)

    record = temp_users[user_id]
    if phone_match and line_id_match:
        phone_ok = phone_match.group() == record['phone']
        line_id_ok = line_id_match.group(1) == record['line_id']

        if phone_ok and line_id_ok:
            now = datetime.now(pytz.timezone("Asia/Taipei"))
            existing_record = Whitelist.query.filter_by(phone=record["phone"]).first()
            if existing_record:
                existing_record.line_user_id = user_id
                existing_record.line_id = record["line_id"]
                existing_record.name = record["name"]
                db.session.commit()
                saved_id = existing_record.id
                created_time = existing_record.created_at.astimezone(pytz.timezone("Asia/Taipei")).strftime('%Y/%m/%d %H:%M:%S')
            else:
                new_user = Whitelist(
                    phone=record["phone"],
                    name=record["name"],
                    line_id=record["line_id"],
                    date=now.strftime("%Y-%m-%d"),
                    created_at=now,
                    line_user_id=user_id
                )
                db.session.add(new_user)
                db.session.commit()
                saved_id = new_user.id
                created_time = now.strftime('%Y/%m/%d %H:%M:%S')

            temp_users.pop(user_id, None)
            reply = (
                f"📱 {record['phone']}\n"
                f"🌸 暱稱：{record['name']}\n"
                f"       個人編號：{saved_id}\n"
                f"🔗 LINE ID：{record['line_id']}\n"
                f"🕒 {created_time}\n"
                f"✅ 驗證成功，歡迎加入華橋"
            )
        else:
            reply = "⚠️ 圖片內容與先前輸入不符，請重新確認後傳送"
    else:
        reply = "⚠️ 未能辨識圖片中的手機號碼與 LINE ID，請重新拍摄並傳送"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
