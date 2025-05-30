FROM python:3.11-slim

# 安裝必要的系統套件，包括 tesseract-ocr
RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    libffi-dev \
    tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

# 設定工作目錄
WORKDIR /app

# 安裝 Python 套件
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 複製所有程式碼
COPY . .

# 啟動程式
CMD ["python", "main.py"]
