from linebot.models import TextSendMessage
from extensions import line_bot_api, db
from models import Whitelist, Coupon
from utils.menu import get_menu_carousel
from utils.draw_utils import draw_coupon, get_today_coupon_flex, has_drawn_today, save_coupon_record
import pytz
from datetime import datetime

def handle_menu(event):
    user_id = event.source.user_id
    user_text = event.message.text.strip()
    tz = pytz.timezone("Asia/Taipei")
    try:
        profile = line_bot_api.get_profile(user_id)
        display_name = profile.display_name
    except Exception:
        display_name = "用戶"

    # 主選單
    if user_text in ["主選單", "功能選單", "選單", "menu", "Menu"]:
        line_bot_api.reply_message(event.reply_token, get_menu_carousel())
        return

    # 驗證資訊
    if user_text == "驗證資訊":
        existing = Whitelist.query.filter_by(line_user_id=user_id).first()
        if existing:
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
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 你尚未完成驗證，請輸入手機號碼進行驗證。"))
        return

    # 每日抽獎
    if user_text == "每日抽獎":
        if not Whitelist.query.filter_by(line_user_id=user_id).first():
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="⚠️ 你尚未完成驗證，請先完成驗證才能參加每日抽獎！"))
            return

        today_str = datetime.now(tz).strftime("%Y-%m-%d")
        coupon = Coupon.query.filter_by(line_user_id=user_id, date=today_str, type="draw").first()
        if coupon:
            flex = get_today_coupon_flex(user_id, display_name, coupon.amount)
            line_bot_api.reply_message(event.reply_token, flex)
            return

        amount = draw_coupon()  # 0/100/200/300
        save_coupon_record(user_id, amount, Coupon, db, type="draw")
        flex = get_today_coupon_flex(user_id, display_name, amount)
        line_bot_api.reply_message(event.reply_token, flex)
        return

    # 券紀錄
    if user_text in ["券紀錄", "我的券紀錄"]:
        today = datetime.now(tz).date()
        month_str = today.strftime("%Y-%m")
        user_coupons = Coupon.query.filter_by(line_user_id=user_id).all()

        # 今日抽獎券
        draw_today = [c for c in user_coupons if c.type == "draw" and c.date == str(today)]
        # 本月回報文
        report_month = [c for c in user_coupons if c.type == "report" and c.date.startswith(month_str)]

        msg = "🎁【今日抽獎券】\n"
        if draw_today:
            for c in draw_today:
                msg += f"　　• 日期：{c.date}｜金額：{c.amount}元\n"
        else:
            msg += "　　無紀錄\n"

        msg += "\n📝【本月回報文抽獎券】\n"
        if report_month:
            for c in report_month:
                no = c.report_no or ""
                # 只有中獎（amount>0）才顯示金額
                if c.amount and c.amount > 0:
                    msg += f"　　• 日期：{c.date}｜編號：{no}｜金額：{c.amount}元\n"
                else:
                    msg += f"　　• 日期：{c.date}｜編號：{no}\n"
        else:
            msg += "　　無紀錄\n"

        msg += "\n※ 回報文抽獎券中獎名單與金額，將於每月抽獎公布"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return
