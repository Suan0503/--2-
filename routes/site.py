import os
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename
from extensions import db
from models import SiteUser, ScheduleEntry, Post, MediaAsset

site_bp = Blueprint('site', __name__)


# ===== Helper: simple auth via session =====
def current_user():
    uid = session.get('uid')
    if not uid:
        return None
    return SiteUser.query.filter_by(id=uid).first()


def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def _wrap(*a, **kw):
        if not current_user():
            flash('請先登入','warning')
            return redirect(url_for('site.login', next=request.path))
        return fn(*a, **kw)
    return _wrap


@site_bp.route('/')
def site_index():
    posts = Post.query.filter_by(is_published=True).order_by(Post.created_at.desc()).limit(12).all()
    # 近期班表：未來 2 天
    now = datetime.utcnow()
    schedules = (ScheduleEntry.query
                 .filter(ScheduleEntry.start_time >= now, ScheduleEntry.visible == True)
                 .order_by(ScheduleEntry.start_time.asc())
                 .limit(50).all())
    return render_template('site/index.html', posts=posts, schedules=schedules)


# ===== Auth =====
@site_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('site/register.html')
    # POST
    email = (request.form.get('email') or '').strip().lower()
    name = (request.form.get('name') or '').strip()
    password = request.form.get('password') or ''
    if not email or not password:
        flash('請輸入 Email 與密碼','warning')
        return redirect(url_for('site.register'))
    if SiteUser.query.filter_by(email=email).first():
        flash('Email 已被使用','warning')
        return redirect(url_for('site.register'))
    u = SiteUser()
    u.email = email
    u.name = name
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    flash('註冊成功，請登入','success')
    return redirect(url_for('site.login'))


@site_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        u = SiteUser.query.filter_by(email=email).first()
        if not u or not u.check_password(password):
            flash('帳號或密碼錯誤','danger')
            return redirect(url_for('site.login'))
        session['uid'] = u.id
        flash('登入成功','success')
        next_url = request.args.get('next') or url_for('site.dashboard')
        return redirect(next_url)
    return render_template('site/login.html')


@site_bp.route('/logout')
def logout():
    session.pop('uid', None)
    flash('已登出','info')
    return redirect(url_for('site.login'))


# ===== Dashboard（熱更新：在網站操作即時變更 DB） =====
@site_bp.route('/dashboard')
@login_required
def dashboard():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    schedules = ScheduleEntry.query.order_by(ScheduleEntry.start_time.desc()).limit(100).all()
    assets = MediaAsset.query.order_by(MediaAsset.created_at.desc()).limit(100).all()
    return render_template('site/dashboard.html', posts=posts, schedules=schedules, assets=assets, user=current_user())


# ===== Posts CRUD =====
@site_bp.route('/posts/new', methods=['GET','POST'])
@login_required
def post_new():
    if request.method == 'GET':
        return render_template('site/post_form.html', post=None)
    # POST
    title = (request.form.get('title') or '').strip()
    body = request.form.get('body') or ''
    price = int(request.form.get('price') or 0)
    _cu = current_user()
    p = Post()
    p.title = title
    p.body = body
    p.price = price
    p.created_by = _cu.id if _cu else None
    db.session.add(p)
    db.session.commit()
    flash('已建立貼文','success')
    return redirect(url_for('site.dashboard'))


@site_bp.route('/posts/<int:pid>/edit', methods=['GET','POST'])
@login_required
def post_edit(pid):
    p = Post.query.filter_by(id=pid).first_or_404()
    if request.method == 'POST':
        p.title = (request.form.get('title') or '').strip()
        p.body = request.form.get('body') or ''
        p.price = int(request.form.get('price') or 0)
        p.is_published = (request.form.get('is_published') == 'on')
        db.session.commit()
        flash('已更新','success')
        return redirect(url_for('site.dashboard'))
    return render_template('site/post_form.html', post=p)


@site_bp.route('/posts/<int:pid>/delete', methods=['POST'])
@login_required
def post_delete(pid):
    p = Post.query.filter_by(id=pid).first_or_404()
    db.session.delete(p)
    db.session.commit()
    flash('已刪除','info')
    return redirect(url_for('site.dashboard'))


