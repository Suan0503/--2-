import re
import pytesseract
from PIL import Image

def extract_lineid_phone(image_path, debug=False):
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image, lang='eng+chi_tra')

    # 手機號碼：09開頭10碼
    phone_match = re.search(r'09\d{8}', text)
    phone = phone_match.group(0) if phone_match else None

    # LINE ID：簡單常見格式，ID:xxxxx 或 ID xxxxx 或 ID：xxxxx
    lineid_match = re.search(r'ID[\s:：]{0,2}([A-Za-z0-9_\-\.]{3,})', text, re.IGNORECASE)
    lineid = lineid_match.group(1) if lineid_match else None

    if debug:
        print("OCR全文：\n", text)
        print("手機:", phone)
        print("LINE ID:", lineid)

    return phone, lineid, text

if __name__ == "__main__":
    img_path = input("請輸入圖片路徑：")
    phone, lineid, text = extract_lineid_phone(img_path, debug=True)
    print(f"\n偵測結果：\n手機號碼：{phone or '未識別'}\nLINE ID：{lineid or '未識別'}")
