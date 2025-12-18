import os
import sys
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_wtf import CSRFProtect
from flask_wtf.csrf import generate_csrf
from sqlalchemy import text
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass  # 若未安裝 python-dotenv 不影響執行

# 保證本目錄可匯入
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from extensions import db
from flask_migrate import Migrate
from routes.message import message_bp
from routes.pending_verify import pending_bp
from routes.admin import admin_bp
from routes.external import external_bp
from models import Whitelist, Blacklist, TempVerify, Coupon
import secrets

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
csrf = CSRFProtect(app)

# Railway / Heroku 資料庫 URL 轉換
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if not DATABASE_URL:
    # Local fallback to SQLite for stability in dev environments
    DATABASE_URL = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'app.db')}"
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
migrate = Migrate(app, db, directory=os.path.join(os.path.dirname(__file__), 'migrations'))

# APScheduler：每日清除過期優惠券（若有殘留未查詢）
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler(timezone='Asia/Taipei')

    def expire_coupons_job():
        from models import StoredValueWallet, StoredValueTransaction
        import pytz
        from datetime import datetime as _dt
        tz = pytz.timezone('Asia/Taipei')
        now_dt = _dt.now(tz)
        expire_dt = tz.localize(_dt(now_dt.year, 12, 31, 23, 59, 59))
        if now_dt.date() != expire_dt.date():
            return  # 僅在 12/31 當天執行一次批次清除
        wallets = StoredValueWallet.query.all()
        for w in wallets:
            txns = StoredValueTransaction.query.filter_by(wallet_id=w.id).all()
            c500 = c300 = c100 = 0
            for t in txns:
                sign = 1 if t.type == 'topup' else -1
                c500 += sign * (t.coupon_500_count or 0)
                c300 += sign * (t.coupon_300_count or 0)
                try:
                    c100 += sign * (getattr(t, 'coupon_100_count', 0) or 0)
                except Exception:
                    pass
            c500 = max(c500,0)
            c300 = max(c300,0)
            c100 = max(c100,0)
            if c500 > 0 or c300 > 0 or c100 > 0:
                try:
                    txn = StoredValueTransaction()
                    txn.wallet_id = w.id
                    txn.type = 'consume'
                    txn.amount = 0
                    txn.remark = f"AUTO_EXPIRE {expire_dt.strftime('%Y/%m/%d')}"
                    txn.coupon_500_count = c500
                    txn.coupon_300_count = c300
                    try:
                        txn.coupon_100_count = c100
                    except Exception:
                        pass
                    db.session.add(txn)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
    scheduler.add_job(expire_coupons_job, 'cron', hour=0, minute=10, id='expire_coupons_daily')

    # 每日 02:00 自動清除「待驗證名單」（temp_verify 狀態為 pending）
    def clear_pending_verify_job():
        from models import TempVerify
        try:
            # 僅刪除仍為 pending 的暫存驗證資料
            pending = TempVerify.query.filter_by(status='pending').all()
            for item in pending:
                db.session.delete(item)
            if pending:
                db.session.commit()
            else:
                db.session.rollback()
        except Exception:
            db.session.rollback()

    scheduler.add_job(clear_pending_verify_job, 'cron', hour=2, minute=0, id='clear_pending_verify_daily')
    scheduler.start()
except Exception:
    pass  # 若未安裝 apscheduler 則略過排程功能

