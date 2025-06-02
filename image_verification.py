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
    if text is None:
        return ""
    return re.sub(r'[\W_]+', '', text)

def normalize_phone(phone):
    phone = phone.replace('O', '0').replace('o', '0')
    phone = re.sub(r'\D', '', phone)
    if phone.startswith('8869') and len(phone) == 12:
        phone = '09' + phone[4:]
    elif phone.startswith('09') and len(phone) == 10:
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
    """
    智慧比對 LINE ID，容許 O/0、S/5、I/1、l/1 混用
    """
    def normalize_for_compare(s):
        s = normalize_text(s).lower()
        # 全部都轉成英數最常見型態
        s = s.replace('0', 'o')
        s = s.replace('1', 'l')
        s = s.replace('5', 's')
        s = s.replace('i', 'l')
        return s
    return normalize_for_compare(id1) == normalize_for_compare(id2)

def generate_lineid_candidates(lineid):
    """
    根據 L/1、O/0、S/5、I/1 混用產生所有可能的 LINE ID 選項，去重。
    """
    variants = set()
    base = lineid
    variants.add(base)

    # O/0
    variants.add(base.replace('O', '0').replace('o', '0'))
    variants.add(base.replace('0', 'O').replace('0', 'o'))

    # l/1
    variants.add(base.replace('l', '1'))
    variants.add(base.replace('1', 'l'))

    # S/5
    variants.add(base.replace('S', '5').replace('s', '5'))
    variants.add(base.replace('5', 'S').replace('5', 's'))

    # I/1
    variants.add(base.replace('I', '1').replace('i', '1'))
    variants.add(base.replace('1', 'I').replace('1', 'i'))

    # 排列組合（只產生一層，避免無限）
    more = set()
    for v in list(variants):
        more.add(v.replace('O', '0').replace('o', '0'))
        more.add(v.replace('0', 'O').replace('0', 'o'))
        more.add(v.replace('l', '1'))
        more.add(v.replace('1', 'l'))
        more.add(v.replace('S', '5').replace('s', '5'))
        more.add(v.replace('5', 'S').replace('5', 's'))
        more.add(v.replace('I', '1').replace('i', '1'))
        more.add(v.replace('1', 'I').replace('1', 'i'))
    variants.update(more)

    # 去掉明顯 fake
    variants = {v for v in variants if v and not is_fake_line_id(v)}
    return list(variants)

def extract_lineid_phone(image_path, debug=False):
    image = preprocess_image(image_path)
    text = pytesseract.image_to_string(image, lang='eng+chi_tra')
    phone_match = re.search(r'(09\d{8})|(?:\+?886\s?\d{2,3}\s?\d{3}\s?\d{3})', text.replace("-", ""))
    phone = None
    if phone_match:
        phone = normalize_phone(phone_match.group(0))
    lineid_match = re.search(r'ID\s*:?[\s\n]*([^\s複製]+)', text, re.IGNORECASE)
    data = pytesseract.image_to_data(image, lang='eng+chi_tra', output_type=pytesseract.Output.DICT)
    words = data['text']
    line_id = None
    if lineid_match:
        candidate = lineid_match.group(1).strip()
        if candidate and not is_fake_line_id(candidate):
            line_id = candidate

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

    if not line_id:
        lineid_match = re.search(r'ID\s*:?[\s\n]*([^\s]+)', text, re.IGNORECASE)
        if lineid_match:
            candidate = re.split(r'(複製|コピー|Copy)', lineid_match.group(1))[0].strip()
            if candidate and not is_fake_line_id(candidate):
                line_id = candidate

    # 產生候選清單
    line_id_candidates = []
    if line_id:
        line_id_candidates = generate_lineid_candidates(line_id)
        line_id_candidates = [c for c in line_id_candidates if not is_fake_line_id(c)]
        line_id_candidates = list(set(line_id_candidates))

    if debug:
        print("OCR全文：", text)
        print("image_to_data：", words)
        print("抓到ID候選：", line_id_candidates)

    # 回傳時
    if len(line_id_candidates) > 1:
        return phone, line_id_candidates, text, similar_id
    elif len(line_id_candidates) == 1:
        return phone, line_id_candidates[0], text, similar_id
    else:
        return phone, None, text, similar_id

# --- CLI互動範例 ---
if __name__ == "__main__":
    img_path = input("請輸入圖片路徑：")
    phone, lineid_result, text, similar_id_func = extract_lineid_phone(img_path, debug=True)
    print(f"【圖片偵測結果】\n手機:{phone}")
    # 如果有多個候選，讓用戶選擇
    if isinstance(lineid_result, list):
        print("請選擇正確的 LINE ID：")
        for idx, lid in enumerate(lineid_result, 1):
            print(f"{idx}. {lid}")
        user_input = input("請輸入編號選擇：")
        selected_line_id = lineid_result[int(user_input)-1]
        print(f"你選擇的 LINE ID 是: {selected_line_id}")
    else:
        print(f"LINE ID: {lineid_result}")
