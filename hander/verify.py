# -*- coding: utf-8 -*-
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageMessage, FollowEvent,
    QuickReply, QuickReplyButton, MessageAction, ImageSendMessage
)
from extensions import handler, line_bot_api, db
from models import Blacklist, Whitelist
from utils.temp_users import get_temp_user, set_temp_user, pop_temp_user
from hander.admin import ADMIN_IDS
from utils.menu_helpers import reply_with_menu
from utils.db_utils import update_or_create_whitelist_from_data
import re, time, os, shutil, secrets, logging
from datetime import datetime, timedelta
import pytz
from PIL import Image
import pytesseract

# ───────────────────────────────────────────────────────────────
# 全域設定
# ───────────────────────────────────────────────────────────────
VERIFY_CODE_EXPIRE = 900  # 驗證碼有效時間(秒)
OCR_DEBUG_IMAGE_BASEURL = os.getenv("OCR_DEBUG_IMAGE_BASEURL", "").rstrip("/")  # 例: https://your.cdn.com/ocr
OCR_DEBUG_IMAGE_DIR = os.getenv("OCR_DEBUG_IMAGE_DIR", "/tmp/ocr_debug")        # 需自行以靜態伺服器對外提供

# manual_verify_pending: {
#   target_user_id_or_placeholder: {
#       "phone": ...,
#       "line_id": ...,
#       "nickname": ...,
#       "code": ...,
#       "initiated_by_admin": admin_id,
#       "created_at": datetime,
#       "code_verified": False,
#       "code_verified_at": None,
#       "allow_user_confirm_until": None,
#   }
# }
manual_verify_pending = {}

# admin_manual_flow: store admin-side multi-step temp state
# { admin_id: {"step": "awaiting_phone"/"awaiting_lineid", "nickname": ..., "phone": ...} }
admin_manual_flow = {}

# ───────────────────────────────────────────────────────────────
# 小工具
# ───────────────────────────────────────────────────────────────
def normalize_phone(phone):
    phone = (phone or "").replace(" ", "").replace("-", "")
    if phone.startswith("+886"):
        return "0" + phone[4:]
    return phone

def make_qr(*labels_texts):
    """快速小工具：產生 QuickReply from tuples(label, text)"""
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label=lbl, text=txt))
        for (lbl, txt) in labels_texts
    ])

def reply_basic(event, text):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=text))

def reply_with_reverify(event, text):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text=text,
            quick_reply=make_qr(("重新驗證", "重新驗證"))
        )
    )

def reply_with_choices(event, text, choices):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=text, quick_reply=make_qr(*choices))
    )

def save_debug_image(temp_path, user_id):
    try:
        if not (OCR_DEBUG_IMAGE_BASEURL and OCR_DEBUG_IMAGE_DIR):
            return None
        os.makedirs(OCR_DEBUG_IMAGE_DIR, exist_ok=True)
        fname = f"{user_id}_{int(time.time())}.jpg"
        dest = os.path.join(OCR_DEBUG_IMAGE_DIR, fname)
        shutil.copyfile(temp_path, dest)
        return f"{OCR_DEBUG_IMAGE_BASEURL}/{fname}"
    except Exception:
        logging.exception("save_debug_image failed")
        return None

def generate_verification_code(length=8):
    return "".join(str(secrets.randbelow(10)) for _ in range(length))

def _find_pending_by_code(code):
    for key, pending in manual_verify_pending.items():
        if pending and pending.get("code") == code:
            return key, pending
    return None, None

# ───────────────────────────────────────────────────────────────
# 1) 加入好友：送歡迎訊息
# ───────────────────────────────────────────────────────────────
@handler.add(FollowEvent)
def handle_follow(event):
    welcome_msg = (
        "歡迎加入🍵茗殿🍵\n"
        "請正確按照步驟提供資料配合快速驗證\n\n"
        "➡️ 請輸入手機號碼進行驗證（含09開頭）"
    )
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=welcome_msg))

