from flask import Flask, request, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage, FollowEvent, ImageMessage
)
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
from dotenv import load_dotenv
import os
import re
import traceback
import pytz
from draw_utils import draw_coupon, get_today_coupon_flex, has_drawn_today, save_coupon_record

# OCR 模組
from image_verification import extract_lineid_phone

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
        alt_text="功能選單",
        contents={
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": "✨ 功能選單 ✨", "weight": "bold", "size": "lg", "align": "center", "color": "#C97CFD"},
                    {"type": "separator"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "lg",
                        "spacing": "sm",
                        "contents": [
                            # 按鈕1
                            {
                                "type": "button",
                                "action": {"type": "message", "label": "📱 驗證資訊", "text": "驗證資訊"},
                                "style": "primary",
                                "color": "#FFB6B6"  # 粉紅
                            },
                            # 按鈕2
                            {
                                "type": "button",
                                "action": {
                                    "type": "uri",
                                    "label": "📅 每日班表",
                                    "uri": "https://t.me/+XgwLCJ6kdhhhZDE1"
                                },
                                "style": "secondary",
                                "color": "#FFF8B7"  # 淡黃
                            },
                            # 按鈕3
                            {
                                "type": "button",
                                "action": {"type": "message", "label": "🎁 每日抽獎", "text": "每日抽獎"},
                                "style": "primary",
                                "color": "#A3DEE6"  # 淡藍
                            },
                            # 按鈕4
                            {
                                "type": "button",
                                "action": {"type": "uri", "label": "📬 預約諮詢", "uri": choose_link()},
                                "style": "primary",
                                "color": "#B889F2"  # 淡紫
                            },
                            # 按鈕5（新）
                            {
                                "type": "button",
                                "action": {
                                    "type": "uri",
                                    "label": "🌸 茗殿討論區",
                                    "uri": "https://line.me/ti/g2/mq8VqBIVupL1lsIXuAulnqZNz5vw7VKrVYjNDg?utm_source=invitation&utm_medium=link_copy&utm_campaign=default"
                                },
                                "style": "primary",
                                "color": "#FFDCFF"  # 很可愛的淡粉紫
                            }
                        ]
                    }
                ]
            }
        }
    )

