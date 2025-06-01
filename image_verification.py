import re
from PIL import Image, ImageEnhance
import pytesseract

def preprocess_image(image_path):
    image = Image.open(image_path)
    # 轉灰階
    image = image.convert('L')
    # 增強對比
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2)
    # 簡單二值化
    image = image.point(lambda x: 0 if x < 140 else 255, '1')
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

def extract_lineid_phone(image_path):
    # 新增預處理流程
    image = preprocess_image(image_path)
    text = pytesseract.image_to_string(image, lang='eng+chi_tra')
    # 手機號
    phone_match = re.search(r'(09\d{8})|(?:\+?886\s?\d{2,3}\s?\d{3}\s?\d{3})', text.replace("-", ""))
    phone = None
    if phone_match:
        phone = normalize_phone(phone_match.group(0))
    # LINE ID（去掉「複製」字）
    lineid_match = re.search(r'ID\s*:?[\s\n]*([A-Za-z0-9_.-]+)', text, re.IGNORECASE)
    line_id = None
    if lineid_match:
        line_id = lineid_match.group(1)
        line_id = line_id.split("複製")[0].strip()
    return phone, line_id, text
