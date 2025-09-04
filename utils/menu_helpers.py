# -*- coding: utf-8 -*-
from linebot.models import TextSendMessage, FlexSendMessage
from extensions import line_bot_api
from storage import ADMIN_IDS  # 管理員清單
from secrets import choice as secrets_choice

# ================= 魔法學院配色（可依喜好微調） =================
# 深色主題：午夜藍 / 靛紫為底，羊皮紙、鍍金點綴，酒紅與翡翠綠作功能色
MAG_BG_1   = "#1A2242"  # 深靛藍（頁1底）
MAG_BG_2   = "#121934"  # 午夜藍（頁2底）
MAG_GOLD   = "#D4AF37"  # 鍍金字/強調
MAG_PARCH  = "#E9DFC7"  # 羊皮紙
MAG_BURG   = "#7C1E2B"  # 酒紅
MAG_EMER   = "#2E7D5B"  # 翡翠綠
MAG_INDIGO = "#283E6D"  # 靛藍（按鈕色）
MAG_PURPLE = "#6B4AAE"  # 魔法紫（按鈕色）
MAG_STEEL  = "#3E4A72"  # 鋼藍（中性色）

# ====== 共用：隨機客服/預約群連結 ======
def choose_link():
    group = [
        "https://line.me/ti/p/g7TPO_lhAL",
        "https://line.me/ti/p/emkjaMQkMK",
        "https://line.me/ti/p/AKRUvSCLRC",
    ]
    return secrets_choice(group)

# ====== JKF 廣告連結（可獨立修改）======
JKF_LINKS = [
    {"label": "茗殿 - 主頁推薦",     "url": "https://www.jkforum.net/p/thread-15744749-1-1.html"},
    {"label": "泰式料理菜單 - 1",   "url": "https://www.jkforum.net/p/thread-16422277-1-1.html"},
    {"label": "泰式料理菜單 - 2",   "url": "https://www.jkforum.net/p/thread-17781450-1-1.html"},
    {"label": "越式料理小吃 - 1",   "url": "https://www.jkforum.net/p/thread-18976516-1-1.html"},
    {"label": "越式料理小吃 - 2",   "url": "https://www.jkforum.net/p/thread-17742482-1-1.html"},
    {"label": "檔期推薦 - 多多",     "url": "https://www.jkforum.net/p/thread-20296958-1-1.html"},
    {"label": "檔期推薦 - 莎莎",     "url": "https://www.jkforum.net/p/thread-20296970-1-1.html"},
    {"label": "檔期推薦 - 心心",     "url": "https://www.jkforum.net/p/thread-10248540-1-1.html"},
    {"label": "本期空缺中",         "url": "https://www.jkforum.net/p/thread-15744749-1-1.html"},
    {"label": "本期空缺中",         "url": "https://www.jkforum.net/p/thread-15744749-1-1.html"},
]

# ====== 廣告專區（魔法學院主題）======
def get_ad_menu():
    btn_primary   = MAG_INDIGO   # 靛藍
    btn_secondary = MAG_PURPLE   # 魔法紫

    buttons = []
    for i, link in enumerate(JKF_LINKS):
        buttons.append({
            "type": "button",
            "action": {"type": "uri", "label": link["label"], "uri": link["url"]},
            "style": "primary",  # 白字
            "color": btn_primary if i % 2 == 0 else btn_secondary
        })

    # 回主選單
    buttons.append({
        "type": "button",
        "action": {"type": "message", "label": "🏛️ 回主選單", "text": "主選單"},
        "style": "primary",
        "color": btn_secondary
    })

    return FlexSendMessage(
        alt_text="廣告專區",
        contents={
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": MAG_BG_2,
                "paddingAll": "16px",
                "contents": [{
                    "type": "text",
                    "text": "🪄 茗殿廣告塔",
                    "weight": "bold",
                    "size": "lg",
                    "align": "center",
                    "color": MAG_GOLD
                }]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": MAG_BG_2,
                "spacing": "md",
                "contents": [
                    {"type": "separator", "color": MAG_STEEL},
                    {"type": "box", "layout": "vertical", "spacing": "sm", "margin": "lg", "contents": buttons}
                ]
            },
            "styles": {"body": {"separator": False}}
        }
    )

