import re
import pytesseract
from PIL import Image, ImageOps, ImageEnhance

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

def normalize_text(text):
    return re.sub(r'[\W_]+', '', text)

def normalize_phone(phone):
    phone = re.sub(r'\D', '', phone)
    # +886903587063 or 886903587063 -> 0903587063
    if phone.startswith('8869') and len(phone) == 12:
        phone = '09' + phone[4:]
    elif phone.startswith('09') and len(phone) == 10:
        pass
    else:
        pass
    return phone

def is_fake_line_id(lineid):
    block_words = [
        "允許利用ID加入好友", "加入好友", "允許", "加入",
        "Allow others to add me by ID", "Add friends", "add friend"
    ]
    if not lineid:
        return True
    if any(bw in lineid for bw in block_words):
        return True
    if re.match(r'^[\u4e00-\u9fff]+$', lineid):
        return True
    if len(lineid) < 3:
        return True
    return False

def similar_id(id1, id2):
    return normalize_text(id1).lower() == normalize_text(id2).lower()

def extract_lineid_phone(image_path, debug=False):
    image = preprocess_image(image_path)
    text = pytesseract.image_to_string(image, lang='eng+chi_tra')
    phone_match = re.search(r'(09\d{8})|(?:\+?886\s?\d{2,3}\s?\d{3}\s?\d{3})', text.replace("-", ""))
    phone = None
    if phone_match:
        phone = normalize_phone(phone_match.group(0))
    # 先用正則抓
    lineid_match = re.search(r'ID\s*:?[\s\n]*([^\s複製]+)', text, re.IGNORECASE)
    data = pytesseract.image_to_data(image, lang='eng+chi_tra', output_type=pytesseract.Output.DICT)
    words = data['text']
    line_id = None
    if lineid_match:
        candidate = lineid_match.group(1).strip()
        if candidate and not is_fake_line_id(candidate):
            line_id = candidate

    # 進階合併多框
    for i, word in enumerate(words):
        if isinstance(word, str) and word and re.match(r'^ID$', word, re.IGNORECASE):
            next_words = []
            for j in range(1, 4):
                if i+j < len(words):
                    w = words[i+j]
                    if w and not re.match(r'^(複製|コピー|Copy)$', w, re.IGNORECASE):
                        next_words.append(w.strip())
                    else:
                        break
            if next_words:
                candidate = ''.join(next_words)
                candidate = re.split(r'(複製|コピー|Copy)', candidate)[0].strip()
                if candidate and not is_fake_line_id(candidate):
                    line_id = candidate
                    break

    # fallback
    if not line_id:
        lineid_match = re.search(r'ID\s*:?[\s\n]*([^\s]+)', text, re.IGNORECASE)
        if lineid_match:
            candidate = re.split(r'(複製|コピー|Copy)', lineid_match.group(1))[0].strip()
            if candidate and not is_fake_line_id(candidate):
                line_id = candidate

    if debug:
        print("OCR全文：", text)
        print("image_to_data：", words)
        print("抓到ID：", line_id)

    return phone, line_id, text, similar_id
