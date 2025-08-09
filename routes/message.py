from flask import Blueprint, request, abort
from extensions import handler
from linebot.exceptions import InvalidSignatureError
import traceback

message_bp = Blueprint('message', __name__)

@message_bp.route("/callback", methods=["POST"])
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

# ⭐ 只 import entrypoint（這會自動帶入各功能模組）
import hander.entrypoint