# ====== 魔法學院主選單（兩頁 Carousel）======
def get_menu_carousel():
    # 第一頁 - 靛藍/金色主題
    page1 = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": MAG_BG_1,
            "paddingAll": "16px",
            "contents": [{
                "type": "text",
                "text": "🏰 茗殿魔法學院選單 1/2",
                "weight": "bold",
                "align": "center",
                "size": "lg",
                "color": MAG_GOLD
            }]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": MAG_BG_1,
            "spacing": "md",
            "contents": [
                {"type": "separator", "color": MAG_STEEL},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "action": {"type": "message", "label": "🪄 學籍驗證（主選單）", "text": "驗證資訊"},
                            "style": "primary",
                            "color": MAG_PURPLE
                        },
                        {
                            "type": "button",
                            "action": {"type": "message", "label": "🎁 入學抽獎", "text": "每日抽獎"},
                            "style": "primary",
                            "color": MAG_GOLD
                        },
                        {
                            "type": "button",
                            "action": {"type": "message", "label": "📜 學員介紹", "text": "廣告專區"},
                            "style": "primary",
                            "color": MAG_EMER
                        },
                        {
                            "type": "button",
                            "action": {"type": "uri", "label": "🗓️ 班表占卜室", "uri": "https://t.me/+svlFjBpb4hxkYjFl"},
                            "style": "secondary",
                            "color": MAG_PARCH     # secondary 會深色字，羊皮紙較適合
                        },
                        {
                            "type": "button",
                            "action": {"type": "uri", "label": "🔮 預約水晶球（總機）", "uri": choose_link()},
                            "style": "secondary",
                            "color": MAG_BURG
                        }
                    ]
                }
            ]
        }
    }

    # 第二頁 - 午夜藍/羊皮紙/金色
    page2 = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": MAG_BG_2,
            "paddingAll": "16px",
            "contents": [{
                "type": "text",
                "text": "📚 魔法學院選單 2/2",
                "weight": "bold",
                "align": "center",
                "size": "lg",
                "color": MAG_GOLD
            }]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": MAG_BG_2,
            "spacing": "md",
            "contents": [
                {"type": "separator", "color": MAG_STEEL},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "action": {
                                "type": "uri",
                                "label": "🏛️ 學院討論大廳",
                                "uri": "https://line.me/ti/g2/mq8VqBIVupL1lsIXuAulnqZNz5vw7VKrVYjNDg?utm_source=invitation&utm_medium=link_copy&utm_campaign=default"
                            },
                            "style": "primary",
                            "color": MAG_EMER
                        },
                        {
                            "type": "button",
                            "action": {"type": "message", "label": "📝 任務回報（暫停）", "text": "回報文"},
                            "style": "primary",
                            "color": MAG_PURPLE
                        },
                        {
                            "type": "button",
                            "action": {"type": "message", "label": "💰 折價卷魔法袋", "text": "折價券管理"},
                            "style": "primary",
                            "color": MAG_INDIGO
                        },
                        {
                            "type": "button",
                            "action": {"type": "message", "label": "🧙 召喚魔法師（管理員）", "text": "呼叫管理員"},
                            "style": "secondary",
                            "color": MAG_STEEL
                        },
                        {
                            "type": "button",
                            "action": {"type": "message", "label": "🌟 最新魔法快訊！限時開啟！", "text": "活動快訊"},
                            "style": "primary",
                            "color": MAG_BURG
                        }
                    ]
                }
            ]
        }
    }

    return FlexSendMessage(
        alt_text="魔法學院主功能選單",
        contents={"type": "carousel", "contents": [page1, page2]}
    )

# ====== 封裝回覆 =======
def reply_with_menu(reply_token, text=None):
    msgs = []
    if text:
        msgs.append(TextSendMessage(text=text))
    msgs.append(get_menu_carousel())
    line_bot_api.reply_message(reply_token, msgs)

def reply_with_ad_menu(reply_token):
    line_bot_api.reply_message(reply_token, [get_ad_menu()])

# ====== 呼叫管理員推播 =======
def notify_admins(user_id, display_name=None):
    # 避免硬性相依：在使用時才 import
    from models import Whitelist
    user = Whitelist.query.filter_by(line_user_id=user_id).first()

    if user:
        code = user.id or "未登記"
        name = user.name or (display_name or "未登記")
        line_id = user.line_id or "未登記"
    else:
        code = "未登記"
        name = display_name or "未登記"
        line_id = "未登記"

    msg = (
        "【用戶呼叫管理員】\n"
        f"暱稱：{name}\n"
        f"用戶編號：{code}\n"
        f"LINE ID：{line_id}\n"
        f"訊息：呼叫管理員\n\n"
        f"➡️ 若要私訊此用戶，請輸入：/msg {user_id} 你的回覆內容"
    )

    for admin_id in ADMIN_IDS:
        try:
            line_bot_api.push_message(admin_id, TextSendMessage(text=msg))
        except Exception as e:
            print(f"通知管理員失敗：{admin_id}，錯誤：{e}")