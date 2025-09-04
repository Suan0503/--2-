from linebot.models import MessageEvent, TextMessage, ImageMessage, FollowEvent, PostbackEvent, TextSendMessage
from extensions import handler, line_bot_api, db
from utils.menu_helpers import reply_with_menu, notify_admins, reply_with_ad_menu
from hander.report import handle_report, handle_report_postback
from hander.admin import handle_admin
from hander.verify import handle_verify
from utils.temp_users import temp_users
from models import Whitelist, Coupon
from utils.draw_utils import draw_coupon, has_drawn_today, save_coupon_record, get_today_coupon_flex
import pytz
from datetime import datetime

from hander.follow import handle_follow
from hander.image import handle_image

import logging
logging.basicConfig(level=logging.INFO)

@handler.add(FollowEvent)
def on_follow(event):
    logging.info(f"[FollowEvent] Source: {event.source}")
    handle_follow(event, line_bot_api)  # 修正：傳入 line_bot_api

@handler.add(MessageEvent, message=ImageMessage)
def on_image(event):
    logging.info(f"[ImageMessage] user_id={event.source.user_id}")
    handle_image(event)

@handler.add(MessageEvent, message=TextMessage)
def entrypoint(event):
    user_text = event.message.text.strip()
    user_id = event.source.user_id
    logging.info(f"[TextMessage] user_id={user_id} text={user_text}")

    # ===== 新增：廣告專區入口 =====
    if user_text == "廣告專區":
        reply_with_ad_menu(event.reply_token)
        return

    # 回報文流程進行中（pending 狀態）
    if user_id in temp_users and (
        temp_users[user_id].get("report_pending") or
        temp_users[user_id].get("report_ng_pending")
    ):
        handle_report(event)
        return

    # 回報文關鍵字
    if user_text in ["回報文", "Report", "report"]:
        handle_report(event)
        return

    # 管理員指令
    if user_text.startswith("/msg "):
        handle_admin(event)
        return

    # 驗證資訊
    if user_text == "驗證資訊":
        tz = pytz.timezone("Asia/Taipei")
        now = datetime.now(tz)
        today_str = now.strftime('%Y-%m-%d')
        pre_event_end = datetime(2025, 9, 10, tzinfo=tz)
        img_url = "https://raw.githubusercontent.com/Suan0503/Test_Mod/refs/heads/main/static/20250904.jpg"  # 你的前導圖網址
        # 9/1~9/9 每日首次跳前導圖
        if now < pre_event_end:
            if user_id not in temp_users or temp_users[user_id].get('pre_event_shown') != today_str:
                from linebot.models import ImageSendMessage
                if user_id not in temp_users:
                    temp_users[user_id] = {}
                temp_users[user_id]['pre_event_shown'] = today_str
                user = Whitelist.query.filter_by(line_user_id=user_id).first()
                if user:
                    reply = (
                        f"📱 {user.phone}\n"
                        f"🌸 暱稱：{user.name or '未登記'}\n"
                        f"       個人編號：{user.id}\n"
                        f"🔗 LINE ID：{user.line_id or '未登記'}\n"
                        f"🕒 {user.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                        f"✅ 驗證成功，歡迎加入茗殿\n"
                        f"🌟 加入密碼：ming666"
                    )
                else:
                    reply = "查無你的驗證資訊，請先完成驗證流程。"
                line_bot_api.reply_message(event.reply_token, [
                    ImageSendMessage(original_content_url=img_url, preview_image_url=img_url),
                    TextSendMessage(text=reply)
                ])
                return
        user = Whitelist.query.filter_by(line_user_id=user_id).first()
        if user:
            reply = (
                f"📱 {user.phone}\n"
                f"🌸 暱稱：{user.name or '未登記'}\n"
                f"       個人編號：{user.id}\n"
                f"🔗 LINE ID：{user.line_id or '未登記'}\n"
                f"🕒 {user.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M:%S')}\n"
                f"✅ 驗證成功，歡迎加入茗殿\n"
                f"🌟 加入密碼：ming666"
            )
        else:
            reply = "查無你的驗證資訊，請先完成驗證流程。"
        reply_with_menu(event.reply_token, reply)
        return

    # ======= 每日抽獎功能 =======
    if user_text in ["每日抽獎"]:
        profile = None
        display_name = "用戶"
        try:
            profile = line_bot_api.get_profile(user_id)
            display_name = profile.display_name
        except Exception:
            pass

        # 判斷今天是否已抽過
        today_coupon = has_drawn_today(user_id, Coupon)
        if today_coupon:
            # 已抽過：直接顯示今日結果（Flex）
            amount = today_coupon.amount
            flex_msg = get_today_coupon_flex(user_id, display_name, amount)
            line_bot_api.reply_message(event.reply_token, [flex_msg])
            return
        else:
            # 沒抽過：抽獎、存檔、Flex
            amount = draw_coupon()
            save_coupon_record(user_id, amount, Coupon, db)
            flex_msg = get_today_coupon_flex(user_id, display_name, amount)
            line_bot_api.reply_message(event.reply_token, [flex_msg])
            return

    # 折價券管理
    if user_text in ["折價券管理", "券紀錄", "我的券紀錄"]:
        tz = pytz.timezone("Asia/Taipei")
        now = datetime.now(tz)
        today_str = now.strftime('%Y-%m-%d')
        month_str = now.strftime('%Y-%m')

        # 今日抽獎券
        today_draw = Coupon.query.filter_by(
            line_user_id=user_id, date=today_str, type="draw"
        ).first()

        # 當月回報文券
        month_reports = Coupon.query.filter(
            Coupon.line_user_id == user_id,
            Coupon.type == "report",
            Coupon.date.startswith(month_str)
        ).order_by(Coupon.date, Coupon.id).all()

        # 今日抽獎券區塊
        coupon_msg = "🎁【今日抽獎券】\n"
        if today_draw:
            coupon_msg += f"　　• 日期：{today_draw.date}｜金額：{today_draw.amount}元\n"
        else:
            coupon_msg += "　　• 尚未中獎\n"

        # 本月回報文券區塊
        coupon_msg += "\n📝【本月回報文抽獎券】\n"
        if month_reports:
            for idx, c in enumerate(month_reports, 1):
                # 金額0元時不顯示金額
                amount_str = f"｜金額：{c.amount}元" if c.amount else ""
                coupon_msg += f"　　• 日期：{c.date}｜編號：{idx:03}{amount_str}\n"
        else:
            coupon_msg += "　　• 無\n"

        coupon_msg += "\n※ 回報文抽獎券中獎名單與金額，將於每月抽獎公布"

        reply_with_menu(event.reply_token, coupon_msg)
        return

    # 主選單/功能選單/查詢規則/活動快訊
    if user_text in [
        "主選單", "功能選單", "選單", "menu", "Menu",
        "查詢規則", "規則查詢"
    ]:
        tz = pytz.timezone("Asia/Taipei")
        now = datetime.now(tz)
        today_str = now.strftime('%Y-%m-%d')
        # 第二活動前導圖：9/1~9/9，每日首次顯示
        pre_event_end = datetime(2025, 9, 10, tzinfo=tz)
        img_url = "https://raw.githubusercontent.com/Suan0503/Test_Mod/refs/heads/main/static/20250904.jpg"  # 請換成你的前導圖網址
        if now < pre_event_end:
            # 檢查 temp_users 是否已記錄今日已顯示
            if user_id not in temp_users or temp_users[user_id].get('pre_event_shown') != today_str:
                from linebot.models import ImageSendMessage
                # 記錄今日已顯示
                if user_id not in temp_users:
                    temp_users[user_id] = {}
                temp_users[user_id]['pre_event_shown'] = today_str
                line_bot_api.reply_message(event.reply_token, [
                    ImageSendMessage(original_content_url=img_url, preview_image_url=img_url),
                    TextSendMessage(text="主選單如下：")
                ])
                return
        reply_with_menu(event.reply_token)
        return

    # 活動快訊：多活動期間判斷
    if user_text == "活動快訊":
        tz = pytz.timezone("Asia/Taipei")
        now = datetime.now(tz)
        # 第一活動：9/1 ~ 9/30
        act1_start = datetime(2025, 9, 1, tzinfo=tz)
        act1_end = datetime(2025, 9, 30, 23, 59, 59, tzinfo=tz)
        # 第二活動：9/10 ~ 9/30
        act2_start = datetime(2025, 9, 10, tzinfo=tz)
        act2_end = datetime(2025, 9, 30, 23, 59, 59, tzinfo=tz)

        msg = ""
        img_url = None
        # 第一活動
        if act1_start <= now <= act1_end:
            msg += "🌸 茗殿好鄰居 1+1 活動 🌸\n"
            msg += "⏰ 即日起～9月底\n\n"
            msg += "💌 邀好友‧齊享優惠\n"
            msg += "✔️ 邀請好友加入並完成驗證：\n"
            msg += "\t• 邀請人 🎁 折價券 200 元\n"
            msg += "\t• 受邀人 🎁 折價券 100 元\n\n"
            msg += "👭 一起來更划算！\n"
            msg += "當日兩人同行預約 👉 現折 100 元\n\n"
            msg += "⚡溫馨提醒：\n領取折價券時，記得主動告知活動喔！"
            img_url = "https://raw.githubusercontent.com/Suan0503/Test_Mod/refs/heads/main/static/%E5%A5%BD%E9%84%B0%E5%B1%851%2B1.png"  # 請換成好鄰居1+1.png的實際網址

        # 第二活動
        if act2_start <= now <= act2_end:
            if msg:
                msg += "\n\n"
            msg += "🏫✨ 茗殿學院祭 — 少女的邀請 ✨🏫\n"
            msg += "⏰ 活動期間：9/10～9/30\n\n"
            msg += "🎀 妹妹們換上 清純校服，帶來滿滿青春氣息 💕\n"
            msg += "🎁 特別準備了 祭典限定特典，\n只送給參加的有緣人！（數量有限，送完為止）\n\n"
            msg += "🌸 在這個屬於學院的季節，\n快來和妹妹們留下專屬回憶吧！"

        if not msg:
            msg = "🌟 目前無進行中活動，敬請期待！"
            reply_with_menu(event.reply_token, msg)
        else:
            # 若有圖片網址，直接用 ImageSendMessage 顯示圖片
            if img_url:
                from linebot.models import ImageSendMessage
                line_bot_api.reply_message(event.reply_token, [
                    TextSendMessage(text=msg),
                    ImageSendMessage(original_content_url=img_url, preview_image_url=img_url)
                ])
            else:
                reply_with_menu(event.reply_token, msg)
        return

    # 呼叫管理員
    if user_text in ["呼叫管理員"]:
        display_name = None
        try:
            profile = line_bot_api.get_profile(user_id)
            display_name = profile.display_name
        except Exception:
            pass
        notify_admins(user_id, display_name)
        reply_with_menu(event.reply_token, "已通知管理員，請稍候，主選單如下：")
        return

    # 其餘交給驗證流程
    handle_verify(event)

@handler.add(PostbackEvent)
def entrypoint_postback(event):
    data = event.postback.data
    user_id = event.source.user_id
    logging.info(f"[PostbackEvent] user_id={user_id} data={data}")

    if data.startswith("report_ok|") or data.startswith("report_ng|"):
        handle_report_postback(event)
        return

    # 處理 OCR 驗證失敗時「申請手動驗證」的 Postback
    if data == "manual_verify":
        record = temp_users.get(user_id)
        if not record:
            line_bot_api.reply_message(
                event.reply_token, TextSendMessage(text="請先輸入手機號碼開始驗證流程。")
            )
            return
        record["step"] = "waiting_confirm"
        temp_users[user_id] = record
        reply = (
            f"📱 {record['phone']}\n"
            f"🌸 暱稱：{record['name']}\n"
            f"       個人編號：待驗證後產生\n"
            f"🔗 LINE ID：{record['line_id']}\n"
            f"（此用戶經手動通過）\n"
            f"請問以上資料是否正確？正確請回復 1\n"
            f"⚠️輸入錯誤請從新輸入手機號碼即可⚠️"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return
