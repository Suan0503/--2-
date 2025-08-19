from linebot.models import TextSendMessage, FlexSendMessage
from extensions import line_bot_api
from storage import ADMIN_IDS  # 管理員清單
import os

def choose_link():
    group = [
        "https://line.me/ti/p/g7TPO_lhAL",
        "https://line.me/ti/p/emkjaMQkMK",
        "https://line.me/ti/p/AKRUvSCLRC"
    ]
    return group[hash(os.urandom(8)) % len(group)]

# === JKF 廣告連結與名稱可獨立修改 ===
JKF_LINKS = [
    {
        "label": "茗殿 - 主頁推薦",
        "url": "https://www.jkforum.net/p/thread-15744749-1-1.html"
    },
    {
        "label": "泰式料理菜單 - 1",
        "url": "https://www.jkforum.net/p/thread-16422277-1-1.html"
    },
    {
        "label": "泰式料理菜單 - 2",
        "url": "https://www.jkforum.net/p/thread-17781450-1-1.html"
    },
    {
        "label": "越式料理小吃 - 1",
        "url": "https://www.jkforum.net/p/thread-18976516-1-1.html"
    },
    {
        "label": "越式料理小吃 - 2",
        "url": "https://www.jkforum.net/p/thread-17742482-1-1.html"
    },
    {
        "label": "檔期推薦 - 多多",
        "url": "https://www.jkforum.net/p/thread-20296958-1-1.html"
    },
    {
        "label": "檔期推薦 - 莎莎",
        "url": "https://www.jkforum.net/p/thread-20296970-1-1.html"
    },
    {
        "label": "檔期推薦 - 心心",
        "url": "https://www.jkforum.net/p/thread-10248540-1-1.html"
    },
    {
        "label": "本期空缺中",
        "url": "https://www.jkforum.net/p/thread-15744749-1-1.html"
    },
    {
        "label": "本期空缺中",
        "url": "https://www.jkforum.net/p/thread-15744749-1-1.html"
    },
]

def get_ad_menu():
    """
    廣告專區 Flex Message，10個JKF連結按鈕（名稱可獨立修改），
    主副色跳色，所有按鈕皆為白色字體。
    """
    buttons = []
    btn_primary = "#2C4A6B"   # 深藍
    btn_secondary = "#4B99C2" # 深天藍

    for i, link in enumerate(JKF_LINKS):
        buttons.append({
            "type": "button",
            "action": {
                "type": "uri",
                "label": link["label"],
                "uri": link["url"]
            },
            "style": "primary",  # 全部主色，確保字體白色
            "color": btn_primary if i % 2 == 0 else btn_secondary
        })
    # 回主選單按鈕
    buttons.append({
        "type": "button",
        "action": {
            "type": "message",
            "label": "🏠 回主選單",
            "text": "主選單"
        },
        "style": "primary",
        "color": btn_secondary
    })
    return FlexSendMessage(
        alt_text="廣告專區",
        contents={
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "backgroundColor": "#1C2636",  # 深夏夜藍
                "contents": [
                    {
                        "type": "text",
                        "text": "🏖️ 夏日廣告專區",
                        "weight": "bold",
                        "size": "lg",
                        "align": "center",
                        "color": "#FFD700"    # 金黃
                    },
                    {"type": "separator", "color": "#31485C"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "margin": "lg",
                        "spacing": "sm",
                        "contents": buttons
                    }
                ]
            }
        }
    )

def get_menu_carousel():
    """
    主功能選單，深色夏日風格
    """
    main_bg1 = "#1C2636"     # 深夏夜藍
    main_bg2 = "#222E44"     # 次深夜藍
    btn_yellow = "#FFD700"   # 金黃
    btn_green = "#11806A"    # 深夏綠
    btn_blue = "#2C4A6B"     # 深藍
    btn_white = "#FDF6EE"    # 柔米白
    btn_orange = "#FF9800"   # 橘色
    btn_pink = "#D97092"     # 夏夜玫瑰粉
    btn_lblue = "#4B99C2"    # 深天藍
    btn_lgreen = "#2BB673"   # 夏夜綠
    btn_gray = "#31485C"     # 深灰藍

    bubbles = []

    # 第一頁
    bubbles.append({
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "backgroundColor": main_bg1,
            "contents": [
                {
                    "type": "text",
                    "text": "🏖️ 夏日茗殿選單 1/2",
                    "weight": "bold",
                    "size": "lg",
                    "align": "center",
                    "color": "#FFD700"
                },
                {"type": "separator", "color": "#31485C"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "lg",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "action": {
                                "type": "message",
                                "label": "🍧 開啟主選單",
                                "text": "驗證資訊"
                            },
                            "style": "primary",
                            "color": btn_yellow
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "message",
                                "label": "🌴 每日抽獎",
                                "text": "每日抽獎"
                            },
                            "style": "primary",
                            "color": btn_green
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "message",
                                "label": "📢 廣告專區",
                                "text": "廣告專區"
                            },
                            "style": "primary",
                            "color": btn_blue
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "uri",
                                "label": "📅 班表查詢",
                                "uri": "https://t.me/+svlFjBpb4hxkYjFl"
                            },
                            "style": "secondary",
                            "color": btn_white
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "uri",
                                "label": "🕶️ 預約諮詢",
                                "uri": choose_link()
                            },
                            "style": "secondary",
                            "color": btn_orange
                        }
                    ]
                }
            ]
        }
    })

    # 第二頁
    bubbles.append({
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "backgroundColor": main_bg2,
            "contents": [
                {
                    "type": "text",
                    "text": "🏝️ 夏日茗殿選單 2/2",
                    "weight": "bold",
                    "size": "lg",
                    "align": "center",
                    "color": "#FFD700"
                },
                {"type": "separator", "color": "#31485C"},
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
                                "label": "🌺 茗殿討論區",
                                "uri": "https://line.me/ti/g2/mq8VqBIVupL1lsIXuAulnqZNz5vw7VKrVYjNDg?utm_source=invitation&utm_medium=link_copy&utm_campaign=default"
                            },
                            "style": "primary",
                            "color": btn_lgreen
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "message",
                                "label": "📝 回報文登記(暫停使用)",
                                "text": "回報文"
                            },
                            "style": "primary",
                            "color": btn_pink
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "message",
                                "label": "💸 折價券管理",
                                "text": "折價券管理"
                            },
                            "style": "primary",
                            "color": btn_lblue
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "message",
                                "label": "🧊 呼叫管理員（暫停使用）",
                                "text": "呼叫管理員"
                            },
                            "style": "secondary",
                            "color": btn_gray
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "message",
                                "label": "🌞 活動快訊（暫停使用）",
                                "text": "活動快訊"
                            },
                            "style": "primary",
                            "color": btn_orange
                        }
                    ]
                }
            ]
        }
    })

    return FlexSendMessage(
        alt_text="🏖️ 夏日主功能選單",
        contents={
            "type": "carousel",
            "contents": bubbles
        }
    )

def reply_with_menu(token, text=None):
    """
    回覆主選單與可選的說明文字
    """
    msgs = []
    if text:
        msgs.append(TextSendMessage(text=text))
    msgs.append(get_menu_carousel())
    line_bot_api.reply_message(token, msgs)

def reply_with_ad_menu(token):
    """
    回覆廣告專區選單
    """
    msgs = [get_ad_menu()]
    line_bot_api.reply_message(token, msgs)

def notify_admins(user_id, display_name=None):
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
