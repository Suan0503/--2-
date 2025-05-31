import re
from PIL import Image
import pytesseract

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

def extract_lineid_phone(image_path):
    text = pytesseract.image_to_string(Image.open(image_path), lang='eng+chi_tra')
    # 手機號
    phone_match = re.search(r'(09\d{8})|(?:\+?886\s?\d{2,3}\s?\d{3}\s?\d{3})', text.replace("-", ""))
    phone = None
    if phone_match:
        phone = normalize_phone(phone_match.group(0))
    # LINE ID（去掉「複製」字）
    # 會抓 ID 開頭後面一串，遇到「複製」或空白或換行就結束
    lineid_match = re.search(r'ID\s*:?[\s\n]*([A-Za-z0-9_.-]+)', text, re.IGNORECASE)
    line_id = None
    if lineid_match:
        line_id = lineid_match.group(1)
        # 如果後面還有空白 +「複製」，把「複製」拿掉
        line_id = line_id.split("複製")[0].strip()
    return phone, line_id, text
