
from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent, ImageMessage, TemplateSendMessage, ButtonsTemplate, PostbackAction
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

pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

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
        traceback.print_exc()
        abort(500)
    return "OK"

@handler.add(FollowEvent)
def handle_follow(event):
    msg = "請輸入手機號碼開始驗證（例如：0912345678）📱"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    msg = event.message.text.strip()
    profile = line_bot_api.get_profile(user_id)
    tz = pytz.timezone("Asia/Taipei")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    existing = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="✅ 已完成驗證"))
        return

    if re.match(r"^09\d{8}$", msg):
        temp_users[user_id] = {"phone": msg, "name": profile.display_name, "line_id": "", "time": now}
        reply = "請輸入您的 LINE ID（不含@）"
    elif user_id in temp_users and not temp_users[user_id]["line_id"]:
        temp_users[user_id]["line_id"] = msg
        reply = "請上傳 LINE 截圖顯示手機與 LINE ID"
    elif msg == "1" and user_id in temp_users:
        data = temp_users[user_id]
        new = Whitelist(phone=data["phone"], name=data["name"], line_id=data["line_id"], date=now, line_user_id=user_id)
        db.session.add(new)
        db.session.commit()
        del temp_users[user_id]
        template = TemplateSendMessage(
            alt_text='驗證完成選單',
            template=ButtonsTemplate(
                title='✅ 驗證成功',
                text='請選擇您要進行的操作',
                actions=[
                    PostbackAction(label='驗證資訊', data='info'),
                    PostbackAction(label='每日班表', data='schedule'),
                    PostbackAction(label='新品上架', data='new'),
                    PostbackAction(label='預約諮詢', data='booking')
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, template)
        return
    else:
        reply = "請先輸入手機號碼（例如：0912345678）"

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

    try:
        img = Image.open(temp_path)
        ocr_text = pytesseract.image_to_string(img, lang="eng+chi_tra")
        print("[OCR]", ocr_text)
    except Exception as e:
        print("[OCR Failed]", e)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 圖片辨識失敗，請重新上傳清晰圖片"))
        return

    phone_match = re.search(r"09\d{8}", ocr_text)
    line_id_match = re.search(r"ID[:：\s]*([a-zA-Z0-9_\-]+)", ocr_text)
    record = temp_users[user_id]

    if phone_match and line_id_match:
        phone_ok = phone_match.group() == record['phone']
        line_id_ok = line_id_match.group(1) == record['line_id']
        if phone_ok and line_id_ok:
            msg = "✅ 圖片驗證成功，請回覆 1 完成登記"
        else:
            msg = "⚠️ 圖片資訊與您輸入的不符，請重新確認"
    else:
        msg = "⚠️ 無法辨識手機與 ID，請重新拍攝並上傳"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
