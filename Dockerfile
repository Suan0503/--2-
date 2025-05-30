FROM python:3.11-slim

# 安裝必要的系統套件
RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    libffi-dev \
    tesseract-ocr \
    curl \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# 設定工作目錄
WORKDIR /app

# 複製 requirements.txt 並安裝 Python 套件
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 複製其他所有程式碼進去容器
COPY . .

# 明確指定啟動指令（python3 比較穩）
CMD ["python3", "main.py"]