# ───────────────────────────────────────────────────────────────
# 管理員：發起手動驗證（多步）相關 helper
# ───────────────────────────────────────────────────────────────
def start_manual_verify_by_admin(admin_id, target_key, nickname, phone, line_id):
    code = None
    for _ in range(5):
        temp_code = generate_verification_code(8)
        found_key, found_pending = _find_pending_by_code(temp_code)
        if not found_pending:
            code = temp_code
            break
    if code is None:
        # fallback: always assign a code even if not unique
        code = generate_verification_code(8)

    tz = pytz.timezone("Asia/Taipei")
    manual_verify_pending[target_key] = {
        "phone": phone,
        "line_id": line_id,
        "nickname": nickname,
        "code": code,
        "initiated_by_admin": admin_id,
        "created_at": datetime.now(tz),
        "code_verified": False,
        "code_verified_at": None,
        "allow_user_confirm_until": None,
    }

    logging.info(f"manual_verify_pending created for {target_key} by admin {admin_id} (code={code})")
    return code

def admin_approve_manual_verify(admin_id, target_user_id):
    pending = manual_verify_pending.pop(target_user_id, None)
    if not pending:
        return False, "找不到待審核項目。"
    tz = pytz.timezone("Asia/Taipei")
    pending_data = {
        "phone": pending.get("phone"),
        "line_id": pending.get("line_id"),
        "name": pending.get("nickname"),
        "date": datetime.now(tz).strftime("%Y-%m-%d"),
    }
    record, _ = update_or_create_whitelist_from_data(pending_data, target_user_id, reverify=True)
    try:
        line_bot_api.push_message(target_user_id, TextSendMessage(text=(
            f"📱 {record.phone}\n"
            f"🌸 暱稱：{record.name or pending.get('nickname')}\n"
            f"🔗 LINE ID：{record.line_id or pending.get('line_id')}\n"
            f"🕒 {record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
            f"管理員已人工核准，驗證完成，歡迎加入。"
        )))
    except Exception:
        logging.exception("notify user after admin approve failed")
    try:
        line_bot_api.push_message(admin_id, TextSendMessage(text=f"已核准 {target_user_id}，寫入白名單：{record.phone}"))
    except Exception:
        logging.exception("notify admin after approve failed")
    return True, "已核准"

def admin_reject_manual_verify(admin_id, target_user_id):
    pending = manual_verify_pending.pop(target_user_id, None)
    if not pending:
        return False, "找不到待審核項目。"
    try:
        line_bot_api.push_message(target_user_id, TextSendMessage(text="管理員已拒絕您的手動驗證申請，請重新聯絡客服或重新申請。"))
    except Exception:
        logging.exception("notify user after admin reject failed")
    try:
        line_bot_api.push_message(admin_id, TextSendMessage(text=f"已拒絕 {target_user_id}"))
    except Exception:
        logging.exception("notify admin after reject failed")
    return True, "已拒絕"

