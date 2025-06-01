import re
import pytesseract
from PIL import Image, ImageOps, ImageEnhance

def preprocess_image(image_path):
    image = Image.open(image_path)
    image = image.convert('L')
    # 檢查是否為白底（亮像素明顯多）
    hist = image.histogram()
    if sum(hist[200:]) > sum(hist[:55]):  # 白色像素大於黑色像素
        image = ImageOps.invert(image)
    # 增強對比
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2)
    # 二值化，針對白底建議閾值再低一點如120
    image = image.point(lambda x: 0 if x < 120 else 255, '1')
    return image

def normalize_text(text):
    text = re.sub(r'[\W_]+', '', text)
    return text

def normalize_phone(phone):
    phone = re.sub(r'\D', '', phone)
    if phone.startswith('886') and len(phone) == 11:
        phone = '09' + phone[3:]
    elif phone.startswith('+886') and len(phone) == 12:
        phone = '09' + phone[4:]
    return phone

def similar_id(id1, id2):
    """簡單模糊比對（可再強化）"""
    return normalize_text(id1).lower() == normalize_text(id2).lower()

def extract_lineid_phone(image_path, debug=False):
    image = preprocess_image(image_path)
    text = pytesseract.image_to_string(image, lang='eng+chi_tra')
    # 手機號
    phone_match = re.search(r'(09\d{8})|(?:\+?886\s?\d{2,3}\s?\d{3}\s?\d{3})', text.replace("-", ""))
    phone = None
    if phone_match:
        phone = normalize_phone(phone_match.group(0))
    # LINE ID 抓取直到遇到空白、換行或「複製」就停止
    lineid_match = re.search(r'ID\s*:?[\s\n]*([^\s複製]+)', text, re.IGNORECASE)

    # 進階：用 image_to_data 合併多框（解決ID被截斷問題）
    data = pytesseract.image_to_data(image, lang='eng+chi_tra', output_type=pytesseract.Output.DICT)
    words = data['text']
    line_id = None
    if lineid_match:
        line_id = lineid_match.group(1).strip()

    # 找到 "ID" 關鍵字，合併其後 1~3 個 box
    for i, word in enumerate(words):
        if isinstance(word, str) and word and re.match(r'^ID$', word, re.IGNORECASE):
            # 合併後面1~3個不為複製/コピー/Copy的 box
            next_words = []
            for j in range(1, 4):
                if i+j < len(words):
                    w = words[i+j]
                    # 若遇到複製、コピー、Copy等就停
                    if w and not re.match(r'^(複製|コピー|Copy)$', w, re.IGNORECASE):
                        next_words.append(w.strip())
                    else:
                        break
            # 合併後當成 ID
            if next_words:
                candidate = ''.join(next_words)
                # 若遇到多語系「複製」關鍵字則截斷
                candidate = re.split(r'(複製|コピー|Copy)', candidate)[0].strip()
                if candidate:
                    line_id = candidate
                    break

    # fallback: 單行正則（遇到有些截圖ID沒被拆開）
    if not line_id:
        lineid_match = re.search(r'ID\s*:?[\s\n]*([^\s]+)', text, re.IGNORECASE)
        if lineid_match:
            line_id = re.split(r'(複製|コピー|Copy)', lineid_match.group(1))[0].strip()

    if debug:
        print("OCR全文：", text)
        print("image_to_data：", words)
        print("抓到ID：", line_id)

    # 新版需求：回傳4個參數，最後一個是similar_id function
    return phone, line_id, text, similar_id
