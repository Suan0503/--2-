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

ADMINS = ["U8f3cc921a9dd18d3e257008a34dd07c1"]
admin_mode = set()
temp_users = {}  # 暫存用戶資料（輸入的手機、ID）

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
        "歡迎加入🍵茗殿🍵\n"
        "請正確按照步驟提供資料配合快速驗證\n\n"
        "➡️ 請輸入手機號碼進行驗證（含09開頭）"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    print(f"[INPUT] User ID: {user_id}, Text: {user_text}")

    tz = pytz.timezone("Asia/Taipei")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name

    existing = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing:
        if user_text == existing.phone:
            reply = (
                f"📱 {existing.phone}\n"
                f"🌸 暱稱：{existing.name or display_name}\n"
                f"       個人編號：{existing.id}\n"
                f"🔗 LINE ID：{existing.line_id or '無資料'}\n"
                f"⏰ 驗證時間：{existing.created_at.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            reply = "✅ 你已完成驗證，不需再次輸入。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 尚未驗證，先要求補資料
    if re.match(r"^09\d{8}$", user_text):
        temp_users[user_id] = {"phone": user_text, "name": display_name, "line_id": ""}
        reply = "請輸入您的 LINE ID（不含@）"
    elif user_id in temp_users and not temp_users[user_id]["line_id"]:
        temp_users[user_id]["line_id"] = user_text
        reply = "請上傳 LINE 個人頁面截圖（顯示手機與 ID）做圖像驗證"
    elif user_text == "1" and user_id in temp_users:
        data = temp_users[user_id]
        new = Whitelist(
            phone=data["phone"], name=data["name"], line_id=data["line_id"],
            date=now, line_user_id=user_id
        )
        db.session.add(new)
        db.session.commit()
        reply = "🎉 資料已確認登記成功，歡迎使用後續功能～"
        temp_users.pop(user_id, None)
    else:
        reply = "請先輸入手機號碼（09開頭）來開始驗證流程～"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

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
        reply = "⚠️ 無法辨識圖片中的手機與 ID，請重新拍攝並上傳。"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