# ───────────────────────────────────────────────────────────────
# 2) 文字訊息：手機 → LINE ID → 要截圖
# ───────────────────────────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    user_text = (event.message.text or "").strip()
    tz = pytz.timezone("Asia/Taipei")

    try:
        profile = line_bot_api.get_profile(user_id)
        display_name = profile.display_name
    except Exception:
        display_name = "用戶"

    # 管理員命令/流程優先處理
    if user_id in ADMIN_IDS:
        if user_text.startswith("手動驗證 - "):
            nickname = user_text.replace("手動驗證 - ", "").strip()
            admin_manual_flow[user_id] = {"step": "awaiting_phone", "nickname": nickname}
            reply_basic(event, f"開始手動驗證（暱稱：{nickname}）。請輸入手機號碼（09開頭）。")
            return

        if user_id in admin_manual_flow and admin_manual_flow[user_id].get("step") == "awaiting_phone":
            phone = normalize_phone(user_text)
            if not re.match(r"^09\d{8}$", phone):
                reply_basic(event, "請輸入正確的手機號（09開頭共10碼）。")
                return
            admin_manual_flow[user_id]["phone"] = phone
            admin_manual_flow[user_id]["step"] = "awaiting_lineid"
            reply_basic(event, "請輸入該使用者的 LINE ID（或輸入：尚未設定）。")
            return

        if user_id in admin_manual_flow and admin_manual_flow[user_id].get("step") == "awaiting_lineid":
            line_id = user_text.strip()
            phone = admin_manual_flow[user_id].get("phone")
            nickname = admin_manual_flow[user_id].get("nickname")
            if not phone:
                reply_basic(event, "發生錯誤：找不到先前輸入的手機號，請重新開始手動驗證流程。")
                admin_manual_flow.pop(user_id, None)
                return
            target_user_id = None
            for uid, data in temp_users.items():
                if data.get("phone") and normalize_phone(data.get("phone")) == normalize_phone(phone):
                    target_user_id = uid
                    break
            if not target_user_id:
                code = start_manual_verify_by_admin(user_id, phone, nickname, phone, line_id)
                admin_manual_flow.pop(user_id, None)
                reply_basic(event, f"找不到 temp_users 中的對應 user，但已建立手動驗證（暫存 key 為手機號）。\n已產生驗證碼：{code}\n請將驗證碼貼給使用者，以完成驗證。")
                return

            code = start_manual_verify_by_admin(user_id, target_user_id, nickname, phone, line_id)
            admin_manual_flow.pop(user_id, None)
            reply_basic(event, f"已產生驗證碼：{code}\n請將驗證碼貼給使用者 {target_user_id} 以完成驗證。")
            return

        if user_text.startswith("核准 "):
            parts = user_text.split(None, 1)
            if len(parts) < 2:
                reply_basic(event, "請指定要核准的 user_id，例如：核准 U1234567890")
                return
            target = parts[1].strip()
            ok, msg = admin_approve_manual_verify(user_id, target)
            reply_basic(event, msg)
            return

        if user_text.startswith("拒絕 "):
            parts = user_text.split(None, 1)
            if len(parts) < 2:
                reply_basic(event, "請指定要拒絕的 user_id，例如：拒絕 U1234567890")
                return
            target = parts[1].strip()
            ok, msg = admin_reject_manual_verify(user_id, target)
            reply_basic(event, msg)
            return

    # 非管理員 / 一般流程處理
    existing = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing:
        if user_text == "重新驗證":
            reply_with_reverify(event, "您已通過驗證，無法重新驗證。")
            return
        if normalize_phone(user_text) == normalize_phone(existing.phone):
            reply = (
                f"📱 {existing.phone}\n"
                f"🌸 暱稱：{existing.name or display_name}\n"
                f"       個人編號：{existing.id}\n"
                f"🔗 LINE ID：{existing.line_id or '未登記'}\n"
                f"🕒 {existing.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿\n"
                f"🌟 加入密碼：ming666"
            )
            reply_with_menu(event.reply_token, reply)
        else:
            reply_with_reverify(event, "⚠️ 已驗證，若要查看資訊請輸入您當時驗證的手機號碼。")
        return

    if user_text.startswith("查詢 - "):
        phone = normalize_phone(user_text.replace("查詢 - ", "").strip())
        msg = f"查詢號碼：{phone}\n查詢結果："
        wl = Whitelist.query.filter_by(phone=phone).first()
        if wl:
            msg += " O白名單\n"
            msg += (
                f"暱稱：{wl.name}\n"
                f"LINE ID：{wl.line_id or '未登記'}\n"
                f"驗證時間：{wl.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
            )
        else:
            msg += " X白名單\n"
        bl = Blacklist.query.filter_by(phone=phone).first()
        if bl:
            msg += " O黑名單\n"
            msg += (
                f"暱稱：{bl.name}\n"
                f"LINE ID：{getattr(bl, 'line_id', '未登記')}\n"
                f"加入時間：{bl.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S') if hasattr(bl, 'created_at') and bl.created_at else '未紀錄'}\n"
            )
        else:
            msg += " X黑名單\n"
        reply_basic(event, msg)
        return

    if user_text == "重新驗證":
        temp_users[user_id] = {"step": "waiting_phone", "name": display_name, "reverify": True}
        reply_basic(event, "請輸入您的手機號碼（09開頭）開始重新驗證～")
        return

    if re.match(r"^\d{8}$", user_text):
        pending = manual_verify_pending.get(user_id)
        pending_key = user_id
        if not pending:
            found_key, found_pending = _find_pending_by_code(user_text)
            if found_pending:
                manual_verify_pending[user_id] = found_pending
                if found_key != user_id:
                    manual_verify_pending.pop(found_key, None)
                pending = found_pending
                pending_key = user_id

        if pending and pending.get("code") == user_text:
            tz = pytz.timezone("Asia/Taipei")
            pending["code_verified"] = True
            pending["code_verified_at"] = datetime.now(tz)
            pending["allow_user_confirm_until"] = datetime.now(tz) + timedelta(minutes=5)
            confirm_msg = (
                f"📱 {pending.get('phone')}\n"
                f"🌸 暱稱： {pending.get('nickname')}\n"
                f"       個人編號： (驗證後產生)\n"
                f"🔗 LINE ID：{pending.get('line_id')}\n"
                f"🕒 {datetime.now(tz).strftime('%Y/%m/%d %H:%M:%S')}\n\n"
                "此為管理員手動驗證，如無誤請輸入 1 完成驗證（或等待管理員直接核准）。"
            )
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=confirm_msg,
                    quick_reply=make_qr(("完成驗證", "1"), ("重新驗證", "重新驗證"))
                )
            )
            return
    phone_candidate = normalize_phone(user_text)
    if not get_temp_user(user_id) and re.match(r"^09\d{8}$", phone_candidate):
        if Blacklist.query.filter_by(phone=phone_candidate).first():
            reply_basic(event, "❌ 請聯絡管理員，無法自動通過驗證流程。❌")
            return
        owner = Whitelist.query.filter_by(phone=phone_candidate).first()
        if owner and owner.line_user_id and owner.line_user_id != user_id:
            reply_basic(event, "❌ 此手機已綁定其他帳號，請聯絡客服協助。")
            return

        set_temp_user(user_id, {"step": "waiting_lineid", "name": display_name, "phone": phone_candidate})
        reply_basic(event, "✅ 手機號已登記～請輸入您的 LINE ID（未設定請輸入：尚未設定）")
        return

    tu = get_temp_user(user_id)
    if tu and tu.get("step") == "waiting_phone":
        phone = normalize_phone(user_text)
        if not re.match(r"^09\d{8}$", phone):
            reply_basic(event, "⚠️ 請輸入正確的手機號碼（09開頭共10碼）")
            return
        if Blacklist.query.filter_by(phone=phone).first():
            reply_basic(event, "❌ 請聯絡管理員，無法自動通過驗證流程。")
            pop_temp_user(user_id)
            return
        owner = Whitelist.query.filter_by(phone=phone).first()
        if owner and owner.line_user_id and owner.line_user_id != user_id:
            reply_basic(event, "❌ 此手機已綁定其他帳號，請聯絡客服協助。")
            return

        tu["phone"] = phone
        tu["step"] = "waiting_lineid"
        set_temp_user(user_id, tu)
        reply_basic(event, "✅ 手機號已登記～請輸入您的 LINE ID（未設定請輸入：尚未設定）")
        return

    tu = get_temp_user(user_id)
    if tu and tu.get("step") == "waiting_lineid":
        line_id = user_text.strip()
        if not line_id:
            reply_basic(event, "⚠️ 請輸入有效的 LINE ID（或輸入：尚未設定）")
            return
        tu["line_id"] = line_id
        tu["step"] = "waiting_screenshot"
        set_temp_user(user_id, tu)
        reply_basic(
            event,
            "📸 請上傳您的 LINE 個人頁面截圖\n"
            "👉 路徑：LINE主頁 > 右上角設定 > 個人檔案 > 點進去後截圖\n"
            "需清楚顯示 LINE 名稱與（若有）ID，作為驗證依據"
        )
        return

    if not get_temp_user(user_id):
        set_temp_user(user_id, {"step": "waiting_phone", "name": display_name})
        reply_basic(event, "歡迎～請直接輸入手機號碼（09開頭）進行驗證。")
        return

