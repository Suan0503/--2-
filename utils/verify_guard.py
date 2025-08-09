from models import Whitelist
from linebot.models import TextSendMessage

def is_verified(user_id):
    """
    判斷用戶是否已通過白名單驗證
    :param user_id: LINE user id
    :return: True if verified, False otherwise
    """
    return Whitelist.query.filter_by(line_user_id=user_id).first() is not None

def guard_verified(event, line_bot_api):
    """
    驗證守門：未驗證者回應提示並終止流程，驗證者回傳True
    :param event: LINE event
    :param line_bot_api: line_bot_api 實例
    :return: True if verified, False otherwise
    """
    user_id = event.source.user_id
    if not is_verified(user_id):
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=(
                    "⚠️ 你尚未完成驗證，請輸入手機號碼進行驗證。\n\n"
                    "請於聊天視窗輸入您的手機號碼（例：0912345678），"
                    "將會收到驗證流程指示。"
                )
            )
        )
        return False
    return True
