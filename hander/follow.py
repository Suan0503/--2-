from extensions import line_bot_api
from linebot.models import TextSendMessage, QuickReply, QuickReplyButton, MessageAction

def handle_follow(event):
    user_id = event.source.user_id
    try:
        profile = line_bot_api.get_profile(user_id)
        display_name = profile.display_name
    except Exception:
        display_name = "用戶"
    welcome_text = (
        f"歡迎 {display_name} 加入🍵茗殿🍵\n\n"
        "完成驗證即可使用「選單功能」查詢各項服務。\n"
        "⚠️ 小助手不提供預約詢價，請洽專屬總機。\n"
        "📣 選單內有「廣告/活動頁」可參考最新方案。"
    )
    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="我同意，開始驗證", text="我同意規則"))
    ])
    line_bot_api.push_message(
        user_id,
        TextSendMessage(
            text=welcome_text,
            quick_reply=quick_reply
        )
    )