"""Blueprint 註冊"""
app.register_blueprint(message_bp)
csrf.exempt(message_bp)  # 豁免 LINE Webhook /callback 不使用 CSRF Token
app.register_blueprint(pending_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(external_bp)

"""admin 相關路由已移至 routes/admin.py 的 Blueprint"""

@app.route('/home')
def home():
    try:
        db.session.execute(text('SELECT 1'))
        db_status = '資料庫連線正常'
    except Exception as e:
        db_status = '資料庫連線異常: ' + str(e)
    return f"LINE Bot 正常運作中～🍵\n{db_status}"

@app.route('/')
def index():
    return redirect('/home')

@app.route('/search')
def search():
    q = request.args.get('q','').strip()
    results = []
    if q:
        wl = Whitelist.query.filter(Whitelist.phone.like(f"%{q}%") | Whitelist.name.like(f"%{q}%") | Whitelist.line_id.like(f"%{q}%")).all()
        for w in wl:
            results.append({'type':'白名單','phone':w.phone,'name':w.name,'line_id':w.line_id})
        bl = Blacklist.query.filter(Blacklist.phone.like(f"%{q}%") | Blacklist.name.like(f"%{q}%")).all()
        for b in bl:
            results.append({'type':'黑名單','phone':b.phone,'name':b.name})
        cp = Coupon.query.filter(Coupon.line_user_id.like(f"%{q}%") | Coupon.report_no.like(f"%{q}%")).all()
        for c in cp:
            results.append({'type':'抽獎券','line_user_id':c.line_user_id,'report_no':c.report_no,'amount':c.amount})
    return render_template('search_result.html', q=q, results=results)

@app.errorhandler(404)
def not_found(e):
    try:
        return render_template('404_modern.html'), 404
    except Exception:
        return 'Not Found', 404

@app.route('/line_status')
def line_status():
    from extensions import ACCESS_TOKEN, CHANNEL_SECRET, line_bot_api
    ok_env = bool(ACCESS_TOKEN and CHANNEL_SECRET)
    profile_ok = False
    try:
        # 嘗試呼叫 API（以空白 user id 會失敗，但可證明物件存在）；這裡只檢查屬性是否存在
        getattr(line_bot_api, 'push_message', None)
        profile_ok = True
    except Exception:
        profile_ok = False
    return {
        'env_ready': ok_env,
        'api_ready': profile_ok,
        'webhook': '/callback',
        'hint': '請在 LINE Developers 將 Webhook 指向 /callback 並開啟。'
    }

@app.route('/api/wallet')
def api_wallet():
    from models import StoredValueWallet, StoredValueTransaction
    phone = request.args.get('phone','').strip()
    if not phone:
        return {'error': 'missing phone'}, 400
    wl = Whitelist.query.filter_by(phone=phone).first()
    if not wl or not wl.line_user_id:
        return {'error': 'not verified'}, 403
    wallet = StoredValueWallet.query.filter_by(phone=phone).first()
    if not wallet:
        return {'phone': phone, 'balance': 0, 'coupon_500': 0, 'coupon_300': 0, 'coupon_100': 0, 'transactions': []}
    txns_all = StoredValueTransaction.query.filter_by(wallet_id=wallet.id).order_by(StoredValueTransaction.created_at.asc()).all()
    c500 = c300 = c100 = 0
    for t in txns_all:
        sign = 1 if t.type == 'topup' else -1
        c500 += sign * (t.coupon_500_count or 0)
        c300 += sign * (t.coupon_300_count or 0)
        try:
            c100 += sign * (getattr(t, 'coupon_100_count', 0) or 0)
        except Exception:
            pass
    # 到期判斷（與前端一致）
    import pytz
    from datetime import datetime as _dt
    tz = pytz.timezone('Asia/Taipei')
    now_dt = _dt.now(tz)
    expire_dt = tz.localize(_dt(now_dt.year, 12, 31, 23, 59, 59))
    if now_dt > expire_dt:
        c500 = 0
        c300 = 0
        c100 = 0
    # 最近 20 筆交易概要
    recent = []
    for t in txns_all[-20:]:
        recent.append({
            'time': t.created_at.isoformat() if t.created_at else None,
            'type': t.type,
            'amount': t.amount,
            'c500': t.coupon_500_count,
            'c300': t.coupon_300_count,
            'c100': getattr(t, 'coupon_100_count', 0),
            'remark': t.remark
        })
    return {
        'phone': phone,
        'balance': wallet.balance,
        'coupon_500': max(c500,0),
        'coupon_300': max(c300,0),
        'coupon_100': max(c100,0),
        'last_notice_at': wallet.last_coupon_notice_at.isoformat() if wallet.last_coupon_notice_at else None,
        'transactions': recent
    }

# 提供 csrf_token() 給模板
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf)

