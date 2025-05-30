from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage, FollowEvent
)
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
from dotenv import load_dotenv
import os
import re
import traceback
import pytz
from draw_utils import draw_coupon, get_today_coupon_flex, has_drawn_today, save_coupon_record

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
ADMINS = ["U8f3cc921a9dd18d3e257008a34dd07c1"]

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

class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    line_user_id = db.Column(db.String(255))
    date = db.Column(db.String(20))
    amount = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

def get_function_menu_flex():
    return FlexSendMessage(
        alt_text="\u2728\u529f\u80fd\u9078\u55ae\u2728",
        contents={
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "lg",
                "contents": [
                    {
                        "type": "text",
                        "text": "\u2728 \u529f\u80fd\u9078\u55ae \u2728",
                        "weight": "bold",
                        "size": "lg",
                        "align": "center",
                        "color": "#333333"
                    },
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "\ud83d\udcf1 \u9a57\u8b49\u8cc7\u8a0a", "text": "\u9a57\u8b49\u8cc7\u8a0a"},
                        "style": "primary",
                        "color": "#33CC99"
                    },
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "\ud83d\uddd5\ufe0f \u6bcf\u65e5\u73ed\u8868", "text": "\u6bcf\u65e5\u73ed\u8868"},
                        "style": "primary",
                        "color": "#33CC99"
                    },
                    {
                        "type": "button",
                        "action": {"type": "message", "label": "\ud83c\udf81 \u6bcf\u65e5\u62bd\u734e", "text": "\u6bcf\u65e5\u62bd\u734e"},
                        "style": "primary",
                        "color": "#33CC99"
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "uri",
                            "label": "\ud83d\udcd6 \u9810\u7d04\u8aee\u8a62",
                            "uri": "https://line.me/ti/p/g7TPO_lhAL"
                        },
                        "style": "primary",
                        "color": "#33CC99"
                    }
                ]
            }
        }
    )

@app.route("/")
def home():
    return "LINE Bot \u6b63\u5e38\u904b\u4f5c\u4e2d\uff5e\ud83c\udf75"

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        print("\u2757 callback \u767c\u751f\u4f8b\u5916\uff1a", e)
        traceback.print_exc()
        abort(500)
    return "OK"

@handler.add(FollowEvent)
def handle_follow(event):
    msg = (
        "\u6b61\u8fce\u52a0\u5165\ud83c\udf75\u83ef\u6bbf\ud83c\udf75\n"
        "\u8acb\u6b63\u78ba\u6309\u7167\u6b65\u9a5f\u63d0\u4f9b\u8cc7\u6599\u914d\u5408\u5feb\u901f\u9a57\u8b49\n\n"
        "\u27a1\ufe0f \u8acb\u8f38\u5165\u624b\u6a5f\u865f\u78bc\u9032\u884c\u9a57\u8b49\uff08\u542b09\u958b\u982d\uff09"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    tz = pytz.timezone("Asia/Taipei")
    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name

    if user_text == "\u6bcf\u65e5\u62bd\u734e":
        today_str = datetime.now(tz).strftime("%Y-%m-%d")
        if has_drawn_today(user_id, Coupon):
            coupon = Coupon.query.filter_by(line_user_id=user_id, date=today_str).first()
            flex = get_today_coupon_flex(user_id, coupon.amount)
            line_bot_api.reply_message(event.reply_token, flex)
            return

        amount = draw_coupon()
        save_coupon_record(user_id, amount, Coupon, db)
        flex = get_today_coupon_flex(user_id, amount)
        line_bot_api.reply_message(event.reply_token, flex)
        return

    existing = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing:
        if user_text == existing.phone:
            reply = (
                f"\ud83d\udcf1 {existing.phone}\n"
                f"\ud83c\udf38 \u66c9\u540d\uff1a{existing.name or display_name}\n"
                f"       \u500b\u4eba\u7de8\u865f\uff1a{existing.id}\n"
                f"\ud83d\udd17 LINE ID\uff1a{existing.line_id or ' \u672a\u767c\u9001'}\n"
                f"\ud83d\udd52 {existing.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"\u2705 \u9a57\u8b49\u6210\u529f\uff0c\u6b61\u8fce\u52a0\u5165\u83ef\u6bbf"
            )
            line_bot_api.reply_message(event.reply_token, [
                TextSendMessage(text=reply),
                get_function_menu_flex()
            ])
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="\u26a0\ufe0f \u4f60\u5df2\u9a57\u8b49\u5b8c\u6210\uff0c\u8acb\u8f38\u5165\u624b\u6a5f\u865f\u78bc\u67e5\u770b\u9a57\u8b49\u8cc7\u8a0a"))
        return

    if re.match(r"^09\d{8}$", user_text):
        black = Blacklist.query.filter_by(phone=user_text).first()
        if black:
            return
        repeated = Whitelist.query.filter_by(phone=user_text).first()
        if repeated and repeated.line_user_id:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="\u26a0\ufe0f \u6b64\u624b\u6a5f\u865f\u78bc\u5df2\u88ab\u4f7f\u7528"))
            return
        temp_users[user_id] = {"phone": user_text, "name": display_name}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="\ud83d\udcf1 \u624b\u6a5f\u5df2\u767b\u8a18\uff0c\u8acb\u8f38\u5165 LINE ID~"))
        return

    if user_id in temp_users and len(user_text) >= 4:
        record = temp_users[user_id]
        record["line_id"] = user_text
        temp_users[user_id] = record
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=(
            f"\ud83d\udcf1 {record['phone']}\n"
            f"\ud83c\udf38 \u66c9\u540d\uff1a{record['name']}\n"
            f"       \u500b\u4eba\u7de8\u865f\uff1a\u5f85\u9a57\u8b49\u5f8c\u7522\u751f\n"
            f"\ud83d\udd17 LINE ID\uff1a{record['line_id']}\n"
            f"\u8acb\u554f\u4ee5\u4e0a\u8cc7\u6599\u662f\u5426\u6b63\u78ba\uff1f\u6b63\u78ba\u8acb\u56de\u8986 1"
        )))
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
            f"\ud83d\udcf1 {data['phone']}\n"
            f"\ud83c\udf38 \u66c9\u540d\uff1a{data['name']}\n"
            f"       \u500b\u4eba\u7de8\u865f\uff1a{saved_id}\n"
            f"\ud83d\udd17 LINE ID\uff1a{data['line_id']}\n"
            f"\ud83d\udd52 {created_time}\n"
            f"\u2705 \u9a57\u8b49\u6210\u529f\uff0c\u6b61\u8fce\u52a0\u5165\u83ef\u6bbf"
        )
        line_bot_api.reply_message(event.reply_token, [
            TextSendMessage(text=reply),
            get_function_menu_flex()
        ])
        temp_users.pop(user_id)
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
