# -*- coding: utf-8 -*-
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageMessage, FollowEvent,
    QuickReply, QuickReplyButton, MessageAction, ImageSendMessage
)
from extensions import handler, line_bot_api, db
from models import Blacklist, Whitelist, TempVerify, StoredValueWallet, StoredValueTransaction
from utils.temp_users import get_temp_user, set_temp_user, pop_temp_user

# 補助：取得所有暫存用戶（僅限 dict 模式）
def get_all_temp_users():
    try:
        from utils.temp_users import temp_users
        return temp_users.items()
    except Exception:
        return []
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

# 驗證完成後的追加說明（同步推送）
EXTRA_NOTICE = (
    "\n\n"
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

def maybe_push_coupon_expiry_notice(user_id):
    """在 12/10~12/31 期間，針對已驗證用戶每日第一次顯示折價券到期提醒。"""
    try:
        wl = Whitelist.query.filter_by(line_user_id=user_id).first()
        if not wl:
            return
        wallet = StoredValueWallet.query.filter_by(phone=wl.phone).first()
        if not wallet:
            return
        tz = pytz.timezone("Asia/Taipei")
        now_dt = datetime.now(tz)
        notice_start = tz.localize(datetime(now_dt.year, 12, 10, 0, 0, 0))
        expire_dt = tz.localize(datetime(now_dt.year, 12, 31, 23, 59, 59))
        if not (notice_start <= now_dt <= expire_dt):
            return
        q = StoredValueTransaction.query.filter_by(wallet_id=wallet.id).all()
        c500 = c300 = c100 = 0
        for t in q:
            sign = 1 if t.type == 'topup' else -1
            c500 += sign * (t.coupon_500_count or 0)
            c300 += sign * (t.coupon_300_count or 0)
            c100 += sign * (getattr(t, 'coupon_100_count', 0) or 0)
        c500 = max(c500, 0)
        c300 = max(c300, 0)
        c100 = max(c100, 0)
        if c500 <= 0 and c300 <= 0 and c100 <= 0:
            return
        last = wallet.last_coupon_notice_at
        show_notice = False
        if not last:
            show_notice = True
        else:
            last_local = last.astimezone(tz)
            show_notice = last_local.date() < now_dt.date()
        if not show_notice:
            return
        msg = (
            f"提醒：您的折價券將於 {expire_dt.strftime('%Y/%m/%d')} 到期。\n"
            f"目前剩餘：500券 x {c500}、300券 x {c300}、100券 x {c100}"
        )
        try:
            line_bot_api.push_message(user_id, TextSendMessage(text=msg))
        except Exception:
            pass
        wallet.last_coupon_notice_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    except Exception:
        logging.exception("maybe_push_coupon_expiry_notice failed")

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
    """將使用者上傳的截圖複製到 DEBUG 目錄並回傳可公開檢視的 URL。失敗則回傳 None。"""
    try:
        if not (OCR_DEBUG_IMAGE_BASEURL and OCR_DEBUG_IMAGE_DIR):
            return None
        os.makedirs(OCR_DEBUG_IMAGE_DIR, exist_ok=True)
        filename = f"{user_id}_{int(time.time())}.jpg"
        dest = os.path.join(OCR_DEBUG_IMAGE_DIR, filename)
        shutil.copy(temp_path, dest)
        return f"{OCR_DEBUG_IMAGE_BASEURL}/{filename}"
    except Exception:
        logging.exception("save_debug_image failed")
        return None

# ───────────────────────────────────────────────────────────────
# TempVerify / Manual verify helpers (遺失函式補回)
# ───────────────────────────────────────────────────────────────
def upsert_tempverify(phone, line_id=None, nickname=None, line_user_id=None):
    """以 phone 為 key upsert temp_verify 資料，供後台待驗證列表顯示。"""
    try:
        phone_n = normalize_phone(phone)
        rec = TempVerify.query.filter_by(phone=phone_n).first()
        if not rec:
            rec = TempVerify()
            rec.phone = phone_n
            db.session.add(rec)
        # 更新欄位
        if line_id is not None:
            rec.line_id = line_id
        if nickname is not None:
            rec.nickname = nickname
        if line_user_id is not None:
            rec.line_user_id = line_user_id
        if not rec.status:
            rec.status = "pending"
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    except Exception:
        logging.exception("upsert_tempverify failed")

def mark_tempverify_verified_by_phone(phone):
    try:
        phone_n = normalize_phone(phone)
        rec = TempVerify.query.filter_by(phone=phone_n).first()
        if rec:
            rec.status = "verified"
            db.session.commit()
    except Exception:
        db.session.rollback()
        logging.exception("mark_tempverify_verified_by_phone failed")

def mark_tempverify_failed_by_phone(phone):
    try:
        phone_n = normalize_phone(phone)
        rec = TempVerify.query.filter_by(phone=phone_n).first()
        if rec:
            rec.status = "failed"
            db.session.commit()
    except Exception:
        db.session.rollback()
        logging.exception("mark_tempverify_failed_by_phone failed")

def _find_pending_by_code(code):
    """在 manual_verify_pending 中尋找指定驗證碼。回傳 (key, pending_dict) 或 (None, None)。"""
    for k, v in manual_verify_pending.items():
        if v.get("code") == code:
            return k, v
    return None, None

def start_manual_verify_by_admin(admin_id, target_user_id_or_placeholder, nickname, phone, line_id):
    """建立管理員手動驗證流程，回傳產生的 8 位數驗證碼。target_user_id_or_placeholder 若尚未有實際 user id 可用手機暫代。"""
    code = f"{secrets.randbelow(10**8):08d}"
    tz = pytz.timezone("Asia/Taipei")
    pending = {
        "phone": normalize_phone(phone),
        "line_id": line_id,
        "nickname": nickname,
        "code": code,
        "initiated_by_admin": admin_id,
        "created_at": datetime.now(tz),
        "code_verified": False,
        "code_verified_at": None,
        "allow_user_confirm_until": None,
    }
    manual_verify_pending[target_user_id_or_placeholder] = pending
    # 讓後台可見
    try:
        upsert_tempverify(phone=pending["phone"], line_id=line_id, nickname=nickname, line_user_id=(target_user_id_or_placeholder if str(target_user_id_or_placeholder).startswith("U") else None))
    except Exception:
        logging.exception("upsert_tempverify in start_manual_verify_by_admin failed")
    return code

def admin_approve_manual_verify(admin_id, target_user_id):
    """管理員核准手動驗證。"""
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
        mark_tempverify_verified_by_phone(record.phone)
    except Exception:
        logging.exception("mark_tempverify_verified_by_phone (admin approve) failed")
    # 推送給使用者
    try:
        msg = (
            f"📱 {record.phone}\n"
            f"🌸 暱稱：{record.name or pending.get('nickname')}\n"
            f"🔗 LINE ID：{record.line_id or pending.get('line_id')}\n"
            f"🕒 {record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
            f"管理員已人工核准，驗證完成，歡迎加入。"
        ) + EXTRA_NOTICE
        line_bot_api.push_message(target_user_id, TextSendMessage(text=msg))
    except Exception:
        logging.exception("notify user after admin approve failed")
    # 回覆管理員
    try:
        line_bot_api.push_message(admin_id, TextSendMessage(text=f"已核准 {target_user_id}，寫入白名單：{record.phone}"))
    except Exception:
        logging.exception("notify admin after approve failed")
    return True, "已核准"

def handle_follow(event):
    """使用者加入好友事件：初始化暫存狀態並提示輸入手機。"""
    try:
        user_id = event.source.user_id
        profile_name = None
        try:
            profile = line_bot_api.get_profile(user_id)
            profile_name = profile.display_name
        except Exception:
            pass
        display_name = profile_name or "用戶"
        set_temp_user(user_id, {"step": "waiting_phone", "name": display_name, "nickname": display_name, "user_id": user_id, "line_user_id": user_id})
        reply_basic(event, "歡迎加入～現在請直接輸入手機號碼（09開頭，共10碼），不要加其它文字。")
    except Exception:
        logging.exception("handle_follow failed")

def admin_reject_manual_verify(admin_id, target_user_id):
    pending = manual_verify_pending.pop(target_user_id, None)
    if not pending:
        return False, "找不到待審核項目。"
    try:
        mark_tempverify_failed_by_phone(pending.get("phone"))
    except Exception:
        logging.exception("mark_tempverify_failed_by_phone (admin reject) failed")
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
    logging.info(f"[handle_text] user_id={user_id} 收到 user_text={user_text}")
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
            for uid, data in get_all_temp_users():
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
    def reply_wallet(wl):
        from linebot.models import FlexSendMessage
        wallet = StoredValueWallet.query.filter_by(phone=wl.phone).first()
        if not wallet:
            reply_basic(event, f"目前無錢包資料（手機：{wl.phone}），請聯絡客服或稍後再試。")
            return
        txns = (StoredValueTransaction.query
                .filter_by(wallet_id=wallet.id)
                .order_by(StoredValueTransaction.created_at.desc())
                .limit(8).all())
        q = StoredValueTransaction.query.filter_by(wallet_id=wallet.id).all()
        c500 = c300 = c100 = 0
        for t in q:
            sign = 1 if t.type == 'topup' else -1
            c500 += sign * (t.coupon_500_count or 0)
            c300 += sign * (t.coupon_300_count or 0)
            c100 += sign * (getattr(t, 'coupon_100_count', 0) or 0)
        tz_local = pytz.timezone("Asia/Taipei")
        now_dt = datetime.now(tz_local)
        expire_dt = tz_local.localize(datetime(now_dt.year, 12, 31, 23, 59, 59))
        if now_dt > expire_dt:
            rem500 = max(c500, 0)
            rem300 = max(c300, 0)
            rem100 = max(c100, 0)
            if rem500 > 0 or rem300 > 0 or rem100 > 0:
                try:
                    expire_txn = StoredValueTransaction()
                    expire_txn.wallet_id = wallet.id
                    expire_txn.type = 'consume'
                    expire_txn.amount = 0
                    expire_txn.remark = f"優惠券到期自動清除 {expire_dt.strftime('%Y/%m/%d')}"
                    expire_txn.coupon_500_count = rem500
                    expire_txn.coupon_300_count = rem300
                    expire_txn.coupon_100_count = rem100
                    db.session.add(expire_txn)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            c500 = c300 = c100 = 0
        else:
            c500 = max(c500, 0)
            c300 = max(c300, 0)
            c100 = max(c100, 0)
        maybe_push_coupon_expiry_notice(user_id)
        txn_boxes = []
        if not txns:
            txn_boxes.append({"type": "text", "text": "(尚無交易紀錄)", "size": "sm", "color": "#999999"})
        else:
            for t in txns:
                ts = t.created_at.astimezone(tz_local).strftime('%m/%d %H:%M') if t.created_at else ''
                label = '儲值 -' if t.type == 'topup' else '扣款 -'
                # 券文案
                parts = []
                if t.type == 'topup':
                    if (t.coupon_500_count or 0) > 0:
                        parts.append(f"新增500折價券X{t.coupon_500_count}")
                    if (t.coupon_300_count or 0) > 0:
                        parts.append(f"新增300折價券X{t.coupon_300_count}")
                    if (getattr(t, 'coupon_100_count', 0) or 0) > 0:
                        parts.append(f"新增100折價券X{t.coupon_100_count}")
                else:
                    if (t.coupon_500_count or 0) > 0:
                        parts.append(f"使用500折價券X{t.coupon_500_count}")
                    if (t.coupon_300_count or 0) > 0:
                        parts.append(f"使用300折價券X{t.coupon_300_count}")
                    if (getattr(t, 'coupon_100_count', 0) or 0) > 0:
                        parts.append(f"使用100折價券X{t.coupon_100_count}")
                coupon_text = '、'.join(parts) if parts else '-'
                remark_text = t.remark or '-'
                txn_boxes.append({
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "baseline",
                            "contents": [
                                {"type": "text", "text": ts or "-", "size": "xs", "color": "#666666", "flex": 3},
                                {"type": "text", "text": label, "size": "xs", "color": "#455a64", "flex": 2},
                                {"type": "text", "text": str(t.amount), "size": "xs", "weight": "bold", "color": "#000000", "flex": 2},
                                {"type": "text", "text": coupon_text, "size": "xs", "color": "#8e24aa", "wrap": True, "flex": 5}
                            ]
                        },
                        {"type": "text", "text": f"備註：{remark_text}", "size": "xxs", "color": "#555555", "wrap": True}
                    ]
                })
        now_str = now_dt.strftime('%Y/%m/%d %H:%M:%S')
        nickname = (wl.name if wl else '') or '用戶'
        line_id_display = wl.line_id if wl and wl.line_id else '未登記'
        user_code = wl.id if wl else '—'
        bubble = {
            "type": "bubble",
            "header": {"type": "box", "layout": "vertical", "backgroundColor": "#212121", "paddingAll": "16px", "contents": [{"type": "text", "text": "💳 儲值金資訊", "size": "lg", "weight": "bold", "color": "#FFD700", "align": "center"}]},
            "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": [
                {"type": "box", "layout": "vertical", "contents": [
                    {"type": "text", "text": f"手機號碼：{wl.phone}", "size": "sm"},
                    {"type": "text", "text": f"用戶暱稱：{nickname}", "size": "sm"},
                    {"type": "text", "text": f"個人編號：{user_code}", "size": "sm"},
                    {"type": "text", "text": f"LINE ID：{line_id_display}", "size": "sm"},
                    {"type": "text", "text": f"查詢時間：{now_str}", "size": "sm", "color": "#607d8b"},
                    {"type": "separator", "margin": "md"},
                    {"type": "box", "layout": "horizontal", "contents": [
                        {"type": "text", "text": "目前餘額", "size": "sm", "color": "#555555", "flex": 5},
                        {"type": "text", "text": f"{wallet.balance} 元", "size": "sm", "weight": "bold", "color": "#1b5e20", "align": "end", "flex": 5}
                    ]},
                    {"type": "box", "layout": "vertical", "margin": "md", "contents": [
                        {"type": "text", "text": f"折價券剩餘：500券 x {c500}、300券 x {c300}、100券 x {c100}", "size": "sm", "color": "#6a1b9a"}
                    ]}
                ]},
                {"type": "separator", "margin": "md"},
                {"type": "text", "text": "使用記錄", "size": "sm", "weight": "bold"},
                {"type": "box", "layout": "vertical", "spacing": "xs", "contents": txn_boxes}
            ]},
            "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": [
                {"type": "button", "style": "primary", "color": "#3F51B5", "action": {"type": "message", "label": "🏛️ 回主選單", "text": "主選單"}},
                {"type": "button", "style": "secondary", "color": "#8E24AA", "action": {"type": "message", "label": "🔁 重新查詢", "text": "儲值金"}}
            ]}
        }
        try:
            line_bot_api.reply_message(event.reply_token, FlexSendMessage(alt_text="儲值金資訊", contents=bubble))
        except Exception:
            logging.exception("reply wallet flex failed")

    existing = Whitelist.query.filter_by(line_user_id=user_id).first()
    if existing:
        if user_text == "重新驗證":
            reply_with_reverify(event, "您已通過驗證，無法重新驗證。")
            return
        # 已驗證用戶：若輸入手機或「儲值金」「查餘額」「餘額」直接顯示對應資訊
        if user_text in ("儲值金", "查餘額", "餘額"):
            reply_wallet(existing)
            return
        # 服務專線關鍵字：顯示熱線資訊後跳主選單
        if user_text.strip() == '服務專線':
            hotline_msg = (
                '📞 茗殿熱線：0987-346-208\n'
                '歡迎來電洽詢，專人即時服務！'
            )
            reply_with_menu(event.reply_token, hotline_msg)
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
            try:
                line_bot_api.push_message(user_id, TextSendMessage(text=EXTRA_NOTICE))
            except Exception:
                logging.exception("push EXTRA_NOTICE after existing whitelist view failed")
            try:
                maybe_push_coupon_expiry_notice(user_id)
            except Exception:
                logging.exception("expiry notice after whitelist view failed")
        else:
            reply_with_reverify(event, "⚠️ 已驗證，若要查看資訊請輸入您當時驗證的手機號碼或輸入『儲值金』查錢包。")
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

    # 上方 wallet 回覆已在 existing 分支處理

    if user_text == "重新驗證":
        logging.info(f"[handle_text] 進入重新驗證分支 user_id={user_id}")
        set_temp_user(user_id, {"step": "waiting_phone", "name": display_name, "reverify": True, "user_id": user_id})
        reply_basic(event, "請輸入您的手機號碼（09開頭）開始重新驗證～")
        return

    phone_candidate = normalize_phone(user_text)
    # 若輸入為手機號且該號已在白名單，直接綁定當前 user 並回覆主選單（即使存在 temp 狀態）
    if re.match(r"^09\d{8}$", phone_candidate):
        wl = Whitelist.query.filter_by(phone=phone_candidate).first()
        if wl:
            if wl.line_user_id and wl.line_user_id != user_id:
                reply_basic(event, "❌ 此手機已綁定其他帳號，請聯絡客服協助。")
                return
            # 綁定 line_user_id（若尚未綁定）
            if wl.line_user_id != user_id:
                wl.line_user_id = user_id
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            # 回覆主選單
            reply = (
                f"📱 {wl.phone}\n"
                f"🌸 暱稱：{wl.name or display_name}\n"
                f"       個人編號：{wl.id}\n"
                f"🔗 LINE ID：{wl.line_id or '未登記'}\n"
                f"🕒 {wl.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿\n"
                f"🌟 加入密碼：ming666"
            )
            reply_with_menu(event.reply_token, reply)
            try:
                line_bot_api.push_message(user_id, TextSendMessage(text=EXTRA_NOTICE))
            except Exception:
                logging.exception("push EXTRA_NOTICE after phone bind failed")
            try:
                maybe_push_coupon_expiry_notice(user_id)
            except Exception:
                logging.exception("expiry notice after phone bind failed")
            pop_temp_user(user_id)
            return
    if not get_temp_user(user_id) and re.match(r"^09\d{8}$", phone_candidate):
        logging.info(f"[handle_text] 進入手機號分支 user_id={user_id} phone={phone_candidate}")
        if Blacklist.query.filter_by(phone=phone_candidate).first():
            reply_basic(event, "❌ 請聯絡管理員，無法自動通過驗證流程。❌")
            return
        owner = Whitelist.query.filter_by(phone=phone_candidate).first()
        if owner and owner.line_user_id and owner.line_user_id != user_id:
            reply_basic(event, "❌ 此手機已綁定其他帳號，請聯絡客服協助。")
            return
        set_temp_user(user_id, {"step": "waiting_lineid", "name": display_name, "phone": phone_candidate, "user_id": user_id})
        reply_basic(event,
            "✅ 手機號已登記～請輸入您的 LINE ID（未設定請輸入：尚未設定）\n"
            "⚠️ 若沒有設定 ID，請『只輸入四個字：尚未設定』，不要加其它文字或符號。"
        )
        return

    if re.match(r"^\d{8}$", user_text):
        logging.info(f"[handle_text] 進入驗證碼分支 user_id={user_id} code={user_text}")
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

    tu = get_temp_user(user_id)
    if tu and tu.get("step") == "waiting_phone":
        logging.info(f"[handle_text] 進入 waiting_phone 分支 user_id={user_id} tu={tu}")
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
        tu["user_id"] = user_id
        set_temp_user(user_id, tu)
        reply_basic(event,
            "✅ 手機號已登記～請輸入您的 LINE ID（未設定請輸入：尚未設定）\n"
            "⚠️ 若沒有設定 ID，請『只輸入四個字：尚未設定』，不要加其它文字或符號。"
        )
        return

    tu = get_temp_user(user_id)
    if tu and tu.get("step") == "waiting_lineid":
        logging.info(f"[handle_text] 進入 waiting_lineid 分支 user_id={user_id} tu={tu}")
        line_id = user_text.strip()
        if not line_id:
            reply_basic(event, "⚠️ 請輸入有效的 LINE ID（或輸入：尚未設定）")
            return
        tu["line_id"] = line_id
        tu["step"] = "waiting_screenshot"
        tu["user_id"] = user_id
        set_temp_user(user_id, tu)
        # 寫入 TempVerify，讓後台待驗證名單可見
        try:
            upsert_tempverify(phone=tu.get("phone"), line_id=line_id, nickname=tu.get("name") or tu.get("nickname"), line_user_id=user_id)
        except Exception:
            logging.exception("upsert_tempverify from waiting_lineid failed")
        reply_basic(
            event,
            "📸 請上傳您的 LINE 個人頁面截圖\n"
            "👉 路徑：LINE主頁 > 右上角『設定』 > 『個人檔案』，點進去後截圖\n"
            "畫面需清楚看到：您的 LINE 名稱，以及名稱下方那一行（顯示 ID 或『未設定』的那一行）。\n\n"
            "範例："
        )
        try:
            from linebot.models import ImageSendMessage
            line_bot_api.push_message(
                user_id,
                ImageSendMessage(
                    original_content_url="https://github.com/Suan0503/Test_Mod/blob/main/static/example_line_screenshot.jpg?raw=true",
                    preview_image_url="https://github.com/Suan0503/Test_Mod/blob/main/static/example_line_screenshot.jpg?raw=true"
                )
            )
        except Exception:
            pass
        return

    if not get_temp_user(user_id):
        logging.info(f"[handle_text] 進入初始分支 user_id={user_id}")
        set_temp_user(user_id, {
            "step": "waiting_phone",
            "name": display_name,
            "nickname": display_name,
            "user_id": user_id,
            "line_user_id": user_id
        })
        reply_basic(event, "歡迎～請直接輸入手機號碼（09開頭）進行驗證。")
        return

