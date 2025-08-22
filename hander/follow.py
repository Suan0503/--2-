from linebot.models import FollowEvent, TextSendMessage, QuickReply, QuickReplyButton, MessageAction
from extensions import handler, line_bot_api

@handler.add(FollowEvent)
def handle_follow(event):
    welcome_msg = (
        "歡迎加入🍵茗殿🍵\n"
        "\n"
        "📜 驗證流程如下：\n"
        "1️⃣ 閱讀規則後點擊『我同意規則』\n"
        "2️⃣ 依步驟輸入手機號與 LINE ID\n"
        "3️⃣ 上傳 LINE 個人檔案截圖\n"
        "4️⃣ 系統進行快速自動驗證\n"
        "5️⃣ 如無法辨識將交由客服人工處理\n"
        "\n"
        "✅ 完成驗證即可解鎖專屬客服＆預約功能💖"
    )
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text=welcome_msg,
            quick_reply=QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="我同意規則", text="我同意規則"))
            ])
        )
    )
# ⭐ 只 import entrypoint（這會自動帶入各功能模組）
import hander.entrypoint
import hander.follow
import hander.image
