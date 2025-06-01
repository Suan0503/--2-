import re
from PIL import Image, ImageEnhance, ImageOps
import pytesseract

def preprocess_image(image_path):
    image = Image.open(image_path)
    # 灰階
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
    image = preprocess_image(image_path)
    text = pytesseract.image_to_string(image, lang='eng+chi_tra')
    # 手機號
    phone_match = re.search(r'(09\d{8})|(?:\+?886\s?\d{2,3}\s?\d{3}\s?\d{3})', text.replace("-", ""))
    phone = None
    if phone_match:
        phone = normalize_phone(phone_match.group(0))
    # LINE ID 抓取直到遇到空白、換行或「複製」就停止
    lineid_match = re.search(r'ID\s*:?[\s\n]*([^\s複製]+)', text, re.IGNORECASE)
    line_id = None
    if lineid_match:
        line_id = lineid_match.group(1).strip()
    return phone, line_id, text
