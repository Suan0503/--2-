import os
from dotenv import load_dotenv

# 載入 .env 檔案（若有的話）
load_dotenv()

# 讀取環境變數，沒有就用預設值
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///local.db")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
PORT = int(os.getenv("PORT", 5000))

# 也可依需求增加你想要的 config
# 例如 DEBUG = os.getenv("DEBUG", "false").lower() == "true"