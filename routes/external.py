from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db
from models import ExternalUser, FeatureFlag, Company, CompanyUser
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

external_bp = Blueprint('external', __name__)

@external_bp.route('/')
def external_home():
    uid = session.get('ext_user_id')
    user = ExternalUser.query.get(uid) if uid else None
    from datetime import datetime as _dt
    return render_template('home_modern.html', user=user, now=_dt.now)

@external_bp.route('/login', methods=['GET','POST'])
def external_login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = (request.form.get('password') or '').strip()
        user = ExternalUser.query.filter_by(email=email, is_active=True).first()
        if not user:
            # 允許以使用者名稱（非 email）登入，匹配我們預設的管理員帳號
            user = ExternalUser.query.filter_by(email=(request.form.get('email') or '').strip()).first()
        if user and check_password_hash(user.password_hash, password):
            session['ext_user_id'] = user.id
            return redirect(url_for('external.features'))
        flash('登入失敗','danger')
    return render_template('external_login.html')

@external_bp.route('/register', methods=['GET','POST'])
def external_register():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = (request.form.get('password') or '').strip()
        if not email or not password:
            flash('缺少必要欄位','warning')
            return redirect(url_for('external.external_register'))
        exists = ExternalUser.query.filter_by(email=email).first()
        if exists:
            flash('Email 已被註冊','danger')
            return redirect(url_for('external.external_register'))
        u = ExternalUser()
        u.email = email
        u.password_hash = generate_password_hash(password)
        u.is_active = True
        # default role & membership
        if not getattr(u, 'role', None):
            u.role = 'user'
        if not getattr(u, 'expires_at', None):
            u.expires_at = datetime.utcnow() + timedelta(days=30)
        db.session.add(u)
        db.session.commit()
        flash('註冊成功，請登入','success')
        return redirect(url_for('external.external_login'))
    return render_template('external_register.html')

def _require_ext_login():
    uid = session.get('ext_user_id')
    if not uid:
        return False
    return True

@external_bp.route('/features', methods=['GET','POST'])
def features():
    if not _require_ext_login():
        return redirect(url_for('external.external_login'))
    if request.method == 'POST':
        # 簡易開關（示範）：根據提交的鍵更新 enabled。付費流程另接第三方。
        for f in FeatureFlag.query.all():
            enabled = request.form.get(f'flag_{f.key}') == 'on'
            f.enabled = enabled
        db.session.commit()
        flash('已更新功能開關','success')
    flags = FeatureFlag.query.order_by(FeatureFlag.name.asc()).all()
    # Remaining days countdown
    uid = session.get('ext_user_id')
    user = ExternalUser.query.get(uid) if uid else None
    remaining_days = None
    if user and getattr(user, 'expires_at', None):
        try:
            remaining_days = max(0, (user.expires_at - datetime.utcnow()).days)
        except Exception:
            remaining_days = None
    return render_template('external_features.html', flags=flags, remaining_days=remaining_days, user=user)

@external_bp.route('/admin', methods=['GET','POST'])
def admin_dashboard():
    # Placeholder: super admin dashboard (company & users management)
    if not _require_ext_login():
        return redirect(url_for('external.external_login'))
    uid = session.get('ext_user_id')
    u = ExternalUser.query.get(uid)
    if not u or getattr(u, 'role', 'user') != 'super_admin':
        flash('需要超級管理員權限','warning')
        return redirect(url_for('external.features'))
    companies = Company.query.order_by(Company.name.asc()).all()
    users = ExternalUser.query.order_by(ExternalUser.created_at.desc()).all()
    return render_template('external_admin.html', companies=companies, users=users)

@external_bp.route('/company', methods=['GET','POST'])
def company_dashboard():
    # Placeholder: company admin dashboard
    if not _require_ext_login():
        return redirect(url_for('external.external_login'))
    uid = session.get('ext_user_id')
    u = ExternalUser.query.get(uid)
    if not u or getattr(u, 'role', 'user') not in ('super_admin','paid_admin','operator'):
        flash('需要公司權限','warning')
        return redirect(url_for('external.features'))
    # 目前以使用者的 company_id 為主
    companies = Company.query.order_by(Company.name.asc()).all()
    members = ExternalUser.query.filter_by(company_id=u.company_id).order_by(ExternalUser.created_at.desc()).all() if u.company_id else []
    return render_template('external_company.html', companies=companies, members=members, me=u)

