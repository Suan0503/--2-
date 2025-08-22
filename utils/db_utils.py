from models import Whitelist, db
from datetime import datetime
from sqlalchemy.exc import IntegrityError

def update_or_create_whitelist_from_data(data, user_id, reverify=False):
    """
    根據 data 內容建立或更新 Whitelist 紀錄。
    :param data: 用戶資料 dict，應包含至少 phone，可包含 name, line_id, date
    :param user_id: LINE user id（會寫入 line_user_id）
    :param reverify: 是否為重新驗證（若為 True，會重設 created_at 並以當前 user_id 為 line_user_id）
    :return: (record, is_new)
    """
    record = Whitelist.query.filter_by(line_user_id=user_id).first()
    is_new = False
    phone = data.get("phone")

    if record:
        # 已有以 line_user_id 為 key 的紀錄，依 reverify 或補全欄位處理
        if reverify:
            record.phone = data.get("phone", record.phone)
            record.name = data.get("name", record.name)
            record.line_id = data.get("line_id", record.line_id)
            record.created_at = datetime.now()
            db.session.commit()
        else:
            updated = False
            if not record.phone and data.get("phone"):
                record.phone = data["phone"]
                updated = True
            if not record.name and data.get("name"):
                record.name = data["name"]
                updated = True
            if not record.line_id and data.get("line_id"):
                record.line_id = data["line_id"]
                updated = True
            if updated:
                db.session.commit()
        return record, is_new

    # 若沒有以 line_user_id 找到，先用 phone 檢查避免 unique constraint 衝突
    if phone:
        existing_by_phone = Whitelist.query.filter_by(phone=phone).first()
        if existing_by_phone:
            # 若為重新驗證，更新主要欄位並把 line_user_id 指回當前 user_id
            if reverify:
                existing_by_phone.name = data.get("name", existing_by_phone.name)
                existing_by_phone.line_id = data.get("line_id", existing_by_phone.line_id)
                existing_by_phone.line_user_id = user_id
                existing_by_phone.created_at = datetime.now()
                db.session.commit()
            else:
                updated = False
                if not existing_by_phone.name and data.get("name"):
                    existing_by_phone.name = data["name"]
                    updated = True
                if not existing_by_phone.line_id and data.get("line_id"):
                    existing_by_phone.line_id = data["line_id"]
                    updated = True
                if not existing_by_phone.line_user_id:
                    existing_by_phone.line_user_id = user_id
                    updated = True
                if updated:
                    db.session.commit()
            return existing_by_phone, False

    # 若仍無符合的紀錄，嘗試新增；用 try/except 處理 race condition 導致的 unique violation
    record = Whitelist(
        phone=phone,
        name=data.get("name"),
        line_id=data.get("line_id"),
        line_user_id=user_id,
        created_at=datetime.now()
    )
    db.session.add(record)
    try:
        db.session.commit()
        is_new = True
        return record, is_new
    except IntegrityError:
        # 可能因為同時插入相同 phone 而衝突，回滾並嘗試以 phone 找回那筆紀錄再更新
        db.session.rollback()
        fallback = None
        if phone:
            fallback = Whitelist.query.filter_by(phone=phone).first()
        if fallback:
            if reverify:
                fallback.name = data.get("name", fallback.name)
                fallback.line_id = data.get("line_id", fallback.line_id)
                fallback.line_user_id = user_id
                fallback.created_at = datetime.now()
                db.session.commit()
            else:
                updated = False
                if not fallback.name and data.get("name"):
                    fallback.name = data["name"]
                    updated = True
                if not fallback.line_id and data.get("line_id"):
                    fallback.line_id = data["line_id"]
                    updated = True
                if not fallback.line_user_id:
                    fallback.line_user_id = user_id
                    updated = True
                if updated:
                    db.session.commit()
            return fallback, False
        # 若找不到 fallback，重新拋出例外
        raise
