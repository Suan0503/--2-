

from models import Whitelist
from extensions import db
from datetime import datetime, timezone
try:
    from sqlalchemy.exc import IntegrityError
except ImportError:
    IntegrityError = Exception
import logging

def _now():
    return datetime.now(timezone.utc)

def _safe_commit():
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"DB commit failed: {e}")
        raise

def _fill_fields(obj, data, fields, user_id=None, reverify=False):
    for field in fields:
        if field == "line_user_id" and user_id:
            setattr(obj, field, user_id)
        elif reverify:
            setattr(obj, field, data.get(field, getattr(obj, field, None)))
        elif not getattr(obj, field, None) and data.get(field):
            setattr(obj, field, data[field])

def update_or_create_whitelist_from_data(data, user_id, reverify=False):
    """
    根據 data 內容建立或更新 Whitelist 紀錄。
    :param data: 用戶資料 dict，應包含至少 phone，可包含 name, line_id, date
    :param user_id: LINE user id（會寫入 line_user_id）
    :param reverify: 是否為重新驗證（若為 True，會重設 created_at 並以當前 user_id 為 line_user_id）
    :return: (record, is_new)
    """
    fields = ["phone", "name", "line_id", "line_user_id", "created_at"]
    phone = data.get("phone")
    is_new = False

    record = Whitelist.query.filter_by(line_user_id=user_id).first()
    if record:
        _fill_fields(record, data, fields, user_id, reverify)
        record.created_at = _now() if reverify else record.created_at
        _safe_commit()
        return record, is_new

    if phone:
        existing_by_phone = Whitelist.query.filter_by(phone=phone).first()
        if existing_by_phone:
            _fill_fields(existing_by_phone, data, fields, user_id, reverify)
            existing_by_phone.created_at = _now() if reverify else existing_by_phone.created_at
            _safe_commit()
            return existing_by_phone, False

    record = Whitelist(
        phone=phone,
        name=data.get("name"),
        line_id=data.get("line_id"),
        line_user_id=user_id,
        created_at=_now()
    )
    db.session.add(record)
    try:
        _safe_commit()
        is_new = True
        return record, is_new
    except IntegrityError:
        db.session.rollback()
        logging.warning("IntegrityError on insert Whitelist, trying fallback by phone")
        fallback = Whitelist.query.filter_by(phone=phone).first() if phone else None
        if fallback:
            _fill_fields(fallback, data, fields, user_id, reverify)
            fallback.created_at = _now() if reverify else fallback.created_at
            _safe_commit()
            return fallback, False
        raise