@external_bp.route('/admin/embed')
def admin_embed():
    """將內部 /admin 子頁嵌入外部頁面 via iframe。
    安全措施：僅允許白名單的子路徑，並且不帶危險查詢參數。
    """
    if not _require_ext_login():
        return redirect(url_for('external.external_login'))
    uid = session.get('ext_user_id')
    u = ExternalUser.query.get(uid)
    if not u or getattr(u, 'role', 'user') not in ('super_admin','paid_admin','operator'):
        flash('需要管理員或操作員權限','warning')
        return redirect(url_for('external.features'))
    path = (request.args.get('path') or 'home').strip()
    # 白名單：允許嵌入的 /admin 子路徑
    allowed = {
        'home': '/admin/home',
        'dashboard': '/admin/dashboard',
        'schedule': '/admin/schedule/',
        'wallet': '/admin/wallet',
        'wallet_summary': '/admin/wallet/summary',
        'wallet_reconcile': '/admin/wallet/reconcile',
        'wallet_reconcile_consume': '/admin/wallet/reconcile_consume',
        'wallet_reconcile_adjusted': '/admin/wallet/reconcile_adjusted',
        'whitelist_search': '/admin/whitelist/search',
        'blacklist_search': '/admin/blacklist/search',
        # 可逐步擴充
    }
    target = allowed.get(path)
    if not target:
        flash('不支援的內部頁面','warning')
        return redirect(url_for('external.features'))
    # 組合絕對 URL（同站域名）
    origin = request.host_url.rstrip('/')
    embed_url = origin + target
    return render_template('external_embed.html', embed_url=embed_url, path=path)

@external_bp.route('/admin/company/create', methods=['POST'])
def admin_company_create():
    if not _require_ext_login():
        return redirect(url_for('external.external_login'))
    uid = session.get('ext_user_id')
    u = ExternalUser.query.get(uid)
    if not u or getattr(u, 'role', 'user') != 'super_admin':
        flash('需要超級管理員權限','warning')
        return redirect(url_for('external.features'))
    name = (request.form.get('name') or '').strip()
    if not name:
        flash('公司名稱必填','danger')
        return redirect(url_for('external.admin_dashboard'))
    if Company.query.filter_by(name=name).first():
        flash('公司名稱已存在','danger')
        return redirect(url_for('external.admin_dashboard'))
    c = Company()
    c.name = name
    db.session.add(c)
    db.session.commit()
    flash('已建立公司','success')
    return redirect(url_for('external.admin_dashboard'))

@external_bp.route('/admin/user/role', methods=['POST'])
def admin_user_role():
    if not _require_ext_login():
        return redirect(url_for('external.external_login'))
    uid = session.get('ext_user_id')
    u = ExternalUser.query.get(uid)
    if not u or getattr(u, 'role', 'user') != 'super_admin':
        flash('需要超級管理員權限','warning')
        return redirect(url_for('external.features'))
    user_id = request.form.get('user_id')
    role = (request.form.get('role') or '').strip()
    target = ExternalUser.query.get(user_id)
    if target:
        target.role = role if role in ('super_admin','paid_admin','operator','user') else 'user'
        db.session.commit()
        flash('已更新使用者角色','success')
    return redirect(url_for('external.admin_dashboard'))

@external_bp.route('/admin/user/company', methods=['POST'])
def admin_user_company():
    if not _require_ext_login():
        return redirect(url_for('external.external_login'))
    uid = session.get('ext_user_id')
    u = ExternalUser.query.get(uid)
    if not u or getattr(u, 'role', 'user') != 'super_admin':
        flash('需要超級管理員權限','warning')
        return redirect(url_for('external.features'))
    user_id = request.form.get('user_id')
    company_id = request.form.get('company_id')
    target = ExternalUser.query.get(user_id)
    if target:
        target.company_id = int(company_id) if company_id else None
        db.session.commit()
        flash('已更新使用者公司','success')
    return redirect(url_for('external.admin_dashboard'))

