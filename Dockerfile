FROM python:3.11-slim

# 安裝 Tesseract-OCR 及中文字庫、其它依賴
RUN apt-get update && \
    apt-get install -y gcc build-essential libffi-dev tesseract-ocr tesseract-ocr-chi-tra && \
    rm -rf /var/lib/apt/lists/*

# 建立工作資料夾
WORKDIR /app

# 複製 requirements.txt 並安裝 Python 套件
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 複製所有檔案
COPY . .

# 預設執行 main.py
CMD ["python", "main.py"]
