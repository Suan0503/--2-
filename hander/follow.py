from linebot.models import FollowEvent, TextSendMessage
import logging
from extensions import line_bot_api as _default_line_bot_api

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handle_follow(event, line_bot_api=None):
    """
    處理 FollowEvent。
    接受兩種使用方式：
      - handle_follow(event)                          -> 使用 extensions.line_bot_api
      - handle_follow(event, line_bot_api=some_api)   -> 使用傳入的 line_bot_api（兼容 routes/message.py 的呼叫）
    """
    api = line_bot_api or _default_line_bot_api
    msg = (
        "歡迎加入茗殿小助手\n"
        "此為店家驗證機器人\n"
        "請依照每一步驟需要提供的資料輸入\n"
        "如果資料有誤請輸入『重新驗證』\n"
        "重新開啟驗證步驟\n\n"
        "由於是驗證機器人。請依照提示輸入資訊。不需要加入過多的字體符號。\n\n"
        "如果真的卡住無法通過出現異常。請不要封鎖。客服人員會一一回覆❤️\n"
        "📢📢📢📢\n\n"
        "第1️⃣步驟：請直接輸入手機號碼09XXXXXXXX\n"
    )
    try:
        api.reply_message(event.reply_token, TextSendMessage(text=msg))
    except Exception:
        logger.exception("回覆 FollowEvent 時發生錯誤")

def follow_step2(event, line_bot_api=None):
    api = line_bot_api or _default_line_bot_api
    msg = (
        "第2️⃣步驟：LineＩＤ的格式只有三種：\n"
        "❌ 請勿輸入line暱稱 ❌\n\n"
        "1。只需輸入英文數字（請勿加上id這兩個字)\n"
        "2。ID09XXXXXXXXX（請不要輸入任何符號或者空格)\n"
        "3。尚未設定（沒有設定ID者就打：尚未設定)\n"
    )
    try:
        api.reply_message(event.reply_token, TextSendMessage(text=msg))
    except Exception:
        logger.exception("回覆 Step2 時發生錯誤")

def follow_step3(event, line_bot_api=None):
    api = line_bot_api or _default_line_bot_api
    msg = (
        "第3️⃣步驟：附上個人檔案畫面截圖\n"
        "⚠️ 需完整。不要塗鴉/修改/剪裁/更改文字 ⚠️\n\n"
        "取得步驟：Line首頁>右上角『設定』>『個人檔案』。截圖\n"
        "(一樣丟圖片)\n"
    )
    try:
        api.reply_message(event.reply_token, TextSendMessage(text=msg))
    except Exception:
        logger.exception("回覆 Step3 時發生錯誤")

def follow_finish(event, line_bot_api=None):
    api = line_bot_api or _default_line_bot_api
    msg = (
        "⚠️⚠️⚠️ 這邊不是總機 ⚠️⚠️⚠️\n\n"
        "✅如果要預約。請直接輸入手機號碼開啟主選單✅\n\n"
        "步驟一：輸入手機號碼（09xxxxxxxx）\n"
        "步驟二：點選『預約諮詢』\n"
        "步驟三：加入總機\n"
        "（總機總共有本家 / 1️⃣館 / 2️⃣館 / 3️⃣館 / 4️⃣館 )\n\n"
        "❌請勿重複加入❌\n"
        "為了避免資訊重複或者時間落差。請勿重複加入並且重複傳送訊息。\n\n"
        "❤️如果有需要刪除總機的好友跟對話，可以再加入總機後索取該總機的QR碼保存❤️"
    )
    try:
        api.reply_message(event.reply_token, TextSendMessage(text=msg))
    except Exception:
        logger.exception("回覆驗證完成時發生錯誤")
    try:
        api.reply_message(event.reply_token, TextSendMessage(text=msg))
    except Exception:
        logger.exception("回覆 FollowEvent 時發生錯誤")
