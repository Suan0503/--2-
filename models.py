from extensions import db
from datetime import datetime, timedelta

class TempVerify(db.Model):
    __tablename__ = "temp_verify"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    phone = db.Column(db.String(20))
    line_id = db.Column(db.String(100))
    nickname = db.Column(db.String(255))
    line_user_id = db.Column(db.String(255))
    status = db.Column(db.String(20), default="pending")  # pending/verified/failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ManualVerifyCode(db.Model):
    __tablename__ = "manual_verify_code"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    phone = db.Column(db.String(20), unique=True)
    code = db.Column(db.String(8))
    nickname = db.Column(db.String(255))
    line_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Whitelist(db.Model):
    __tablename__ = "whitelist"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    name = db.Column(db.String(255))
    line_id = db.Column(db.String(100))
    line_user_id = db.Column(db.String(255), unique=True)

class Blacklist(db.Model):
    __tablename__ = "blacklist"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    date = db.Column(db.String(20))
    phone = db.Column(db.String(20), unique=True)
    reason = db.Column(db.Text)
    name = db.Column(db.String(255))

class Coupon(db.Model):
    __tablename__ = "coupon"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    line_user_id = db.Column(db.String(255))
    date = db.Column(db.String(20))
    amount = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    report_no = db.Column(db.String(20))  # 新增的流水抽獎券編號
    type = db.Column(db.String(20), default="draw")  # 新增：來源類型 "draw" or "report"


# 儲值金錢包
class StoredValueWallet(db.Model):
    __tablename__ = "stored_value_wallet"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 對應白名單使用者（非強制外鍵，避免跨 DB 差異）
    whitelist_id = db.Column(db.Integer, index=True)
    phone = db.Column(db.String(20), index=True)
    balance = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    # 每日到期提醒用
    last_coupon_notice_at = db.Column(db.DateTime)


# 儲值金交易紀錄
class StoredValueTransaction(db.Model):
    __tablename__ = "stored_value_txn"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    wallet_id = db.Column(db.Integer, index=True, nullable=False)
    type = db.Column(db.String(20), nullable=False)  # topup / consume
    amount = db.Column(db.Integer, nullable=False)
    remark = db.Column(db.Text)  # 例如預約記錄
    # 精準對帳欄位
    payment_method = db.Column(db.String(50))  # CASH, BANK, CARD, TWQR, OTHER
    reference_id = db.Column(db.String(100))   # 交易序號/匯款後五碼等
    operator = db.Column(db.String(100))       # 經手人
    coupon_500_count = db.Column(db.Integer, default=0, nullable=False)
    coupon_300_count = db.Column(db.Integer, default=0, nullable=False)
    # 新增 100 券
    coupon_100_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class WageConfig(db.Model):
    __tablename__ = 'wage_config'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    wage_40 = db.Column(db.Integer, nullable=False, default=0)
    wage_60 = db.Column(db.Integer, nullable=False, default=0)
    wage_90 = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class ExternalUser(db.Model):
    __tablename__ = 'external_user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    # Multi-company & roles
    role = db.Column(db.String(50), nullable=False, default='user')  # super_admin | paid_admin | operator | user
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)
    # Membership expiration (default +30 days from creation)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

class Company(db.Model):
    __tablename__ = 'company'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())

class CompanyUser(db.Model):
    __tablename__ = 'company_user'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('external_user.id'), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')
    created_at = db.Column(db.DateTime, default=db.func.now())

class FeatureFlag(db.Model):
    __tablename__ = 'feature_flag'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    enabled = db.Column(db.Boolean, default=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=db.func.now())
    # Optional scoping per company (null = global)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=True)

def ensure_external_user_defaults(user: ExternalUser):
    """Ensure expires_at default if missing."""
    if user and user.expires_at is None:
        user.expires_at = datetime.utcnow() + timedelta(days=30)
