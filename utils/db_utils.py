from models import db, Whitelist
from datetime import datetime

def update_or_create_whitelist_from_data(data, user_id=None):
    """
    用戶手機號碼重複時，直接補齊原本缺的欄位，不會覆蓋已填寫的舊值。若無則新增。
    :param data: dict, 包含 phone、name、line_id、reason、date 等欄位
    :param user_id: LINE 用戶 id
    :return: (record, is_new) -> record: Whitelist 物件, is_new: 是否新建
    """
    existing = Whitelist.query.filter_by(phone=data["phone"]).first()
    need_commit = False
    if existing:
        # 只補空的欄位，不覆蓋已存在的值
        if data.get("name") and not existing.name:
            existing.name = data["name"]
            need_commit = True
        if data.get("line_id") and not existing.line_id:
            existing.line_id = data["line_id"]
            need_commit = True
        if user_id and not existing.line_user_id:
            existing.line_user_id = user_id
            need_commit = True
        if data.get("reason") and not existing.reason:
            existing.reason = data["reason"]
            need_commit = True
        if data.get("date") and not existing.date:
            existing.date = data["date"]
            need_commit = True
        if need_commit:
            db.session.commit()
        return existing, False  # False 代表覆寫
    else:
        new_user = Whitelist(
            phone=data["phone"],
            name=data.get("name"),
            line_id=data.get("line_id"),
            line_user_id=user_id if user_id else data.get("line_user_id"),
            reason=data.get("reason"),
            date=data.get("date"),
            created_at=datetime.utcnow()
        )
        db.session.add(new_user)
        db.session.commit()
        return new_user, True  # True 代表新建

def is_user_verified(line_user_id):
    return Whitelist.query.filter_by(line_user_id=line_user_id).first() is not None
