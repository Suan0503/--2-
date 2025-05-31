# image_verification.py
from PIL import Image
import pytesseract
import re

def extract_lineid_phone(image_path):
    text = pytesseract.image_to_string(Image.open(image_path), lang='eng+chi_tra')
    phone_match = re.search(r'09\d{8}', text)
    lineid_match = re.search(r'LINE\s*ID[:：]?\s*([A-Za-z0-9_.-]+)', text, re.IGNORECASE)
    phone = phone_match.group(0) if phone_match else None
    line_id = lineid_match.group(1) if lineid_match else None
    return phone, line_id, text
