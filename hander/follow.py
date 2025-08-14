def handle_follow(event):
    welcome_msg = (
        "歡迎加入🍵茗殿🍵\n"
        "\n"
        "請按照步驟完成驗證\n"
        "完成驗證才能預約\n"
        "\n"
        "※小助手無法預約，請洽專屬總機"
    )
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text=welcome_msg,
            quick_reply=QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="我同意規則", text="我同意規則"))
            ])
        )
    )
