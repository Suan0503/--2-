# -*- coding: utf-8 -*-
from linebot.models import (
    MessageEvent, ImageMessage, TextSendMessage, ImageSendMessage
)
from extensions import handler, line_bot_api
from utils.temp_users import get_temp_user, pop_temp_user
from utils.menu_helpers import reply_with_menu
import os
import time
import logging
from PIL import Image
import pytesseract

# 處理使用者上傳的圖片（OCR / 驗證流程用）
def handle_image(event):
    user_id = event.source.user_id
    tu = get_temp_user(user_id)

    # 使用流程檢查：若使用者不在等待上傳截圖的步驟，回覆提示
    if not tu or tu.get("step") != "waiting_screenshot":
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="請先完成前面步驟後再上傳截圖唷～")
            )
        except Exception:
            logging.exception("reply failed in handle_image (not waiting_screenshot)")
        return

    # 取得圖片內容並儲存到暫存檔
    try:
        message_content = line_bot_api.get_message_content(event.message.id)
    except Exception:
        logging.exception("failed to get message content")
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="無法取得圖片內容，請稍後再試。"))
        except Exception:
            pass
        return

    tmp_dir = "/tmp/ocr_inbox"
    os.makedirs(tmp_dir, exist_ok=True)
    temp_path = os.path.join(tmp_dir, f"{user_id}_{int(time.time())}.jpg")

    try:
        with open(temp_path, "wb") as f:
            for chunk in message_content.iter_content():
                f.write(chunk)
    except Exception:
        logging.exception("failed to write image to disk")
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="儲存圖片失敗，請重試。"))
        except Exception:
            pass
        return

    # 嘗試執行簡單的 OCR，如果你不需要可以把這段移除
    ocr_text = ""
    try:
        image = Image.open(temp_path)
        ocr_text = pytesseract.image_to_string(image) or ""
    except Exception:
        logging.exception("ocr failed (this is non-fatal)")

    # 構建回覆（這裡採用較保守的策略：將結果告知使用者並顯示可用的下一步）
    try:
        msg = (
            "我們已收到你的截圖，正在進行檢查。\n"
            "若 OCR 成功擷取到資訊，系統會自動處理；若失敗，請依指示重傳或聯絡客服。\n\n"
            "（以下為 OCR 摘要，供客服/使用者參考）\n"
            "——— OCR 摘要 ———\n"
            f"{ocr_text.strip()[:900] or '（無可辨識文字）'}\n"
            "————————\n"
            "若確認無誤請稍待系統處理，或回傳「重新上傳」以重傳截圖。"
        )
        # 使用 reply_with_menu 讓 UI 一致（此 helper 在專案其他處有使用）
        reply_with_menu(event.reply_token, msg)
    except Exception:
        logging.exception("reply_with_menu failed in handle_image")
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="處理完成，系統已收到圖片。"))
        except Exception:
            pass
    finally:
        # 清理暫存檔
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            logging.exception("failed to remove temp file in handle_image")
