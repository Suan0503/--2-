from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
import os

db = SQLAlchemy()

# 回復為正式環境，不再覆寫 LineBotApi，取消所有 debug log
line_bot_api = LineBotApi(os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(os.environ["LINE_CHANNEL_SECRET"])
