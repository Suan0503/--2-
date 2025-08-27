from linebot.models import MessageEvent, ImageMessage, TextSendMessage
from extensions import line_bot_api
from utils.image_verification import extract_lineid_phone, normalize_phone
from utils.temp_users import get_temp_user, set_temp_user, pop_temp_user  # 確認 utils/temp_users.py 有這三個函式
from utils.db_utils import update_or_create_whitelist_from_data
from datetime import datetime
import re
from utils.menu_helpers import reply_with_menu  # 只要這個

def handle_image(event):
    user_id = event.source.user_id
    print(f"[ImageHandler] Received image from user_id={user_id}")
    try:
        tu = get_temp_user(user_id)
        if not tu or tu.get("step") != "waiting_screenshot":
            print("[ImageHandler] Not in image verification flow, skip.")
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請先完成手機號與 LINE ID 驗證，再上傳截圖！"))
            return

        message_content = line_bot_api.get_message_content(event.message.id)
        image_path = f"/tmp/{user_id}_line_profile.png"
        with open(image_path, 'wb') as fd:
            for chunk in message_content.iter_content():
                fd.write(chunk)

        phone_ocr, lineid_ocr, ocr_text = extract_lineid_phone(image_path)
        input_phone = tu.get("phone")
        input_lineid = tu.get("line_id")
        record = tu

        phone_ocr_norm = normalize_phone(phone_ocr) if phone_ocr else None
        input_phone_norm = normalize_phone(input_phone) if input_phone else None

        # --- OCR 與手動輸入完全吻合且格式正確才自動通關 ---
        if (
            phone_ocr_norm and lineid_ocr
            and phone_ocr_norm == input_phone_norm
            and input_lineid is not None and lineid_ocr.lower() == input_lineid.lower()
            and re.match(r"^09\d{8}$", phone_ocr_norm)
            and len(lineid_ocr) >= 3 and len(lineid_ocr) <= 20 and re.match(r"^[A-Za-z0-9_\-\.]+$", lineid_ocr)
        ):
            now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            data = {
                "phone": record['phone'],
                "name": record['name'],
                "line_id": record['line_id'],
                "date": now_str,
                "reason": "OCR自動通過"
            }
            db_record, _ = update_or_create_whitelist_from_data(data, user_id)
            code = str(db_record.id) if getattr(db_record, "id", None) else "待驗證後產生"

            msg = (
                f"📱 {record['phone']}\n"
                f"🌸 暱稱：{record['name']}\n"
                f"       個人編號：{code}\n"
                f"🔗 LINE ID：{record['line_id']}\n"
                f"🕒 {now_str}\n"
                f"✅ 驗證成功，歡迎加入茗殿\n"
                f"🌟 加入密碼：ming666"
            )
            pop_temp_user(user_id)
            reply_with_menu(event.reply_token, msg)
            return

        # --- LINE ID 尚未設定時，僅允許 phone_ocr 完全正確且格式正確 ---
        if input_lineid == "尚未設定":
            if phone_ocr_norm == input_phone_norm and phone_ocr_norm and re.match(r"^09\d{8}$", phone_ocr_norm):
                reply = (
                    f"📱 {record['phone']}\n"
                    f"🌸 暱稱：{record['name']}\n"
                    f"       個人編號：待驗證後產生\n"
                    f"🔗 LINE ID：尚未設定\n"
                    f"請問以上資料是否正確？正確請回復 1\n"
                    f"⚠️輸入錯誤請從新輸入手機號碼即可⚠️"
                )
                record["step"] = "waiting_confirm"
                set_temp_user(user_id, record)
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            else:
                detect_phone = phone_ocr_norm or '未識別'
                detect_lineid = lineid_ocr or '未識別'
                msg = (
                    "❌ 截圖中的手機號碼或 LINE ID 與您輸入的不符，請重新上傳正確的 LINE 個人頁面截圖。\n"
                    f"【圖片偵測結果】\n手機:{detect_phone}\nLINE ID:{detect_lineid}"
                )
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
            return

        # --- 兩者都必須格式正確且完全吻合才能通過 ---
        lineid_match = (lineid_ocr is not None and input_lineid is not None and lineid_ocr.lower() == input_lineid.lower())
        if (
            phone_ocr_norm == input_phone_norm and phone_ocr_norm and re.match(r"^09\d{8}$", phone_ocr_norm)
            and (lineid_match or lineid_ocr == "尚未設定")
            and lineid_ocr and len(lineid_ocr) >= 3 and len(lineid_ocr) <= 20 and re.match(r"^[A-Za-z0-9_\-\.]+$", lineid_ocr)
        ):
            reply = (
                f"📱 {record['phone']}\n"
                f"🌸 暱稱：{record['name']}\n"
                f"       個人編號：待驗證後產生\n"
                f"🔗 LINE ID：{record['line_id']}\n"
                f"請問以上資料是否正確？正確請回復 1\n"
                f"⚠️輸入錯誤請從新輸入手機號碼即可⚠️"
            )
            record["step"] = "waiting_confirm"
            set_temp_user(user_id, record)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
            return

        # --- fallback: OCR 不符，顯示細節（合併為一則訊息）---
        detect_phone = phone_ocr_norm or '未識別'
        detect_lineid = lineid_ocr or '未識別'
        msg = (
            "❌ 截圖中的手機號碼或 LINE ID 與您輸入的不符，請重新上傳正確的 LINE 個人頁面截圖。\n"
            f"【圖片偵測結果】\n手機:{detect_phone}\nLINE ID:{detect_lineid}"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
    except Exception as e:
        print(f"[ImageHandler] Exception: {e}")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="系統錯誤，請重新上傳圖片或聯絡管理員。"))
