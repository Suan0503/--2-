from linebot.models import TextSendMessage
from extensions import line_bot_api
from storage import ADMIN_IDS

def handle_admin(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    if user_id in ADMIN_IDS and user_text.startswith("/msg "):
        try:
            parts = user_text.split(" ", 2)
            if len(parts) < 3:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text="格式錯誤，請用 /msg <user_id> <內容>"))
                return
            target_user_id = parts[1].strip()
            msg = parts[2].strip()
            line_bot_api.push_message(target_user_id, TextSendMessage(text=f"【管理員回覆】\n{msg}"))
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="已發送訊息給用戶"))
        except Exception as e:
            print("管理員私訊失敗：", e)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="發送失敗，請檢查 user_id 是否正確"))
        return