# 啟動前初始化（優先遷移，失敗則 create_all）
with app.app_context():
    migrations_path = os.path.join(os.path.dirname(__file__), 'migrations')
    used_create_all = False
    if os.path.isdir(migrations_path):
        try:
            from flask_migrate import upgrade as _upgrade, stamp as _stamp
            _upgrade(migrations_path)
        except Exception as e:
            # upgrade 失敗則退回 create_all，之後 stamp head 讓未來 upgrade 可以接續
            db.create_all()
            used_create_all = True
            try:
                # stamp to latest known revision to align DB with migrations state
                from flask_migrate import stamp as _stamp  # ensure defined in this scope
                _stamp(migrations_path, '0003_add_wallet_notice')
            except Exception:
                pass
    else:
        db.create_all()
        used_create_all = True
        try:
            from flask_migrate import stamp as _stamp
            _stamp(migrations_path, '0003_add_wallet_notice')
        except Exception:
            pass

    # 兼容補丁：確保 temp_verify 有 line_user_id 欄位（PostgreSQL 支援 IF NOT EXISTS）
    try:
        db.session.execute(text("ALTER TABLE temp_verify ADD COLUMN IF NOT EXISTS line_user_id VARCHAR(255)"))
        db.session.commit()
    except Exception:
        db.session.rollback()
    # 兼容補丁：確保 stored_value_wallet 有 last_coupon_notice_at 欄位
    try:
        # PostgreSQL 支援 IF NOT EXISTS
        db.session.execute(text("ALTER TABLE stored_value_wallet ADD COLUMN IF NOT EXISTS last_coupon_notice_at TIMESTAMP"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        # SQLite 無 IF NOT EXISTS：檢查後再新增
        try:
            engine_name = db.get_engine().name
            if engine_name == 'sqlite':
                info = db.session.execute(text("PRAGMA table_info(stored_value_wallet)")).fetchall()
                cols = {row[1] for row in info}
                if 'last_coupon_notice_at' not in cols:
                    db.session.execute(text("ALTER TABLE stored_value_wallet ADD COLUMN last_coupon_notice_at TIMESTAMP"))
                    db.session.commit()
        except Exception:
            db.session.rollback()

    # 兼容補丁：確保 stored_value_txn 有 coupon_100_count 欄位
    try:
        db.session.execute(text("ALTER TABLE stored_value_txn ADD COLUMN IF NOT EXISTS coupon_100_count INTEGER DEFAULT 0 NOT NULL"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            engine_name = db.get_engine().name
            if engine_name == 'sqlite':
                info = db.session.execute(text("PRAGMA table_info(stored_value_txn)")).fetchall()
                cols = {row[1] for row in info}
                if 'coupon_100_count' not in cols:
                    db.session.execute(text("ALTER TABLE stored_value_txn ADD COLUMN coupon_100_count INTEGER DEFAULT 0 NOT NULL"))
                    db.session.commit()
        except Exception:
            db.session.rollback()

    # 兼容補丁：精準對帳欄位（payment_method, reference_id, operator）
    try:
        db.session.execute(text("ALTER TABLE stored_value_txn ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50)"))
        db.session.execute(text("ALTER TABLE stored_value_txn ADD COLUMN IF NOT EXISTS reference_id VARCHAR(100)"))
        db.session.execute(text("ALTER TABLE stored_value_txn ADD COLUMN IF NOT EXISTS operator VARCHAR(100)"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            engine_name = db.get_engine().name
            if engine_name == 'sqlite':
                info = db.session.execute(text("PRAGMA table_info(stored_value_txn)")).fetchall()
                cols = {row[1] for row in info}
                alters = []
                if 'payment_method' not in cols:
                    alters.append("ALTER TABLE stored_value_txn ADD COLUMN payment_method VARCHAR(50)")
                if 'reference_id' not in cols:
                    alters.append("ALTER TABLE stored_value_txn ADD COLUMN reference_id VARCHAR(100)")
                if 'operator' not in cols:
                    alters.append("ALTER TABLE stored_value_txn ADD COLUMN operator VARCHAR(100)")
                for sql in alters:
                    db.session.execute(text(sql))
                if alters:
                    db.session.commit()
        except Exception:
            db.session.rollback()

    # 兼容補丁：多公司與會員欄位
    # 建立 company 與 company_user 表（SQLite/PG 簡單兼容，PG 用 IF NOT EXISTS）
    try:
        db.session.execute(text("CREATE TABLE IF NOT EXISTS company (id SERIAL PRIMARY KEY, name VARCHAR(255) UNIQUE, created_at TIMESTAMP, updated_at TIMESTAMP)"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            engine_name = db.get_engine().name
            if engine_name == 'sqlite':
                db.session.execute(text("CREATE TABLE IF NOT EXISTS company (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(255) UNIQUE, created_at TIMESTAMP, updated_at TIMESTAMP)"))
                db.session.commit()
        except Exception:
            db.session.rollback()
    try:
        db.session.execute(text("CREATE TABLE IF NOT EXISTS company_user (id SERIAL PRIMARY KEY, company_id INTEGER, user_id INTEGER, role VARCHAR(50), created_at TIMESTAMP)"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            engine_name = db.get_engine().name
            if engine_name == 'sqlite':
                db.session.execute(text("CREATE TABLE IF NOT EXISTS company_user (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER, user_id INTEGER, role VARCHAR(50), created_at TIMESTAMP)"))
                db.session.commit()
        except Exception:
            db.session.rollback()

    # external_user 欄位：role, company_id, expires_at
    try:
        db.session.execute(text("ALTER TABLE external_user ADD COLUMN IF NOT EXISTS role VARCHAR(50)"))
        db.session.execute(text("ALTER TABLE external_user ADD COLUMN IF NOT EXISTS company_id INTEGER"))
        db.session.execute(text("ALTER TABLE external_user ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            engine_name = db.get_engine().name
            if engine_name == 'sqlite':
                info = db.session.execute(text("PRAGMA table_info(external_user)")).fetchall()
                cols = {row[1] for row in info}
                alters = []
                if 'role' not in cols:
                    alters.append("ALTER TABLE external_user ADD COLUMN role VARCHAR(50)")
                if 'company_id' not in cols:
                    alters.append("ALTER TABLE external_user ADD COLUMN company_id INTEGER")
                if 'expires_at' not in cols:
                    alters.append("ALTER TABLE external_user ADD COLUMN expires_at TIMESTAMP")
                for sql in alters:
                    db.session.execute(text(sql))
                if alters:
                    db.session.commit()
        except Exception:
            db.session.rollback()

    # feature_flag 欄位：company_id
    try:
        db.session.execute(text("ALTER TABLE feature_flag ADD COLUMN IF NOT EXISTS company_id INTEGER"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            engine_name = db.get_engine().name
            if engine_name == 'sqlite':
                info = db.session.execute(text("PRAGMA table_info(feature_flag)")).fetchall()
                cols = {row[1] for row in info}
                if 'company_id' not in cols:
                    db.session.execute(text("ALTER TABLE feature_flag ADD COLUMN company_id INTEGER"))
                    db.session.commit()
        except Exception:
            db.session.rollback()

    # 預設超級管理員帳號密碼（若不存在）
    try:
        from models import ExternalUser
        from werkzeug.security import generate_password_hash
        admin = ExternalUser.query.filter_by(email='mingteagood').first()
        if not admin:
            admin = ExternalUser()
            admin.email = 'mingteagood'
            admin.password_hash = generate_password_hash('88888888')
            admin.is_active = True
            try:
                admin.role = 'super_admin'
            except Exception:
                pass
            db.session.add(admin)
            db.session.commit()
    except Exception:
        db.session.rollback()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
