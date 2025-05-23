FROM python:3.11-slim

# 安裝依賴
RUN apt-get update && apt-get install -y gcc build-essential libffi-dev

# 建立工作資料夾
WORKDIR /app

# 安裝套件
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 複製所有檔案
COPY . .

# 執行程式
CMD ["python", "main.py"]
