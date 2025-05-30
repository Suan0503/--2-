FROM python:3.11-slim

# 安裝系統必要套件
RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    libffi-dev \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
 && rm -rf /var/lib/apt/lists/*

# 設定工作目錄
WORKDIR /app

# 複製需求檔與程式碼
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY . .

# 啟動伺服器
CMD ["python", "main.py"]
