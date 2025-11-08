from flask import Blueprint, request, abort
from extensions import handler, ACCESS_TOKEN, CHANNEL_SECRET
from linebot.exceptions import InvalidSignatureError
import traceback

message_bp = Blueprint('message', __name__)

@message_bp.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    # 環境變數缺失時，extensions 啟用降級模式，直接回 OK 以避免 LINE 重試暴增
    if not ACCESS_TOKEN or not CHANNEL_SECRET:
        return "LINE not configured", 200
    if not signature:
        return "Missing signature", 400
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    except Exception as e:
        print("❗ callback 發生例外：", e)
        traceback.print_exc()
        return "Internal error", 500
    return "OK", 200

# ⭐ 只 import entrypoint（這會自動帶入各功能模組）
import hander.entrypoint
