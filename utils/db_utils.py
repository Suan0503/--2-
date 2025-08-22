```python
from models import Whitelist, db
from datetime import datetime
from sqlalchemy.exc import IntegrityError

def update_or_create_whitelist_from_data(data, user_id, reverify=False):
    """
    根據 data 內容建立或更新白名單紀錄。
    :param data: 用戶資料 dict
    :param user_id: LINE user id
    :param reverify: 是否重新驗證 (布林值，預設 False)
    :return: (record, is_new)
    """
    record = Whitelist.query.filter_by(line_user_id=user_id).first()
    is_new = False
    phone = data.get("phone")

    if record:
        # 若 reverify，重設部分欄位及驗證時間
        if reverify:
            record.phone = data.get("phone", record.phone)
            record.name = data.get("name", record.name)
            record.line_id = data.get("line_id", record.line_id)
            record.created_at = datetime.now()
            db.session.commit()
        else:
            # 正常更新，僅補全空欄位
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
    else:
        # 如果沒有找到以 line_user_id 為 key 的紀錄，先確認是否已有相同 phone 的紀錄，
        # 避免因 phone 欄位上有 unique constraint 而拋出 IntegrityError。
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
                    # 補全空欄位
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
                record = existing_by_phone
                is_new = False
                return record, is_new

        # 若沒有相同 phone 的紀錄，嘗試新增；為了保險加上 IntegrityError 處理以避免 race condition
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
        except IntegrityError:
            # 若插入失敗（例如同時有另一個流程剛插入相同 phone），回滾並嘗試改為更新已存在的那一筆
            db.session.rollback()
            fallback = None
            if phone:
                fallback = Whitelist.query.filter_by(phone=phone).first()
            if fallback:
                # 補全必要欄位並保存
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
                record = fallback
                is_new = False
            else:
                # 若沒有 fallback，重新拋出錯誤以便上層可以觀察到異常
                raise

    return record, is_new
```
