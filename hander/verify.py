from linebot.models import MessageEvent, TextMessage, TextSendMessage
from extensions import handler, line_bot_api, db
from models import Whitelist, Blacklist
from utils.menu import get_menu_carousel
from utils.db_utils import update_or_create_whitelist_from_data
from utils.temp_users import temp_users, manual_verify_pending
import re
from datetime import datetime
import pytz

def normalize_phone(phone):
    phone = (phone or "").replace(" ", "").replace("-", "")
    if phone.startswith("+8869"):
        return "0" + phone[4:]
    if phone.startswith("+886"):
        return "0" + phone[4:]
    return phone

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

    # ==== 手動驗證流程優先判斷 ====
    # 如果正在進行手動驗證流程
    if user_id in temp_users and temp_users[user_id].get("step") == "waiting_confirm":
        # 只要是"1"就通過
        if user_text == "1":
            data = temp_users[user_id]
            now = datetime.now(tz)
            data["date"] = now.strftime("%Y-%m-%d")
            record, is_new = update_or_create_whitelist_from_data(data, user_id)
            if is_new:
                reply = (
                    f"📱 {data['phone']}\n"
                    f"🌸 暱稱：{data['name']}\n"
                    f"       個人編號：{record.id}\n"
                    f"🔗 LINE ID：{data['line_id']}\n"
                    f"🕒 {record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                    f"✅ 驗證成功，歡迎加入茗殿\n"
                    f"🌟 加入密碼：ming666"
                )
            else:
                reply = (
                    f"📱 {record.phone}\n"
                    f"🌸 暱稱：{record.name or data.get('name')}\n"
                    f"       個人編號：{record.id}\n"
                    f"🔗 LINE ID：{record.line_id or data.get('line_id')}\n"
                    f"🕒 {record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                    f"✅ 你的資料已補全，歡迎加入茗殿\n"
                    f"🌟 加入密碼：ming666"
                )
            line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply), get_menu_carousel()])
            temp_users.pop(user_id)
            return
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 如果資料正確請回覆 1，錯誤請重新輸入手機號碼。"))
            return

    # === 補回已驗證用戶再次輸入手機號的判斷 ===
    existing = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing:
        # 用戶已驗證
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
            line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply), get_menu_carousel()])
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 你已驗證完成，請輸入手機號碼查看驗證資訊"))
        return

    # 手機號碼驗證
    if re.match(r"^09\d{8}$", user_text):
        black = Blacklist.query.filter_by(phone=user_text).first()
        if black:
            return
        repeated = Whitelist.query.filter_by(phone=user_text).first()
        data = {"phone": user_text, "name": display_name}
        if repeated and repeated.line_user_id:
            update_or_create_whitelist_from_data(data)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ 此手機號碼已被使用，已補全缺失資料。")
            )
            return
        temp_users[user_id] = {"phone": user_text, "name": display_name, "step": "waiting_lineid"}
        line_bot_api.reply_message(
            event.reply_token,
            [
                TextSendMessage(text="📱 手機已登記囉～請接著輸入您的 LINE ID"),
                TextSendMessage(
                    text=(
                        "若您有設定 LINE ID → ✅ 直接輸入即可\n"
                        "若尚未設定 ID → 請輸入：「尚未設定」\n"
                        "若您的 LINE ID 是手機號碼本身（例如 09xxxxxxxx）→ 請在開頭加上「ID」兩個字\n"
                        "例如：ID 0912345678"
                    )
                )
            ]
        )
        return

    # 填寫 LINE ID
    if user_id in temp_users and temp_users[user_id].get("step", "waiting_lineid") == "waiting_lineid" and len(user_text) >= 2:
        record = temp_users[user_id]
        input_lineid = user_text.strip()
        if input_lineid.lower().startswith("id"):
            phone_candidate = re.sub(r"[^\d]", "", input_lineid)
            if re.match(r"^id\s*09\d{8}$", input_lineid.lower().replace(" ", "")):
                record["line_id"] = phone_candidate
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="❌ 請輸入正確格式：ID 09xxxxxxxx（例如：ID 0912345678）")
                )
                return
        elif input_lineid in ["尚未設定", "無ID", "無", "沒有", "未設定"]:
            record["line_id"] = "尚未設定"
        else:
            record["line_id"] = input_lineid
        record["step"] = "waiting_screenshot"
        temp_users[user_id] = record

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=(
                    "請上傳您的 LINE 個人頁面截圖（需清楚顯示手機號與 LINE ID）以供驗證。\n"
                    "📸 操作教學：LINE主頁 > 右上角設定 > 個人檔案（點進去之後截圖）"
                )
            )
        )
        return

    # 最後確認（for 圖片驗證流程）
    if user_text == "1" and user_id in temp_users and temp_users[user_id].get("step") == "waiting_confirm":
        data = temp_users[user_id]
        now = datetime.now(tz)
        data["date"] = now.strftime("%Y-%m-%d")
        record, is_new = update_or_create_whitelist_from_data(data, user_id)
        if is_new:
            reply = (
                f"📱 {data['phone']}\n"
                f"🌸 暱稱：{data['name']}\n"
                f"       個人編號：{record.id}\n"
                f"🔗 LINE ID：{data['line_id']}\n"
                f"🕒 {record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿\n"
                f"🌟 加入密碼：ming666"
            )
        else:
            reply = (
                f"📱 {record.phone}\n"
                f"🌸 暱稱：{record.name or data.get('name')}\n"
                f"       個人編號：{record.id}\n"
                f"🔗 LINE ID：{record.line_id or data.get('line_id')}\n"
                f"🕒 {record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 你的資料已補全，歡迎加入茗殿\n"
                f"🌟 加入密碼：ming666"
            )
        line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply), get_menu_carousel()])
        temp_users.pop(user_id)
        return

    # fallback：尚未驗證
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入手機號碼進行驗證。"))
    return
