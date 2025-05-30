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
import pytesseract
from PIL import Image
import threading

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

@handler.add(FollowEvent)
def handle_follow(event):
    msg = (
        "歡迎加入🍵茗殿🍵\n"
        "請正確按照步驟提供資料配合快速驗證\n\n"
        "➡️ 請輸入手機號碼進行驗證（含09開頭）"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    if user_id not in temp_users:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 請先輸入手機號碼與 LINE ID"))
        return

    # 先行回覆，避免 callback timeout
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🖼️ 收到圖片，正在驗證中…請稍等～"))

    def process_image():
        try:
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
                reply = "⚠️ 未能辨識圖片中的手機號碼與 LINE ID，請重新拍攝並傳送。"

            line_bot_api.push_message(user_id, TextSendMessage(text=reply))

        except Exception as e:
            print("❗ 圖片處理錯誤：", e)
            traceback.print_exc()
            line_bot_api.push_message(user_id, TextSendMessage(text="⚠️ 圖片處理時發生錯誤，請稍後再試。"))

    threading.Thread(target=process_image).start()