# ───────────────────────────────────────────────────────────────
# 3) 圖片訊息：OCR → 快速通關 / 資料有誤 顯示 OCR 圖片(或文字)
# ───────────────────────────────────────────────────────────────
@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    tu = get_temp_user(user_id)
    if not tu or tu.get("step") != "waiting_screenshot":
        reply_with_reverify(event, "請先完成前面步驟後再上傳截圖唷～")
        return

    message_content = line_bot_api.get_message_content(event.message.id)
    tmp_dir = "/tmp/ocr_inbox"
    os.makedirs(tmp_dir, exist_ok=True)
    temp_path = os.path.join(tmp_dir, f"{user_id}_{int(time.time())}.jpg")
    with open(temp_path, 'wb') as f:
        for chunk in message_content.iter_content():
            f.write(chunk)

    expected_line_id = (tu.get("line_id") or "").strip()
    try:
        image = Image.open(temp_path)
        ocr_text = pytesseract.image_to_string(image)
        ocr_text_low = (ocr_text or "").lower()

        def fast_pass():
            tz = pytz.timezone("Asia/Taipei")
            data = tu
            now = datetime.now(tz)
            data["date"] = now.strftime("%Y-%m-%d")
            record, _ = update_or_create_whitelist_from_data(
                data, user_id, reverify=tu.get("reverify", False)
            )
            # 標記 TempVerify 為 verified
            try:
                mark_tempverify_verified_by_phone(record.phone)
            except Exception:
                logging.exception("mark_tempverify_verified_by_phone (fast_pass) failed")
            reply = (
                f"📱 {record.phone}\n"
                f"🌸 暱稱：{record.name or '用戶'}\n"
                f"🔗 LINE ID：{record.line_id or '未登記'}\n"
                f"🕒 {record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿\n"
                f"🌟 加入密碼：ming666"
            )
            reply_with_menu(event.reply_token, reply)
            try:
                line_bot_api.push_message(user_id, TextSendMessage(text=EXTRA_NOTICE))
            except Exception:
                logging.exception("push EXTRA_NOTICE after fast_pass failed")
            try:
                maybe_push_coupon_expiry_notice(user_id)
            except Exception:
                logging.exception("expiry notice after fast_pass failed")
            pop_temp_user(user_id)

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
        tu["step"] = "waiting_confirm_after_ocr"
        set_temp_user(user_id, tu)
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
        # 用戶回覆「1」確認資料：
        #  - 一般用戶 OCR 比對失敗後，step 為 waiting_confirm_after_ocr
        #  - 圖片驗證／管理員手動通關後，step 為 waiting_confirm
        tu = get_temp_user(user_id)
        if tu and tu.get("step") in ("waiting_confirm_after_ocr", "waiting_confirm"):
            tz = pytz.timezone("Asia/Taipei")
            data = tu
            now = datetime.now(tz)
            data["date"] = now.strftime("%Y-%m-%d")
            record, _ = update_or_create_whitelist_from_data(
                data, user_id, reverify=data.get("reverify", False)
            )
            try:
                mark_tempverify_verified_by_phone(record.phone)
            except Exception:
                logging.exception("mark_tempverify_verified_by_phone (post_ocr user confirm) failed")
            reply = (
                f"📱 {record.phone}\n"
                f"🌸 暱稱：{record.name or '用戶'}\n"
                f"🔗 LINE ID：{record.line_id or '未登記'}\n"
                f"🕒 {record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿\n"
                f"🌟 加入密碼：ming666"
            )
            reply_with_menu(event.reply_token, reply)
            try:
                line_bot_api.push_message(user_id, TextSendMessage(text=EXTRA_NOTICE))
            except Exception:
                logging.exception("push EXTRA_NOTICE after post_ocr confirm failed")
            try:
                maybe_push_coupon_expiry_notice(user_id)
            except Exception:
                logging.exception("expiry notice after post_ocr confirm failed")
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
                try:
                    mark_tempverify_verified_by_phone(record.phone)
                except Exception:
                    logging.exception("mark_tempverify_verified_by_phone (admin manual 1) failed")
                reply = (
                    f"📱 {record.phone}\n"
                    f"🌸 暱稱：{record.name or '用戶'}\n"
                    f"🔗 LINE ID：{record.line_id or '未登記'}\n"
                    f"🕒 {record.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                    f"✅ 驗證成功，歡迎加入茗殿\n"
                    f"🌟 加入密碼：ming666"
                )
                reply_with_menu(event.reply_token, reply)
                try:
                    line_bot_api.push_message(user_id, TextSendMessage(text=EXTRA_NOTICE))
                except Exception:
                    logging.exception("push EXTRA_NOTICE after manual verify confirm failed")
                try:
                    maybe_push_coupon_expiry_notice(user_id)
                except Exception:
                    logging.exception("expiry notice after manual verify confirm failed")
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
                "此為管理員手動驗證，如無誤按「完成驗證」。"
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