@external_bp.route('/company/user/role', methods=['POST'])
def company_user_role():
    if not _require_ext_login():
        return redirect(url_for('external.external_login'))
    uid = session.get('ext_user_id')
    u = ExternalUser.query.get(uid)
    if not u or getattr(u, 'role', 'user') not in ('super_admin','paid_admin','operator'):
        flash('需要公司權限','warning')
        return redirect(url_for('external.features'))
    user_id = request.form.get('user_id')
    role = (request.form.get('role') or '').strip()
    target = ExternalUser.query.get(user_id)
    if target and target.company_id == u.company_id:
        target.role = role if role in ('paid_admin','operator','user') else 'user'
        db.session.commit()
        flash('已更新公司成員角色','success')
    return redirect(url_for('external.company_dashboard'))

@external_bp.route('/company/user/membership', methods=['POST'])
def company_user_membership():
    if not _require_ext_login():
        return redirect(url_for('external.external_login'))
    uid = session.get('ext_user_id')
    u = ExternalUser.query.get(uid)
    if not u or getattr(u, 'role', 'user') not in ('super_admin','paid_admin','operator'):
        flash('需要公司權限','warning')
        return redirect(url_for('external.features'))
    user_id = request.form.get('user_id')
    action = (request.form.get('action') or '').strip()  # add/deduct
    days = int(request.form.get('days') or 0)
    target = ExternalUser.query.get(user_id)
    if target and target.company_id == u.company_id and days:
        base = target.expires_at or datetime.utcnow()
        if action == 'add':
            target.expires_at = base + timedelta(days=days)
        elif action == 'deduct':
            target.expires_at = base - timedelta(days=days)
        db.session.commit()
        flash('已更新會員天數','success')
    return redirect(url_for('external.company_dashboard'))

@external_bp.route('/logout')
def external_logout():
    session.pop('ext_user_id', None)
    flash('已登出','info')
    return redirect(url_for('external.external_login'))

# ===== Legacy redirects to keep old /MT_System URLs working =====
@external_bp.route('/MT_System/')
def legacy_root():
    return redirect(url_for('external.external_home'))

@external_bp.route('/MT_System/login')
def legacy_login():
    return redirect(url_for('external.external_login'))

@external_bp.route('/MT_System/register')
def legacy_register():
    return redirect(url_for('external.external_register'))

@external_bp.route('/MT_System/features')
def legacy_features():
    return redirect(url_for('external.features'))

@external_bp.route('/MT_System/admin')
def legacy_admin():
    return redirect(url_for('external.admin_dashboard'))

@external_bp.route('/MT_System/company')
def legacy_company():
    return redirect(url_for('external.company_dashboard'))

@external_bp.route('/MT_System/admin/embed')
def legacy_embed():
    return redirect(url_for('external.admin_embed'))

@external_bp.route('/seed')
def external_seed():
    """一次性種子：需提供 ?token= 與環境變數 SEED_TOKEN 相同，建立外部使用者與預設功能旗標。
    安全建議：完成後請移除 SEED_TOKEN 或停用此路由。
    """
    import os
    token = (request.args.get('token') or '').strip()
    expected = os.getenv('SEED_TOKEN', '')
    if not expected or token != expected:
        flash('未授權','danger')
        return redirect(url_for('external.external_login'))
    # 建立外部使用者（若不存在）
    admin_email = os.getenv('SEED_ADMIN_EMAIL', 'admin@example.com')
    admin_pass = os.getenv('SEED_ADMIN_PASSWORD', 'change-me')
    user = ExternalUser.query.filter_by(email=admin_email).first()
    if not user:
        user = ExternalUser()
        user.email = admin_email
        user.password_hash = generate_password_hash(admin_pass)
        user.is_active = True
        db.session.add(user)
    # 預置功能旗標
    defaults = [
        ('verify_flow', '驗證流程', '外部可使用基本驗證功能'),
        ('wallet_reporting', '錢包報表', '查詢報表與摘要'),
        ('csv_export', '匯出功能', 'CSV/JSON 匯出'),
        ('line_tools', 'LINE 工具', 'LINE 相關工具'),
    ]
    for key, name, desc in defaults:
        ff = FeatureFlag.query.filter_by(key=key).first()
        if not ff:
            ff = FeatureFlag()
            ff.key = key
            ff.name = name
            ff.description = desc
            ff.enabled = False
            db.session.add(ff)
    db.session.commit()
    flash('種子資料已建立','success')
    return redirect(url_for('external.external_login'))