# ───────────────────────────────────────────────────────────────
# 3) 圖片訊息：OCR → 快速通關 / 資料有誤 顯示 OCR 圖片(或文字)
# ───────────────────────────────────────────────────────────────
@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    if user_id not in temp_users or temp_users[user_id].get("step") != "waiting_screenshot":
        reply_with_reverify(event, "請先完成前面步驟後再上傳截圖唷～")
        return

    message_content = line_bot_api.get_message_content(event.message.id)
    tmp_dir = "/tmp/ocr_inbox"
    os.makedirs(tmp_dir, exist_ok=True)
    temp_path = os.path.join(tmp_dir, f"{user_id}_{int(time.time())}.jpg")
    with open(temp_path, 'wb') as f:
        for chunk in message_content.iter_content():
            f.write(chunk)

    expected_line_id = (temp_users[user_id].get("line_id") or "").strip()
    try:
        image = Image.open(temp_path)
        ocr_text = pytesseract.image_to_string(image)
        ocr_text_low = (ocr_text or "").lower()

        def fast_pass():
            tz = pytz.timezone("Asia/Taipei")
            data = temp_users[user_id]
            now = datetime.now(tz)
            data["date"] = now.strftime("%Y-%m-%d")
            record, _ = update_or_create_whitelist_from_data(
                data, user_id, reverify=temp_users[user_id].get("reverify", False)
            )
            reply = (
                f"📱 {record.phone}\n"
                f"🌸 暱稱：{record.name or '用戶'}\n"
                f"🔗 LINE ID：{record.line_id or '未登記'}\n"
                f"🕒 {record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿\n"
                f"🌟 加入密碼：ming666"
            )
            reply_with_menu(event.reply_token, reply)
            temp_users.pop(user_id, None)

        # 修正：用 .strip().lower() 強化容錯
        if expected_line_id.strip().lower() in ["尚未設定", "未設定", "無", "none", "not set"]:
            fast_pass()
            return

        if expected_line_id and expected_line_id.strip().lower() in ocr_text_low:
            fast_pass()
            return

        public_url = save_debug_image(temp_path, user_id)
        preview_note = ""
        preview_msg = []
        if public_url:
            preview_note = "\n📷 這是我們辨識用的截圖預覽（僅你可見）："
            preview_msg.append(ImageSendMessage(original_content_url=public_url, preview_image_url=public_url))

        warn = (
            "⚠️ 截圖中的內容無法對上您剛輸入的 LINE ID。\n"
            "以下是 OCR 辨識到的重點文字（供你核對）：\n"
            "——— OCR ———\n"
            f"{ocr_text.strip()[:900] or '（無文字或辨識失敗）'}\n"
            "———————\n"
            "請選擇：重新上傳 / 重新輸入LINE ID / 重新驗證（從頭）。"
            f"{preview_note}"
        )
        temp_users[user_id]["step"] = "waiting_confirm_after_ocr"
        text_msg = TextSendMessage(
            text=warn,
            quick_reply=make_qr(
                ("重新上傳", "重新上傳"),
                ("重新輸入LINE ID", "重新輸入LINE ID"),
                ("重新驗證", "重新驗證")
            )
        )
        if preview_msg:
            line_bot_api.reply_message(event.reply_token, [text_msg] + preview_msg)
        else:
            line_bot_api.reply_message(event.reply_token, text_msg)

    except Exception:
        logging.exception("handle_image error")
        reply_with_reverify(event, "⚠️ 圖片處理失敗，請重新上傳或改由客服協助。")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

