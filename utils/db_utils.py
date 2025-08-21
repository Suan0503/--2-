from models import Whitelist, db
from datetime import datetime

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
        # 新增白名單資料
        record = Whitelist(
            phone=data.get("phone"),
            name=data.get("name"),
            line_id=data.get("line_id"),
            line_user_id=user_id,
            created_at=datetime.now()
        )
        db.session.add(record)
        db.session.commit()
        is_new = True

    return record, is_new
