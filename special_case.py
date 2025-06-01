# special_case.py

import json
import threading

SPECIAL_CASE_FILE = "special_case_list.json"
_lock = threading.Lock()

def load_special_cases():
    try:
        with open(SPECIAL_CASE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_special_cases(cases):
    with open(SPECIAL_CASE_FILE, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

def is_special_case(user_id):
    cases = load_special_cases()
    return user_id in cases

def add_special_case(user_id):
    with _lock:
        cases = load_special_cases()
        if user_id not in cases:
            cases.append(user_id)
            save_special_cases(cases)
            return True
        return False