def choose_link():
    group = [
        "https://line.me/ti/p/g7TPO_lhAL",
        "https://line.me/ti/p/Q6-jrvhXbH",
        "https://line.me/ti/p/AKRUvSCLRC"
    ]
    return group[hash(os.urandom(8)) % len(group)]

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
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    tz = pytz.timezone("Asia/Taipei")
    profile = line_bot_api.get_profile(user_id)
    display_name = profile.display_name

    if user_text == "驗證資訊":
        existing = Whitelist.query.filter_by(line_user_id=user_id).first()
        if existing:
            reply = (
                f"📱 {existing.phone}\n"
                f"🌸 暱稱：{existing.name or display_name}\n"
                f"       個人編號：{existing.id}\n"
                f"🔗 LINE ID：{existing.line_id or '未登記'}\n"
                f"🕒 {existing.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿\n"
                f"🌟 加入密碼：ming666"
            )
            line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply), get_function_menu_flex()])
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 你尚未完成驗證，請輸入手機號碼進行驗證。"))
        return

    if user_text == "每日抽獎":
        today_str = datetime.now(tz).strftime("%Y-%m-%d")
        if has_drawn_today(user_id, Coupon):
            coupon = Coupon.query.filter_by(line_user_id=user_id, date=today_str).first()
            flex = get_today_coupon_flex(user_id, display_name, coupon.amount)
            line_bot_api.reply_message(event.reply_token, flex)
            return
        amount = draw_coupon()
        save_coupon_record(user_id, amount, Coupon, db)
        flex = get_today_coupon_flex(user_id, display_name, amount)
        line_bot_api.reply_message(event.reply_token, flex)
        return

    existing = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing:
        if user_text == existing.phone:
            reply = (
                f"📱 {existing.phone}\n"
                f"🌸 暱稱：{existing.name or display_name}\n"
                f"       個人編號：{existing.id}\n"
                f"🔗 LINE ID：{existing.line_id or '未登記'}\n"
                f"🕒 {existing.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿\n"
                f"🌟 加入密碼：ming666"
            )
            line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply), get_function_menu_flex()])
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 你已驗證完成，請輸入手機號碼查看驗證資訊"))
        return

    if re.match(r"^09\d{8}$", user_text):
        black = Blacklist.query.filter_by(phone=user_text).first()
        if black:
            return
        repeated = Whitelist.query.filter_by(phone=user_text).first()
        if repeated and repeated.line_user_id:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ 此手機號碼已被使用，請輸入正確的手機號碼")
            )
            return
        temp_users[user_id] = {"phone": user_text, "name": display_name, "step": "waiting_lineid"}
        line_bot_api.reply_message(
            event.reply_token,
            [
                TextSendMessage(text="📱 手機已登記囉～請接著輸入您的 LINE ID"),
                TextSendMessage(text="（如無 ID 請輸入：無ID）\n若手機就是 ID，請開頭輸入ID兩字（ID09XXXXXXXX）")
            ]
        )
        return

    # 步驟二：輸入 LINE ID
    if user_id in temp_users and temp_users[user_id].get("step", "waiting_lineid") == "waiting_lineid" and len(user_text) >= 4:
        record = temp_users[user_id]
        record["line_id"] = user_text
        record["step"] = "waiting_screenshot"
        temp_users[user_id] = record

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=(
                    "請上傳您的 LINE 個人頁面截圖（需清楚顯示手機號與 LINE ID）以供驗證。\n"
                    "📸 操作教學：LINE主頁 > 右上角設定 > 個人檔案（點進去之後截圖）"
                )
            )
        )
        return

    # 步驟四：用戶確認
    if user_text == "1" and user_id in temp_users and temp_users[user_id].get("step") == "waiting_confirm":
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
            f"✅ 驗證成功，歡迎加入茗殿\n"
            f"🌟 加入密碼：ming666"
        )
        line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply), get_function_menu_flex()])
        temp_users.pop(user_id)
        return

# 處理 LINE 截圖上傳並 OCR 驗證
@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    if user_id not in temp_users or temp_users[user_id].get("step") != "waiting_screenshot":
        return  # 非驗證流程不處理

    # 下載圖片
    message_content = line_bot_api.get_message_content(event.message.id)
    image_path = f"/tmp/{user_id}_line_profile.png"
    with open(image_path, 'wb') as fd:
        for chunk in message_content.iter_content():
            fd.write(chunk)

    # OCR 驗證
    phone_ocr, lineid_ocr, ocr_text = extract_lineid_phone(image_path)
    input_phone = temp_users[user_id].get("phone")
    input_lineid = temp_users[user_id].get("line_id")

    # 比對 OCR 結果
    if phone_ocr == input_phone and lineid_ocr == input_lineid:
        record = temp_users[user_id]
        reply = (
            f"📱 {record['phone']}\n"
            f"🌸 暱稱：{record['name']}\n"
            f"       個人編號：待驗證後產生\n"
            f"🔗 LINE ID：{record['line_id']}\n"
            f"請問以上資料是否正確？正確請回復 1\n"
            f"⚠️輸入錯誤請從新輸入手機號碼即可⚠️"
        )
        record["step"] = "waiting_confirm"
        temp_users[user_id] = record
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="❌ 截圖中的手機號碼或 LINE ID 與您輸入的不符，請重新上傳正確的 LINE 個人頁面截圖。")
        )

@app.route("/ocr", methods=["POST"])
def ocr_image_verification():
    if "image" not in request.files:
        return jsonify({"error": "請上傳圖片（欄位名稱 image）"}), 400
    file = request.files["image"]
    file_path = "temp_ocr_img.png"
    file.save(file_path)
    phone, line_id, text = extract_lineid_phone(file_path)
    os.remove(file_path)
    return jsonify({
        "phone": phone,
        "line_id": line_id,
        "ocr_text": text
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
