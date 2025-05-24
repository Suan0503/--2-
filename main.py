from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.models import MessageEvent, TextMessage, TextSendMessage, FollowEvent
from linebot.exceptions import InvalidSignatureError
from datetime import datetime
from dotenv import load_dotenv
@@ -70,11 +70,30 @@ def callback():
        abort(400)
    return "OK"

@handler.add(FollowEvent)
def handle_follow(event):
    welcome = "歡迎加入～請輸入手機號碼進行驗證喲 📱"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()

    # 指令查詢
    if user_text == "/指令":
        reply = (
            "📋 可用指令列表：\n"
            "/查 單號碼 - 查使用者驗證狀態\n"
            "/封鎖 手機號 - 將使用者列入黑名單\n"
            "/解鎖 手機號 - 解除封鎖\n"
            "/拉黑 手機號 原因\n"
            "/白單 手機號 原因\n"
            "/查單 手機號 - 查詢黑白名單紀錄"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    if user_text == "查詢":
        user = User.query.filter_by(line_user_id=user_id).first()
        if user:
@@ -166,10 +185,7 @@ def handle_message(event):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

    # 非指令處理區段 - 最後驗證手機
    if user_text.startswith("/"):
        return

    # 手機號碼驗證區段
    if re.match(r"^09\d{8}$", user_text):
        existing = User.query.filter_by(phone_number=user_text).first()
        if existing:
@@ -194,8 +210,6 @@ def handle_message(event):
            append_to_sheet(user_text, user_id, "white", user.verified_at)
            reply = f"驗證成功！{user_text} 已加入白名單 🎉"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
    else:
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
