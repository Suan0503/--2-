import re
import difflib
from PIL import Image, ImageEnhance, ImageOps
import pytesseract

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
    text = text.lower()
    text = re.sub(r'[\W_]+', '', text)
    return text

def similar_id(id1, id2):
    """
    判斷兩個 LINE ID 是否相似，允許常見 OCR 混淆字元，編輯距離容忍度 0.85
    """
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
    # 編輯距離
    return difflib.SequenceMatcher(None, id1, id2).ratio() > 0.85

def extract_lineid_phone(image_path, debug=False):
    image = preprocess_image(image_path)
    text = pytesseract.image_to_string(image, lang='eng+chi_tra')
    # 手機號
    phone_match = re.search(r'(09\d{8})|(?:\+?886\s?\d{2,3}\s?\d{3}\s?\d{3})', text.replace("-", ""))
    phone = None
    if phone_match:
        phone = normalize_phone(phone_match.group(0))

    # 用 image_to_data 合併多框，解決ID被截斷
    data = pytesseract.image_to_data(image, lang='eng+chi_tra', output_type=pytesseract.Output.DICT)
    words = data['text']
    line_id = None

    for i, word in enumerate(words):
        if isinstance(word, str) and word and re.match(r'^ID$', word, re.IGNORECASE):
            next_words = []
            for j in range(1, 4):
                if i + j < len(words):
                    w = words[i + j]
                    if w and not re.match(r'^(複製|コピー|Copy)$', w, re.IGNORECASE):
                        next_words.append(w.strip())
                    else:
                        break
            if next_words:
                candidate = ''.join(next_words)
                candidate = re.split(r'(複製|コピー|Copy)', candidate)[0].strip()
                if candidate:
                    line_id = candidate
                    break

    # fallback: 單行正則
    if not line_id:
        lineid_match = re.search(r'ID\s*:?[\s\n]*([^\s]+)', text, re.IGNORECASE)
        if lineid_match:
            line_id = re.split(r'(複製|コピー|Copy)', lineid_match.group(1))[0].strip()

    if debug:
        print("OCR全文：", text)
        print("image_to_data：", words)
        print("抓到ID：", line_id)

    return phone, line_id, text, similar_id
