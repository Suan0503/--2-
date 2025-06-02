import re
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
import cv2
import numpy as np
import os

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
    def normalize_for_compare(s):
        s = normalize_text(s).lower()
        s = s.replace('0', 'o')
        s = s.replace('1', 'l')
        s = s.replace('5', 's')
        s = s.replace('i', 'l')
        return s
    return normalize_for_compare(id1) == normalize_for_compare(id2)

def generate_lineid_candidates(lineid):
    variants = set()
    base = lineid
    variants.add(base)
    variants.add(base.replace('O', '0').replace('o', '0'))
    variants.add(base.replace('0', 'O').replace('0', 'o'))
    variants.add(base.replace('l', '1'))
    variants.add(base.replace('1', 'l'))
    variants.add(base.replace('S', '5').replace('s', '5'))
    variants.add(base.replace('5', 'S').replace('5', 's'))
    variants.add(base.replace('I', '1').replace('i', '1'))
    variants.add(base.replace('1', 'I').replace('1', 'i'))
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
    variants = {v for v in variants if v and not is_fake_line_id(v)}
    return list(variants)

def detect_profile_type(image_path):
    image = Image.open(image_path)
    data = pytesseract.image_to_data(image, lang='chi_tra+eng', output_type=pytesseract.Output.DICT)
    n_boxes = len(data['level'])
    for i in range(n_boxes):
        if data['text'][i] == "個人檔案":
            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
            img_w, img_h = image.size
            x_center = x + w / 2
            is_top = y < (img_h * 0.15)
            is_center = (img_w * 0.35) < x_center < (img_w * 0.65)
            is_left = x_center < (img_w * 0.2)
            if is_top and is_center:
                return "iOS"
            elif is_top and is_left:
                return "Android"
    return "Unknown"

def specialize_ios(image):
    print("執行iOS特化處理")
    # 可加強 iOS 特化影像處理

def specialize_android(image):
    print("執行Android特化處理")
    # 可加強 Android 特化影像處理

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
    line_id_candidates = []
    if line_id:
        line_id_candidates = generate_lineid_candidates(line_id)
        line_id_candidates = [c for c in line_id_candidates if not is_fake_line_id(c)]
        line_id_candidates = list(set(line_id_candidates))
    if debug:
        print("OCR全文：", text)
        print("image_to_data：", words)
        print("抓到ID候選：", line_id_candidates)
    if len(line_id_candidates) > 1:
        return phone, line_id_candidates, text, similar_id
    elif len(line_id_candidates) == 1:
        return phone, line_id_candidates[0], text, similar_id
    else:
        return phone, None, text, similar_id

def detect_red_boxes(image_path):
    """OpenCV 偵測紅框座標，回傳 [(x, y, w, h), ...]"""
    image = cv2.imread(image_path)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 100, 100])
    upper_red2 = np.array([179, 255, 255])
    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = mask1 + mask2
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w > 30 and h > 30:  # 可依需求調整
            boxes.append((x, y, w, h))
    boxes = sorted(boxes, key=lambda b: (b[1], b[0]))
    return boxes

def crop_red_boxes(image_path, boxes, out_dir="crops"):
    """根據紅框座標裁切圖片，儲存於 crops/ 並回傳 PIL.Image 物件和路徑"""
    os.makedirs(out_dir, exist_ok=True)
    img = Image.open(image_path)
    crops = []
    for i, (x, y, w, h) in enumerate(boxes):
        crop = img.crop((x, y, x + w, y + h))
        save_path = f"{out_dir}/crop_{i+1}.jpg"
        crop.save(save_path)
        crops.append((crop, save_path))
    return crops

if __name__ == "__main__":
    img_path = input("請輸入圖片路徑：")
    boxes = detect_red_boxes(img_path)
    if not boxes:
        print("沒找到紅框！")
        exit()
    print(f"偵測到 {len(boxes)} 個紅框。")
    crops = crop_red_boxes(img_path, boxes, out_dir="crops")
    for i, (crop_img, save_path) in enumerate(crops):
        print(f"紅框 {i+1} ({save_path}) OCR 結果：")
        # 直接針對裁切圖檔做 extract_lineid_phone
        phone, lineid_result, text, similar_id_func = extract_lineid_phone(save_path, debug=True)
        print(f"手機：{phone}")
        if isinstance(lineid_result, list):
            print("請選擇正確的 LINE ID：")
            for idx, lid in enumerate(lineid_result, 1):
                print(f"{idx}. {lid}")
            user_input = input("請輸入編號選擇：")
            selected_line_id = lineid_result[int(user_input)-1]
            print(f"你選擇的 LINE ID 是: {selected_line_id}")
        else:
            print(f"LINE ID: {lineid_result}")
        print("-" * 30)
