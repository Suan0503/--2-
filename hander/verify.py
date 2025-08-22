from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageMessage,
    QuickReply, QuickReplyButton, MessageAction
)
from extensions import handler, line_bot_api, db
from models import Blacklist, Whitelist
from utils.temp_users import temp_users
from hander.admin import ADMIN_IDS
from utils.menu_helpers import reply_with_menu
from utils.db_utils import update_or_create_whitelist_from_data
import re, time, os
from datetime import datetime
import pytz
from PIL import Image
import pytesseract

manual_verify_pending = {}

VERIFY_CODE_EXPIRE = 900  # 驗證碼有效時間(秒)

def normalize_phone(phone):
    phone = (phone or "").replace(" ", "").replace("-", "")
    if phone.startswith("+8869"):
        return "0" + phone[4:]
    if phone.startswith("+886"):
        return "0" + phone[4:]
    return phone

def quick_reply_reverify(text):
    return TextSendMessage(
        text=text,
        quick_reply=QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="重新驗證", text="重新驗證"))
        ])
    )

def reply_with_reverify(event, text):
    line_bot_api.reply_message(
        event.reply_token,
        quick_reply_reverify(text)
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_verify(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    tz = pytz.timezone("Asia/Taipei")
    try:
        profile = line_bot_api.get_profile(user_id)
        display_name = profile.display_name
    except Exception:
        display_name = "用戶"

    # --- 新增：若使用者尚未在 temp_users，但訊息本身就是手機，直接當作 Step1 處理 ---
    phone_candidate = normalize_phone(user_text)
    if user_id not in temp_users and re.match(r"^09\d{8}$", phone_candidate):
        # 若已驗證過（以 line_user_id 判斷），回覆已驗證訊息
        if Whitelist.query.filter_by(line_user_id=user_id).first():
            reply_with_reverify(event, "您已通過驗證，無需再次輸入手機。")
            return
        # 若在黑名單，拒絕
        if Blacklist.query.filter_by(phone=phone_candidate).first():
            reply_with_reverify(event, "❌ 請聯絡管理員，無法自動通過驗證流程。")
            return
        # 直接記錄並進到等待 LINE ID 的步驟
        temp_users[user_id] = {"step": "waiting_lineid", "name": display_name, "phone": phone_candidate}
        reply_with_reverify(event, "✅ 手機號已登記～請輸入您的 LINE ID（未設定請輸入 尚未設定）")
        return
    # --- End 新增 ---

    # 查詢模組
    if user_text.startswith("查詢 - "):
        phone = normalize_phone(user_text.replace("查詢 - ", "").strip())
        msg = f"查詢號碼：{phone}\n查詢結果："
        # 查白名單
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
        # 查黑名單
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
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return

    # 管理員手動黑名單流程
    if user_text.startswith("手動黑名單 - "):
        if user_id not in ADMIN_IDS:
            reply_with_reverify(event, "❌ 只有管理員可使用此功能")
            return
        parts = user_text.split(" - ", 1)
        if len(parts) == 2 and parts[1]:
            temp_users[user_id] = {"blacklist_step": "wait_phone", "name": parts[1]}
            reply_with_reverify(event, "請輸入該用戶的手機號碼")
        else:
            reply_with_reverify(event, "格式錯誤，請用：手動黑名單 - 暱稱")
        return

    if user_id in temp_users and temp_users[user_id].get("blacklist_step") == "wait_phone":
        phone = normalize_phone(user_text)
        if user_text == "取消":
            temp_users.pop(user_id)
            reply_with_reverify(event, "❌ 已取消黑名單流程。")
            return
        if not phone or not phone.startswith("09") or len(phone) != 10:
            reply_with_reverify(event, "請輸入正確的手機號碼（09xxxxxxxx）\n或輸入「取消」結束流程。")
            return
        temp_users[user_id]['phone'] = phone
        temp_users[user_id]['blacklist_step'] = "confirm"
        reply_with_reverify(
            event,
            (
                f"暱稱：{temp_users[user_id]['name']}\n"
                f"手機號：{phone}\n"
                f"確認加入黑名單？正確請回覆 1\n"
                f"⚠️ 如有誤請重新輸入手機號碼，或輸入「取消」結束流程 ⚠️"
            )
        )
        return

    if user_id in temp_users and temp_users[user_id].get("blacklist_step") == "confirm":
        if user_text == "1":
            info = temp_users[user_id]
            record = Blacklist.query.filter_by(phone=info['phone']).first()
            if not record:
                record = Blacklist(
                    phone=info['phone'],
                    name=info['name']
                )
                db.session.add(record)
                db.session.commit()
                reply = (
                    f"✅ 已將手機號 {info['phone']} (暱稱：{info['name']}) 加入黑名單！"
                )
            else:
                reply = (
                    f"⚠️ 手機號 {info['phone']} 已在黑名單名單中。"
                )
            reply_with_reverify(event, reply)
            temp_users.pop(user_id)
            return
        elif user_text == "取消":
            temp_users.pop(user_id)
            reply_with_reverify(event, "❌ 已取消黑名單流程。")
            return
        else:
            temp_users[user_id]['blacklist_step'] = "wait_phone"
            reply_with_reverify(
                event,
                "⚠️ 如果資料正確請回覆 1，錯誤請重新輸入手機號碼。\n或輸入「取消」結束流程。"
            )
            return

    # 管理員手動驗證白名單流程
    if user_text.startswith("手動驗證 - "):
        if user_id not in ADMIN_IDS:
            reply_with_reverify(event, "❌ 只有管理員可使用此功能")
            return
        parts = user_text.split(" - ", 1)
        if len(parts) == 2 and parts[1]:
            temp_users[user_id] = {"manual_step": "wait_lineid", "name": parts[1]}
            reply_with_reverify(event, "請輸入該用戶的 LINE ID")
        else:
            reply_with_reverify(event, "格式錯誤，請用：手動驗證 - 暱稱")
        return

    if user_id in temp_users and temp_users[user_id].get("manual_step") == "wait_lineid":
        if not user_text:
            reply_with_reverify(event, "請輸入正確的 LINE ID")
            return
        temp_users[user_id]['line_id'] = user_text
        temp_users[user_id]['manual_step'] = "wait_phone"
        reply_with_reverify(event, "請輸入該用戶的手機號碼")
        return

    if user_id in temp_users and temp_users[user_id].get("manual_step") == "wait_phone":
        phone = normalize_phone(user_text)
        if not phone or not phone.startswith("09") or len(phone) != 10:
            reply_with_reverify(event, "請輸入正確的手機號碼（09xxxxxxxx）")
            return
        temp_users[user_id]['phone'] = phone
        code = str(int(time.time()))[-8:]
        manual_verify_pending[code] = {
            'name': temp_users[user_id]['name'],
            'line_id': temp_users[user_id]['line_id'],
            'phone': temp_users[user_id]['phone'],
            'create_ts': int(time.time()),
            'admin_id': user_id,
            'step': 'wait_user_input'
        }
        del temp_users[user_id]
        reply_with_reverify(event, f"驗證碼產生：{code}\n請將此8位驗證碼自行輸入聊天室")
        return

    if user_text in manual_verify_pending:
        info = manual_verify_pending[user_text]
        now_ts = int(time.time())
        if now_ts - info['create_ts'] > VERIFY_CODE_EXPIRE:
            del manual_verify_pending[user_text]
            reply_with_reverify(event, "驗證碼已過期，請重新申請。")
            return
        temp_users[user_id] = {
            "phone": info["phone"],
            "name": info["name"],
            "line_id": info["line_id"],
            "step": "waiting_manual_confirm"
        }
        reply_msg = (
            f"📱 手機號碼：{info['phone']}\n"
            f"🌸 暱稱：{info['name']}\n"
            f"       個人編號：待驗證後產生\n"
            f"🔗 LINE ID：{info['line_id']}\n"
            f"（此用戶為手動通過）\n"
            f"請問以上資料是否正確？正確請回復 1\n"
            f"⚠️輸入錯誤請重新輸入手機號碼即可⚠️"
        )
        reply_with_reverify(event, reply_msg)
        del manual_verify_pending[user_text]
        return

    if user_id in temp_users and temp_users[user_id].get("step") == "waiting_manual_confirm":
        if user_text == "1":
            info = temp_users[user_id]
            record = Whitelist.query.filter_by(phone=info['phone']).first()
            is_new = False
            if record:
                updated = False
                if not record.line_id:
                    record.line_id = info['line_id']
                    updated = True
                if not record.name:
                    record.name = info['name']
                    updated = True
                if updated:
                    db.session.commit()
            else:
                record = Whitelist(
                    phone=info['phone'],
                    name=info['name'],
                    line_id=info['line_id'],
                    line_user_id=user_id
                )
                db.session.add(record)
                db.session.commit()
                is_new = True
            reply = (
                f"📱 {record.phone}\n"
                f"🌸 暱稱：{record.name}\n"
                f"       個人編號：{record.id}\n"
                f"🔗 LINE ID：{record.line_id}\n"
                f"✅ 驗證成功，歡迎加入茗殿\n"
                f"🌟 加入密碼：ming666"
            )
            reply_with_menu(event.reply_token, reply)
            temp_users.pop(user_id)
            return
        else:
            reply_with_reverify(event, "⚠️ 如果資料正確請回覆 1，錯誤請重新輸入手機號碼。")
            return

    if user_text == "查詢手動驗證":
        if user_id not in ADMIN_IDS:
            reply_with_reverify(event, "❌ 只有管理員可使用此功能")
            return
        msg = "【待用戶輸入驗證碼名單】\n"
        for code, info in manual_verify_pending.items():
            msg += f"暱稱:{info['name']} LINE ID:{info['line_id']} 手機:{info['phone']} 驗證碼:{code}\n"
        if not manual_verify_pending:
            msg += "目前無待驗證名單"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return

    # 已驗證用戶不可使用重新驗證
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
            reply_with_reverify(event, "⚠️ 你已驗證完成，請輸入手機號碼查看驗證資訊")
        return

    # 新用戶允許重新驗證（保留使用者主動輸入「重新驗證」）
    if user_text == "重新驗證":
        temp_users[user_id] = {"step": "waiting_phone", "name": display_name, "reverify": True}
        reply_with_reverify(event, "請輸入您的手機號碼（09開頭）開始重新驗證～")
        return

    # Step 1: 輸入手機號碼 (for users already in temp_users waiting_phone)
    if user_id in temp_users and temp_users[user_id].get("step") == "waiting_phone":
        phone = normalize_phone(user_text)
        if Blacklist.query.filter_by(phone=phone).first():
            reply_with_reverify(event, "❌ 請聯絡管理員，無法自動通過驗證流程。")
            temp_users.pop(user_id)
            return
        if not phone or not phone.startswith("09") or len(phone) != 10:
            reply_with_reverify(event, "⚠️ 請輸入正確的手機號碼（09開頭共10碼）")
            return
        temp_users[user_id]["phone"] = phone
        temp_users[user_id]["step"] = "waiting_lineid"
        reply_with_reverify(event, "✅ 手機號已登記～請輸入您的 LINE ID（未設定請輸入 尚未設定）")
        return

    # Step 2: 輸入 LINE ID (for users in temp_users waiting_lineid)
    if user_id in temp_users and temp_users[user_id].get("step") == "waiting_lineid":
        line_id = user_text
        if not line_id:
            reply_with_reverify(event, "⚠️ 請輸入有效的 LINE ID（或輸入 尚未設定）")
            return
        temp_users[user_id]["line_id"] = line_id
        temp_users[user_id]["step"] = "waiting_screenshot"
        reply_with_reverify(
            event,
            "📸 請上傳您的 LINE 個人頁面截圖\n"
            "👉 路徑：LINE主頁 > 右上角設定 > 個人檔案 > 點進去後截圖\n"
            "需清楚顯示 LINE 名稱與 ID，作為驗證依據"
        )
        return

    # Step 3: 圖片驗證確認後用戶輸入 1
    if user_id in temp_users and temp_users[user_id].get("step") == "waiting_confirm" and user_text == "1":
        data = temp_users[user_id]
        now = datetime.now(tz)
        data["date"] = now.strftime("%Y-%m-%d")
        # 呼叫 db_utils 進行建立或更新，帶入 reverify flag 若有
        record, is_new = update_or_create_whitelist_from_data(
            data, user_id, reverify=temp_users[user_id].get("reverify", False)
        )
        reply = (
            f"📱 {record.phone}\n"
            f"🌸 暱稱：{record.name or display_name}\n"
            f"🔗 LINE ID：{record.line_id or '未登記'}\n"
            f"🕒 {record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
            f"✅ 驗證成功，歡迎加入茗殿\n"
            f"🌟 加入密碼：ming666"
        )
        reply_with_menu(event.reply_token, reply)
        temp_users.pop(user_id)
        return

    # fallback: 直接啟動驗證流程（移除顯示「我同意規則」按鈕）
    if user_id not in temp_users:
        temp_users[user_id] = {"step": "waiting_phone", "name": display_name}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"歡迎 {display_name}，請直接輸入手機號碼（09開頭）進行驗證。")
        )
        return

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    if user_id not in temp_users or temp_users[user_id].get("step") != "waiting_screenshot":
        reply_with_reverify(event, "請先完成前面步驟後再上傳截圖唷～")
        return

    # 儲存圖片檔案
    message_content = line_bot_api.get_message_content(event.message.id)
    temp_path = f"/tmp/{user_id}_profile.jpg"
    with open(temp_path, 'wb') as f:
        for chunk in message_content.iter_content():
            f.write(chunk)

    # OCR 辨識
    try:
        image = Image.open(temp_path)
        text = pytesseract.image_to_string(image, lang='eng')
        if re.search(r"09\d{8}", text):
            temp_users[user_id]["step"] = "waiting_confirm"
            reply_with_reverify(event, "✅ 圖片已成功辨識！請回覆「1」完成驗證。")
        else:
            reply_with_reverify(event, "❌ 無法辨識手機號碼，請確認圖片清晰度或改由人工處理。")
    except Exception:
        reply_with_reverify(event, "⚠️ 圖片處理失敗，請重新上傳或改由客服協助。")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
