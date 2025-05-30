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
import pytesseract
from PIL import Image

print("🟢 進入 main.py 開始啟動 Flask")

load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

temp_users = {}

class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(255))
    line_id = db.Column(db.String(100))
    line_user_id = db.Column(db.String(255), unique=True)

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
        print("🔴 LINE Callback 發生錯誤：", e)
        traceback.print_exc()
        abort(500)
    return "OK"

@handler.add(FollowEvent)
def handle_follow(event):
    msg = "請上傳個人檔案截圖，我們將自動辨識並開始快速驗證唷～📷"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    profile = line_bot_api.get_profile(user_id)
    name = profile.display_name
    tz = pytz.timezone("Asia/Taipei")
    now = datetime.now(tz)

    try:
        message_content = line_bot_api.get_message_content(event.message.id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tf:
            for chunk in message_content.iter_content():
                tf.write(chunk)
            temp_path = tf.name

        img = Image.open(temp_path)
        ocr_text = pytesseract.image_to_string(img, lang="eng+chi_tra")
        print("[OCR]", ocr_text)

        phone_match = re.search(r"09\d{8}", ocr_text)
        line_id_match = re.search(r"LINE\s*ID[:：]?\s*([a-zA-Z0-9_\-]+)", ocr_text, re.IGNORECASE)

        if phone_match and line_id_match:
            phone = phone_match.group()
            line_id = line_id_match.group(1)

            temp_users[user_id] = {
                "phone": phone,
                "name": name,
                "line_id": line_id,
                "time": now.strftime("%Y/%m/%d %H:%M:%S")
            }

            msg = (
                f"📱 {phone}\n"
                f"🌸 暱稱：{name}\n"
                f"       個人編號：\n"
                f"🔗 LINE ID：{line_id}\n"
                f"🕒 {now.strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"是否正確？正確請回覆 1 完成登記～"
            )
        else:
            msg = "⚠️ 無法辨識手機號碼與 LINE ID，請重新上傳清晰截圖。"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

    except Exception as e:
        print("🔴 辨識圖片時出錯：", e)
        traceback.print_exc()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 發生錯誤，請稍後再試。"))

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    tz = pytz.timezone("Asia/Taipei")

    if event.message.text.strip() == "1" and user_id in temp_users:
        data = temp_users[user_id]
        now = datetime.now(tz)

        try:
            new_entry = Whitelist(
                phone=data["phone"],
                name=data["name"],
                line_id=data["line_id"],
                date=now.strftime("%Y-%m-%d"),
                created_at=now,
                line_user_id=user_id
            )
            db.session.add(new_entry)
            db.session.commit()
            saved_id = new_entry.id

            msg = (
                f"📱 {data['phone']}\n"
                f"🌸 暱稱：{data['name']}\n"
                f"       個人編號：{saved_id}\n"
                f"🔗 LINE ID：{data['line_id']}\n"
                f"🕒 {data['time']}\n"
                f"✅ 驗證成功，歡迎加入茗殿～"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            temp_users.pop(user_id)
        except Exception as e:
            print("🔴 儲存資料時出錯：", e)
            traceback.print_exc()
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 資料儲存失敗，請稍後再試。"))
