import re
from PIL import Image
import pytesseract

def normalize_phone(phone):
    """將+886 903 587 063、886903587063等轉為09xxxxxxxx格式"""
    if not phone:
        return None
    phone = phone.replace(" ", "").replace("-", "")
    # 若以+886或886開頭
    if phone.startswith("+886"):
        phone = "0" + phone[4:]
    elif phone.startswith("886"):
        phone = "0" + phone[3:]
    # 僅保留數字
    phone = re.sub(r'\D', '', phone)
    # 最後確認長度
    if len(phone) == 10 and phone.startswith("09"):
        return phone
    return None

def extract_lineid_phone(image_path):
    text = pytesseract.image_to_string(Image.open(image_path), lang='eng+chi_tra')
    # 找手機號
    # 支援 "0903587063", "903587063", "+886903587063", "+886 903 587 063", "886903587063", "886 903 587 063"
    phone_match = re.search(r'(09\d{8})|(?:\+?886\s?\d{2,3}\s?\d{3}\s?\d{3})', text.replace("-", ""))
    phone = None
    if phone_match:
        phone = normalize_phone(phone_match.group(0))
    # LINE ID
    lineid_match = re.search(r'LINE\s*ID[:：]?\s*([A-Za-z0-9_.-]+)', text, re.IGNORECASE)
    line_id = lineid_match.group(1) if lineid_match else None
    return phone, line_id, text