# ───────────────────────────────────────────────────────────────
# 4) OCR/手動驗證後的確認處理
# ───────────────────────────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessage)
def handle_post_ocr_confirm(event):
    user_id = event.source.user_id
    user_text = (event.message.text or "").strip()
    tz = pytz.timezone("Asia/Taipei")

    tu = get_temp_user(user_id)
    if tu and tu.get("step") in ("waiting_screenshot", "waiting_confirm_after_ocr") and user_text == "重新上傳":
        tu["step"] = "waiting_screenshot"
        set_temp_user(user_id, tu)
        reply_basic(event, "請重新上傳您的 LINE 個人頁面截圖（個人檔案按進去後請直接截圖）。")
        return True

    tu = get_temp_user(user_id)
    if tu and tu.get("step") == "waiting_confirm_after_ocr" and user_text == "重新輸入LINE ID":
        tu["step"] = "waiting_lineid"
        set_temp_user(user_id, tu)
        reply_basic(event, "請輸入新的 LINE ID（或輸入：尚未設定）。")
        return True

    if user_text == "重新驗證":
        try:
            profile = line_bot_api.get_profile(user_id)
            display_name = profile.display_name
        except Exception:
            tu = get_temp_user(user_id) or {}
            display_name = tu.get("name", "用戶")
        set_temp_user(user_id, {"step": "waiting_phone", "name": display_name, "reverify": True})
        reply_basic(event, "請輸入您的手機號碼（09開頭）開始重新驗證～")
        return True

    if user_text == "1":
        # 一般用戶 OCR 比對失敗後，step 為 waiting_confirm_after_ocr
        tu = get_temp_user(user_id)
        if tu and tu.get("step") == "waiting_confirm_after_ocr":
            tz = pytz.timezone("Asia/Taipei")
            data = tu
            now = datetime.now(tz)
            data["date"] = now.strftime("%Y-%m-%d")
            record, _ = update_or_create_whitelist_from_data(
                data, user_id, reverify=data.get("reverify", False)
            )
            reply = (
                f"📱 {record.phone}\n"
                f"🌸 暱稱：{record.name or '用戶'}\n"
                f"🔗 LINE ID：{record.line_id or '未登記'}\n"
                f"🕒 {record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿\n"
                f"🌟 加入密碼：ming666"
            )
            reply_with_menu(event.reply_token, reply)
            pop_temp_user(user_id)
            return True
        # 管理員人工驗證流程
        pending = manual_verify_pending.get(user_id)
        if pending and pending.get("code_verified"):
            until = pending.get("allow_user_confirm_until")
            now = datetime.now(tz)
            if until and now <= until:
                data = {
                    "phone": pending.get("phone"),
                    "line_id": pending.get("line_id"),
                    "name": pending.get("nickname"),
                    "date": now.strftime("%Y-%m-%d"),
                }
                record, _ = update_or_create_whitelist_from_data(
                    data, user_id, reverify=True
                )
                reply = (
                    f"📱 {record.phone}\n"
                    f"🌸 暱稱：{record.name or '用戶'}\n"
                    f"🔗 LINE ID：{record.line_id or '未登記'}\n"
                    f"🕒 {record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                    f"✅ 驗證成功，歡迎加入茗殿\n"
                    f"🌟 加入密碼：ming666"
                )
                reply_with_menu(event.reply_token, reply)
                manual_verify_pending.pop(user_id, None)
                pop_temp_user(user_id)
                return True
            else:
                manual_verify_pending.pop(user_id, None)
                reply_basic(event, "按 1 時限已過，請重新向管理員申請手動驗證或等待管理員核准。")
                return True
        reply_basic(event, "無效指令或無待處理的人工驗證。若要重新驗證請點「重新驗證」。")
        return True

    if re.match(r"^\d{8}$", user_text):
        pending = manual_verify_pending.get(user_id)
        if not pending:
            found_key, found_pending = _find_pending_by_code(user_text)
            if found_pending:
                manual_verify_pending[user_id] = found_pending
                if found_key != user_id:
                    manual_verify_pending.pop(found_key, None)
                pending = found_pending

        if pending and pending.get("code") == user_text:
            tz = pytz.timezone("Asia/Taipei")
            pending["code_verified"] = True
            pending["code_verified_at"] = datetime.now(tz)
            pending["allow_user_confirm_until"] = datetime.now(tz) + timedelta(minutes=5)
            confirm_msg = (
                f"📱 {pending.get('phone')}\n"
                f"🌸 暱稱： {pending.get('nickname')}\n"
                f"       個人編號： (驗證後產生)\n"
                f"🔗 LINE ID：{pending.get('line_id')}\n"
                f"🕒 {datetime.now(tz).strftime('%Y/%m/%d %H:%M:%S')}\n\n"
                "此為管理員手動驗證，如無誤請輸入 1 完成驗證。"
            )
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=confirm_msg,
                    quick_reply=make_qr(("完成驗證", "1"), ("重新驗證", "重新驗證"))
                )
            )
            return True

    return False

def handle_verify(event):
    try:
        if hasattr(event, "message") and event.message is not None:
            msg = event.message
            if isinstance(msg, TextMessage):
                try:
                    handled = handle_post_ocr_confirm(event)
                except Exception:
                    logging.exception("handle_post_ocr_confirm failed")
                    handled = False
                if handled:
                    return
                return handle_text(event)
            if isinstance(msg, ImageMessage):
                return handle_image(event)
        if isinstance(event, FollowEvent):
            return handle_follow(event)
        return handle_text(event)
    except Exception:
        logging.exception("handle_verify dispatch failed")
        try:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="系統發生錯誤，請稍後再試或聯絡管理員。"))
        except Exception:
            pass
        raise
