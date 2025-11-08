from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
import os, logging

db = SQLAlchemy()

ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not ACCESS_TOKEN or not CHANNEL_SECRET:
	logging.warning("LINE 環境變數缺失，啟用降級模式 (mock line_bot_api/handler)")
	class _MockLineBotApi:
		def __getattr__(self, name):
			def _missing(*a, **kw):
				logging.warning(f"[MockLineBotApi] 呼叫 {name} 被忽略，因環境變數未設定")
			return _missing
	class _MockHandler:
		def handle(self, body, signature):
			logging.warning("[MockHandler] 收到事件但 LINE_SECRET 未設定，略過處理")
	line_bot_api = _MockLineBotApi()
	handler = _MockHandler()
else:
	line_bot_api = LineBotApi(ACCESS_TOKEN)
	handler = WebhookHandler(CHANNEL_SECRET)
