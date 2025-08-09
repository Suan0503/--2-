from linebot.models import (
    MessageEvent, TextMessage, TemplateSendMessage, ButtonsTemplate, PostbackAction, PostbackEvent, TextSendMessage
)
from extensions import line_bot_api, db
from models import Whitelist, Coupon
from utils.temp_users import temp_users
from storage import ADMIN_IDS
import re, time
from datetime import datetime
import pytz

report_pending_map = {}

def handle_report(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    tz = pytz.timezone("Asia/Taipei")
    try:
        profile = line_bot_api.get_profile(user_id)
        display_name = profile.display_name
    except Exception:
        display_name = "用戶"

    # 啟動回報流程
    if user_text in ["回報文", "Report", "report"]:
        temp_users[user_id] = {"report_pending": True}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請輸入要回報的網址（請直接貼網址）：\n\n如需取消，請輸入「取消」")
        )
        return

    # 用戶取消回報流程
    if user_id in temp_users and temp_users[user_id].get("report_pending"):
        if user_text == "取消":
            temp_users.pop(user_id, None)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="已取消回報流程，回到主選單！")
            )
            return

        url = user_text
        if not re.match(r"^https?://", url):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="請輸入正確的網址格式（必須以 http:// 或 https:// 開頭）\n如需取消，請輸入「取消」")
            )
            return
        wl = Whitelist.query.filter_by(line_user_id=user_id).first()
        user_number = wl.id if wl else ""
        user_lineid = wl.line_id if wl else ""
        last_coupon = Coupon.query.filter(Coupon.report_no != None).order_by(Coupon.id.desc()).first()
        if last_coupon and last_coupon.report_no and last_coupon.report_no.isdigit():
            report_no = int(last_coupon.report_no) + 1
        else:
            report_no = 1
        report_no_str = f"{report_no:03d}"

        short_text = f"網址：{url}" if len(url) < 55 else "新回報文，請點選按鈕處理"
        detail_text = (
            f"【用戶回報文】編號-{report_no_str}\n"
            f"暱稱：{display_name}\n"
            f"用戶編號：{user_number}\n"
            f"LINE ID：{user_lineid}\n"
            f"網址：{url}"
        )
        report_id = f"{user_id}_{int(time.time()*1000)}"
        for admin_id in ADMIN_IDS:
            report_pending_map[report_id] = {
                "user_id": user_id,
                "admin_id": admin_id,
                "display_name": display_name,
                "user_number": user_number,
                "user_lineid": user_lineid,
                "url": url,
                "report_no": report_no_str
            }
            line_bot_api.push_message(
                admin_id,
                TemplateSendMessage(
                    alt_text="收到用戶回報文",
                    template=ButtonsTemplate(
                        title="收到新回報文",
                        text=short_text,
                        actions=[
                            PostbackAction(label="🟢 O", data=f"report_ok|{report_id}"),
                            PostbackAction(label="❌ X", data=f"report_ng|{report_id}")
                        ]
                    )
                )
            )
            line_bot_api.push_message(admin_id, TextSendMessage(text=detail_text))
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ 已收到您的回報，管理員會盡快處理！")
        )
        temp_users.pop(user_id)
        return

    # 管理員填寫拒絕原因
    if user_id in temp_users and temp_users[user_id].get("report_ng_pending"):
        report_id = temp_users[user_id]["report_ng_pending"]
        info = report_pending_map.get(report_id)
        if info:
            reason = user_text
            to_user_id = info["user_id"]
            reply = f"❌ 您的回報文未通過審核，原因如下：\n{reason}"
            try:
                line_bot_api.push_message(to_user_id, TextSendMessage(text=reply))
            except Exception as e:
                print("推播用戶回報拒絕失敗", e)
            temp_users.pop(user_id)
            report_pending_map.pop(report_id, None)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="已將原因回傳給用戶。"))
        else:
            temp_users.pop(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="找不到該回報資料（可能已處理過或超時）"))
        return

def handle_report_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    if data.startswith("report_ok|"):
        report_id = data.split("|")[1]
        info = report_pending_map.get(report_id)
        if info:
            to_user_id = info["user_id"]
            report_no = info.get("report_no", "未知")
            reply = f"🟢 您的回報文已審核通過，獲得一張月底抽獎券！（編號：{report_no}）"
            try:
                tz = pytz.timezone("Asia/Taipei")
                today = datetime.now(tz).strftime("%Y-%m-%d")
                # 回報文寫入 coupon.amount=0, type="report"（預設0，只有中獎才會改成大於0）
                new_coupon = Coupon(
                    line_user_id=to_user_id,
                    amount=0,  # ← 修改為 0
                    date=today,
                    created_at=datetime.now(tz),
                    report_no=report_no,
                    type="report"
                )
                db.session.add(new_coupon)
                db.session.commit()
                line_bot_api.push_message(to_user_id, TextSendMessage(text=reply))
            except Exception as e:
                print("推播用戶通過回報文失敗", e)
            report_pending_map.pop(report_id, None)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="已通過並回覆用戶。"))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="該回報已處理過或超時"))
        return
    elif data.startswith("report_ng|"):
        report_id = data.split("|")[1]
        info = report_pending_map.get(report_id)
        if info:
            temp_users[user_id] = {"report_ng_pending": report_id}
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入不通過的原因："))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="該回報已處理過或超時"))
        return
