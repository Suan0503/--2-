import re
import difflib
from PIL import Image, ImageEnhance, ImageOps
import pytesseract

INVALID_ID_CONTENTS = [
    "允許加入好友", "allow others to add me", 
    "朋友推薦", "friends recommendations",
    "複製", "copy", "コピー"
]

def preprocess_image(image_path):
    image = Image.open(image_path)
    image = image.convert('L')
    hist = image.histogram()
    if sum(hist[200:]) > sum(hist[:55]):
        image = ImageOps.invert(image)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2)
    image = image.point(lambda x: 0 if x < 120 else 255, '1')
    return image

def normalize_phone(phone):
    if not phone:
        return None
    phone = phone.replace(" ", "").replace("-", "")
    if phone.startswith("+886"):
        phone = "0" + phone[4:]
    elif phone.startswith("886"):
        phone = "0" + phone[3:]
    phone = re.sub(r'\D', '', phone)
    if len(phone) == 10 and phone.startswith("09"):
        return phone
    return None

def normalize_text(text):
    if not text:
        return ""
    text = re.sub(r'[\W_]+', '', text.lower())
    return text

def similar_id(id1, id2):
    if not id1 or not id2:
        return False
    id1 = id1.lower()
    id2 = id2.lower()
    if id1 == id2:
        return True
    swaps = [
        ('l', '1'), ('1', 'l'),
        ('0', 'o'), ('o', '0'),
        ('2', 'a'), ('a', '2'),
        ('5', 's'), ('s', '5')
    ]
    for a, b in swaps:
        if id1.replace(a, b) == id2 or id2.replace(a, b) == id1:
            return True
    return difflib.SequenceMatcher(None, id1, id2).ratio() > 0.85

def extract_lineid_phone(image_path, debug=False):
    image = preprocess_image(image_path)
    text = pytesseract.image_to_string(image, lang='eng+chi_tra')

    # 手機號碼：全文找所有可能的 09 開頭 or +886
    phone = None
    phone_matches = re.findall(r'(09\d{2}[-\s]?\d{3}[-\s]?\d{3}|(?:\+886|886)[-\s]?\d{2}[-\s]?\d{3}[-\s]?\d{3})', text)
    for m in phone_matches:
        phone_candidate = normalize_phone(m)
        if phone_candidate:
            phone = phone_candidate
            break

    # LINE ID 抓取
    line_id = None
    # 多種容錯關鍵字：ID/Id/id/LINE ID/Line ID/line id
    id_keywords = ["ID", "Id", "id", "LINE ID", "Line ID", "line id"]
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if any(kw in line for kw in id_keywords):
            # 找下方那一排、或冒號右邊
            # 先抓冒號右邊
            colon_match = re.search(r'[:：]\s*([\w\-]+)', line)
            if colon_match:
                candidate = colon_match.group(1).strip()
                if candidate and not any(bad in candidate.lower() for bad in INVALID_ID_CONTENTS):
                    line_id = candidate
                    break
            # 再抓下方一行
            if i+1 < len(lines):
                candidate = lines[i+1].strip()
                if candidate and not any(bad in candidate.lower() for bad in INVALID_ID_CONTENTS):
                    line_id = candidate
                    break
    # fallback: 全文正則
    if not line_id:
        id_match = re.search(r'ID\s*[:：]?\s*([\w\-]+)', text, re.IGNORECASE)
        if id_match:
            candidate = id_match.group(1).strip()
            if candidate and not any(bad in candidate.lower() for bad in INVALID_ID_CONTENTS):
                line_id = candidate

    if debug:
        print("OCR全文：", text)
        print("手機號碼：", phone)
        print("LINE ID：", line_id)
    return phone, line_id, text, similar_id
