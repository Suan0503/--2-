FROM python:3.11-slim

# 安裝系統相依套件（不含圖片處理的東西）
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
 && rm -rf /var/lib/apt/lists/*

# 設定工作目錄
WORKDIR /app

# 複製並安裝 Python 套件
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 複製所有程式碼
COPY . .

# 啟動應用（使用 gunicorn 避免 Flask 單機 499）
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8000", "main:app"]