# ===== Schedule CRUD =====
@site_bp.route('/schedule/new', methods=['POST'])
@login_required
def schedule_new():
    name = (request.form.get('name') or '').strip()
    nation = (request.form.get('nation') or '').strip()
    room = (request.form.get('room') or '').strip()
    start = (request.form.get('start') or '').strip()
    duration = int(request.form.get('duration') or 0)
    languages = ','.join([v for v in (request.form.getlist('lang') or []) if v])
    price = int(request.form.get('price') or 0)
    if not name or not start or duration <= 0:
        flash('資料不完整','warning')
        return redirect(url_for('site.dashboard'))
    try:
        start_dt = datetime.fromisoformat(start)
    except Exception:
        flash('開始時間格式錯誤，請用 YYYY-MM-DD HH:MM','danger')
        return redirect(url_for('site.dashboard'))
    _cu = current_user()
    s = ScheduleEntry()
    s.girl_name = name
    s.nation = nation
    s.room = room
    s.start_time = start_dt
    s.duration_min = duration
    s.languages = languages
    s.price = price
    s.created_by = _cu.id if _cu else None
    db.session.add(s)
    db.session.commit()
    flash('已新增班表','success')
    return redirect(url_for('site.dashboard'))


@site_bp.route('/schedule/<int:sid>/toggle', methods=['POST'])
@login_required
def schedule_toggle(sid):
    s = ScheduleEntry.query.filter_by(id=sid).first_or_404()
    s.visible = not s.visible
    db.session.commit()
    return redirect(url_for('site.dashboard'))


@site_bp.route('/schedule/<int:sid>/delete', methods=['POST'])
@login_required
def schedule_delete(sid):
    s = ScheduleEntry.query.filter_by(id=sid).first_or_404()
    db.session.delete(s)
    db.session.commit()
    return redirect(url_for('site.dashboard'))


# ===== Uploads =====
def _upload_to_local(file_storage):
    upload_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads')
    upload_dir = os.path.abspath(upload_dir)
    os.makedirs(upload_dir, exist_ok=True)
    fname = secure_filename(file_storage.filename or f"upload-{uuid.uuid4().hex}")
    path = os.path.join(upload_dir, fname)
    file_storage.save(path)
    url = f"/static/uploads/{fname}"
    return url, fname, None


def _upload_to_s3(file_storage):
    # 動態匯入以避免在未安裝 boto3 的環境觸發靜態檢查錯誤
    boto3 = __import__('boto3')
    bucket = os.getenv('S3_BUCKET')
    region = os.getenv('S3_REGION')
    key_prefix = os.getenv('S3_KEY_PREFIX', 'uploads/')
    if not bucket or not region:
        raise RuntimeError('S3 參數未設定')
    s3 = boto3.client('s3', region_name=region,
                      aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
    fname = secure_filename(file_storage.filename or f"upload-{uuid.uuid4().hex}")
    key = f"{key_prefix}{uuid.uuid4().hex}-{fname}"
    s3.upload_fileobj(file_storage.stream, bucket, key, ExtraArgs={'ContentType': file_storage.mimetype or 'application/octet-stream', 'ACL': 'public-read'})
    url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    return url, key, fname


@site_bp.route('/upload', methods=['POST'])
@login_required
def upload():
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'no file'}), 400
    use_s3 = os.getenv('USE_S3', '0') == '1'
    try:
        if use_s3:
            url, key, fname = _upload_to_s3(f)
        else:
            url, fname, key = _upload_to_local(f)
        m = MediaAsset()
        m.url = url
        m.key = key
        m.filename = fname
        m.content_type = f.mimetype
        m.size = request.content_length or 0
        db.session.add(m)
        db.session.commit()
        return jsonify({'url': url, 'id': m.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@site_bp.route('/media/<int:mid>/delete', methods=['POST'])
@login_required
def media_delete(mid):
    asset = MediaAsset.query.filter_by(id=mid).first_or_404()
    use_s3 = os.getenv('USE_S3', '0') == '1'
    if use_s3 and asset.key:
        try:
            boto3 = __import__('boto3')
            bucket = os.getenv('S3_BUCKET')
            region = os.getenv('S3_REGION')
            if bucket and region:
                s3 = boto3.client('s3', region_name=region,
                                  aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                                  aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'))
                s3.delete_object(Bucket=bucket, Key=asset.key)
        except Exception:
            pass  # 刪除失敗不阻斷流程
    else:
        # 本地檔案刪除
        try:
            if asset.filename:
                local_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', asset.filename)
                local_path = os.path.abspath(local_path)
                if os.path.isfile(local_path):
                    os.remove(local_path)
        except Exception:
            pass
    db.session.delete(asset)
    db.session.commit()
    flash('圖片已刪除','info')
    return redirect(url_for('site.dashboard'))
