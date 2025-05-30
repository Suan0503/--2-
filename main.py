from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import (MessageEvent, TextMessage, TextSendMessage,
                            FollowEvent, ImageMessage, PostbackEvent, FlexSendMessage)
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
from dotenv import load_dotenv
import os
import re
import traceback
import pytz

print("🟢 啟動 LINE 機器人")

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
temp_users = {}

class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
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
        print("❗ callback 發生例外：", e)
        traceback.print_exc()
        abort(500)
    return "OK"

@handler.add(FollowEvent)
def handle_follow(event):
    msg = ("歡迎加入🍵茗殿🍵\n"
           "請正確按照步驟提供資料配合快速驗證\n\n"
           "➡️ 請輸入手機號碼進行驗證（含09開頭）")
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
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
                f"⏰ 驗證時間：{existing.created_at.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            reply = "✅ 你已完成驗證，不需再次輸入。"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if re.match(r"^09\d{8}$", user_text):
        temp_users[user_id] = {"phone": user_text, "name": display_name, "line_id": ""}
        reply = "請輸入您的 LINE ID（不含@）"
    elif user_id in temp_users and not temp_users[user_id]["line_id"]:
        temp_users[user_id]["line_id"] = user_text
        reply = "✅ 請輸入 1 確認並完成驗證"
    elif user_text == "1" and user_id in temp_users:
        data = temp_users[user_id]
        new = Whitelist(
            phone=data["phone"], name=data["name"], line_id=data["line_id"],
            date=now, line_user_id=user_id
        )
        db.session.add(new)
        db.session.commit()
        temp_users.pop(user_id, None)

        flex_contents = {
            "type": "bubble",
            "size": "mega",
            "hero": {
                "type": "image",
                "url": "https://i.imgur.com/VYQ4Jqa.png",
                "size": "full",
                "aspectRatio": "20:13",
                "aspectMode": "cover"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": "🎉 驗證完成！", "size": "xl", "weight": "bold", "color": "#1DB446"},
                    {"type": "text", "text": f"哈囉 {data['name']}，歡迎加入 🍵茗殿🍵", "wrap": True},
                    {"type": "separator"},
                    {"type": "text", "text": "請選擇下一步操作：", "wrap": True, "margin": "md"},
                    {"type": "box", "layout": "vertical", "spacing": "sm", "margin": "lg", "contents": [
                        {"type": "button", "style": "primary", "color": "#93D6B9", "action": {"type": "postback", "label": "✅ 驗證資訊", "data": "action=info"}},
                        {"type": "button", "style": "primary", "color": "#B1D4E0", "action": {"type": "postback", "label": "📅 每日班表", "data": "action=schedule"}},
                        {"type": "button", "style": "primary", "color": "#E2C0BE", "action": {"type": "postback", "label": "🆕 新品上架", "data": "action=new"}},
                        {"type": "button", "style": "primary", "color": "#F5BBA7", "action": {"type": "postback", "label": "📝 預約諮詢", "data": "action=booking"}}
                    ]}
                ]
            }
        }
        flex_msg = FlexSendMessage(alt_text="驗證完成，請選擇下一步", contents=flex_contents)
        line_bot_api.reply_message(event.reply_token, flex_msg)
        return
    else:
        reply = "請先輸入手機號碼（09開頭）來開始驗證流程～"

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    if data == "action=info":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="這是你的驗證資訊頁面唷🌟"))
    elif data == "action=schedule":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="📅 查看每日班表請點：\nhttps://your-domain.com/schedule"))
    elif data == "action=new":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="🆕 新品上架資訊會定期公告唷～"))
    elif data == "action=booking":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入想預約的妹妹名稱，我們會儘快協助安排唷～💕"))
