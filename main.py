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

# 載入環境變數
load_dotenv()

# 初始化 Flask 與資料庫
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# LINE Bot 初始化
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 管理變數
ADMINS = ["U8f3cc921a9dd18d3e257008a34dd07c1"]
admin_mode = set()
temp_users = {}  # 暫存使用者輸入

# 時區設定
tz = pytz.timezone("Asia/Taipei")

# 資料表
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

# 路由
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

# 使用者加入時歡迎訊息
@handler.add(FollowEvent)
def handle_follow(event):
    msg = (
        "歡迎加入🍵茗殿🍵\n"
        "請正確按照步驟提供資料配合快速驗證\n\n"
        "➡️ 請輸入手機號碼進行驗證（含09開頭）"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

# 文字處理邏輯
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    print(f"[INPUT] User ID: {user_id}, Text: {user_text}")

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
                f"✅ 驗證成功，歡迎加入茗殿"
            )
        else:
            reply = "⚠️ 你已驗證完成，請輸入手機號碼查看驗證資訊"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if re.match(r"^09\d{8}$", user_text):
        if Blacklist.query.filter_by(phone=user_text).first():
            return
        repeated = Whitelist.query.filter_by(phone=user_text).first()
        if repeated and repeated.line_user_id:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 此手機號碼已被使用，請輸入正確的手機號碼"))
            return
        temp_users[user_id] = {"phone": user_text, "name": display_name}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📱 手機已登記，請接著輸入您的 LINE ID～"))
        return

    if user_id in temp_users and len(user_text) >= 4:
        record = temp_users[user_id]
        record["line_id"] = user_text
        reply = (
            f"📱 {record['phone']}\n"
            f"🌸 暱稱：{record['name']}\n"
            f"       個人編號：待驗證後產生\n"
            f"🔗 LINE ID：{record['line_id']}\n"
            f"請問以上資料是否正確？資料一經送出無法修改，如正確請回復 1"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if user_text == "1" and user_id in temp_users:
        data = temp_users[user_id]
        now = datetime.now(tz)
        existing_record = Whitelist.query.filter_by(phone=data["phone"]).first()

        if existing_record:
            existing_record.line_user_id = user_id
            existing_record.line_id = data["line_id"]
            existing_record.name = data["name"]
            db.session.commit()
            saved_id = existing_record.id
            created_time = existing_record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')
        else:
            new_user = Whitelist(
                phone=data["phone"],
                name=data["name"],
                line_id=data["line_id"],
                date=now.strftime("%Y-%m-%d"),
                created_at=now,
                line_user_id=user_id
            )
            db.session.add(new_user)
            db.session.commit()
            saved_id = new_user.id
            created_time = now.strftime('%Y/%m/%d %H:%M:%S')

        reply = (
            f"📱 {data['phone']}\n"
            f"🌸 暱稱：{data['name']}\n"
            f"       個人編號：{saved_id}\n"
            f"🔗 LINE ID：{data['line_id']}\n"
            f"🕒 {created_time}\n"
            f"✅ 驗證成功，歡迎加入茗殿"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        temp_users.pop(user_id)
        return

# 圖片辨識處理（防止 499）
@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    if user_id not in temp_users:
        return

    # 快速回覆避免 499
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="🖼️ 圖片接收中，請稍候... 正在驗證中～")
    )

    try:
        message_content = line_bot_api.get_message_content(event.message.id)
        image_data = b''.join(chunk for chunk in message_content.iter_content())

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tf:
            tf.write(image_data)
            temp_path = tf.name

        img = Image.open(temp_path)
        img = img.resize((img.width // 2, img.height // 2))
        ocr_text = pytesseract.image_to_string(img, lang="eng+chi_tra")
        print(f"[OCR] {ocr_text}")

        phone_match = re.search(r"09\d{8}", ocr_text)
        line_id_match = re.search(r"ID[:：\s]*([a-zA-Z0-9_\-]+)", ocr_text)

        record = temp_users[user_id]
        if phone_match and line_id_match:
            phone_ok = phone_match.group() == record['phone']
            line_id_ok = line_id_match.group(1) == record['line_id']

            if phone_ok and line_id_ok:
                reply = (
                    f"📱 {record['phone']}\n"
                    f"🌸 暱稱：{record['name']}\n"
                    f"       個人編號：待驗證後產生\n"
                    f"🔗 LINE ID：{record['line_id']}\n"
                    f"🖼️ 圖片驗證成功！請回覆 1 完成登記。"
                )
            else:
                reply = "⚠️ 圖片內容與先前輸入不符，請重新確認。"
        else:
            reply = "⚠️ 未能辨識圖片中的手機號碼與 LINE ID，請重新拍攝並傳送。"

        line_bot_api.push_message(user_id, TextSendMessage(text=reply))

    except Exception as e:
        print("❗ 圖片處理錯誤：", e)
        traceback.print_exc()
        line_bot_api.push_message(user_id, TextSendMessage(text="⚠️ 圖片驗證時發生錯誤，請稍後再試～"))

# 啟動伺服器
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
