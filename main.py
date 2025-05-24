from flask import Flask, request, abort, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
from dotenv import load_dotenv
import os
import re

load_dotenv()

app = Flask(__name__, template_folder="templates")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

ADMINS = ["U8f3cc921a9dd18d3e257008a34dd07c1"]

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    line_user_id = db.Column(db.String(255), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(10), nullable=False, default='pending')
    verified_at = db.Column(db.DateTime, nullable=True)

class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    reason = db.Column(db.Text)

class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    reason = db.Column(db.Text)

with app.app_context():
    db.create_all()

@app.route("/")
def home():
    return "LINE Bot 正常運作中～🍓"

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    print(f"收到使用者輸入：{user_text}")

    if re.match(r"^09\d{8}$", user_text):
        existing_by_id = User.query.filter_by(line_user_id=user_id).first()
        existing_by_phone = User.query.filter_by(phone_number=user_text).first()

        if existing_by_phone and existing_by_phone.line_user_id != user_id:
            reply = f"⚠️ 此號碼已由其他帳號驗證過，無法重複綁定 ❌"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        if existing_by_id:
            if existing_by_id.status == "black":
                return
            elif existing_by_id.status == "white":
                vtime = existing_by_id.verified_at.strftime("%Y/%m/%d %H:%M") if existing_by_id.verified_at else "-"
                reply = f"📱 {existing_by_id.phone_number}\n✅ 已經驗證完成！\n🕒 時間：{vtime}"
            else:
                existing_by_id.phone_number = user_text
                existing_by_id.status = "white"
                existing_by_id.verified_at = datetime.now()
                db.session.commit()
                vtime = existing_by_id.verified_at.strftime("%Y/%m/%d %H:%M")
                reply = f"✅ 驗證成功！\n📱 {user_text}\n🕒 時間：{vtime}"
        else:
            new_user = User(
                line_user_id=user_id,
                phone_number=user_text,
                status="white",
                verified_at=datetime.now()
            )
            db.session.add(new_user)
            db.session.commit()
            vtime = new_user.verified_at.strftime("%Y/%m/%d %H:%M")
            reply = f"✅ 驗證成功！\n📱 {user_text}\n🕒 時間：{vtime}"

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))

@app.route("/dashboard")
def dashboard():
    users = User.query.order_by(User.verified_at.desc()).all()
    return render_template("dashboard.html", users=users)

@app.route("/api/query")
def api_query():
    phone = request.args.get("phone")
    user = User.query.filter_by(phone_number=phone).first()
    if user:
        return jsonify({
            "status": user.status,
            "phone": user.phone_number,
            "line_user_id": user.line_user_id,
            "verified_at": user.verified_at.strftime("%Y/%m/%d %H:%M") if user.verified_at else "-"
        })
    else:
        return jsonify({ "status": "not_found" })

@app.route("/api/delete", methods=["POST"])
def api_delete():
    phone = request.form.get("phone")
    user = User.query.filter_by(phone_number=phone).first()
    if user:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": f"{phone} 已刪除"})
    return jsonify({"message": "未找到使用者"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
