import os
import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import Whitelist, Blacklist, TempVerify, StoredValueWallet, StoredValueTransaction, WageConfig
from utils.db_utils import update_or_create_whitelist_from_data
from hander.verify import EXTRA_NOTICE
from linebot.models import TextSendMessage
from extensions import line_bot_api
from extensions import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from models import ExternalUser, FeatureFlag
from flask import session
from config import LINE_CHANNEL_ACCESS_TOKEN

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# 常數：Dashboard 顯示筆數
DASHBOARD_LIMIT = int(os.getenv('DASHBOARD_LIMIT', '20'))


def load_dashboard_data():
    whitelists = Whitelist.query.order_by(Whitelist.created_at.desc()).limit(DASHBOARD_LIMIT).all()
    blacklists = Blacklist.query.order_by(Blacklist.created_at.desc()).limit(DASHBOARD_LIMIT).all()
    tempverifies = (TempVerify.query
            .filter(TempVerify.status == 'pending',
                TempVerify.phone.isnot(None), TempVerify.phone != '',
                TempVerify.line_id.isnot(None), TempVerify.line_id != '')
            .order_by(TempVerify.created_at.desc())
            .limit(DASHBOARD_LIMIT).all())
    return whitelists, blacklists, tempverifies

def render_dashboard(whitelists=None, blacklists=None, tempverifies=None):
    if whitelists is None:
        whitelists = Whitelist.query.order_by(Whitelist.created_at.desc()).limit(DASHBOARD_LIMIT).all()
    if blacklists is None:
        blacklists = Blacklist.query.order_by(Blacklist.created_at.desc()).limit(DASHBOARD_LIMIT).all()
    if tempverifies is None:
        # 僅顯示「待驗證」且有輸入手機與 LINE ID 的資料
        tempverifies = (TempVerify.query
                        .filter(TempVerify.status == 'pending',
                                TempVerify.phone.isnot(None), TempVerify.phone != '',
                                TempVerify.line_id.isnot(None), TempVerify.line_id != '')
                        .order_by(TempVerify.created_at.desc())
                        .limit(DASHBOARD_LIMIT).all())
    return render_template('admin_dashboard.html', whitelists=whitelists, blacklists=blacklists, tempverifies=tempverifies)

def render_home(whitelists=None, blacklists=None, tempverifies=None, active_tab=None):
    if whitelists is None or blacklists is None or tempverifies is None:
        base_wl, base_bl, base_tv = load_dashboard_data()
        if whitelists is None:
            whitelists = base_wl
        if blacklists is None:
            blacklists = base_bl
        if tempverifies is None:
            tempverifies = base_tv
    return render_template('admin_home.html', whitelists=whitelists, blacklists=blacklists, tempverifies=tempverifies, limit=DASHBOARD_LIMIT, active_tab=active_tab)


@admin_bp.route('/')
def admin_root():
    return redirect(url_for('admin.home'))

@admin_bp.route('/home')
def home():
    whitelists, blacklists, tempverifies = load_dashboard_data()
    active_tab = request.args.get('tab') or request.args.get('active_tab')
    return render_template('admin_home.html', whitelists=whitelists, blacklists=blacklists, tempverifies=tempverifies, limit=DASHBOARD_LIMIT, active_tab=active_tab)


@admin_bp.route('/dashboard')
def admin_dashboard():
    return render_dashboard()


# 白名單
@admin_bp.route('/whitelist/search')
def whitelist_search():
    q = request.args.get('q','').strip()
    view = request.args.get('view')
    if q:
        whitelists = Whitelist.query.filter(
            Whitelist.phone.like(f"%{q}%") |
            Whitelist.name.like(f"%{q}%") |
            Whitelist.line_id.like(f"%{q}%")
        ).order_by(Whitelist.created_at.desc()).limit(DASHBOARD_LIMIT).all()
    else:
        whitelists = None
    if view == 'home':
        return render_home(whitelists=whitelists, active_tab='whitelist')
    return render_dashboard(whitelists=whitelists)
@admin_bp.route('/whitelist/delete', methods=['POST'])
def whitelist_delete():
    phone = request.form.get('phone','').strip()
    w = Whitelist.query.filter_by(phone=phone).first()
    if not w:
        flash('找不到該白名單記錄','danger')
        return redirect(url_for('admin.home', tab='whitelist'))
    db.session.delete(w)
    db.session.commit()
    flash('白名單刪除成功','info')
    return redirect(url_for('admin.home', tab='whitelist'))


# 黑名單
@admin_bp.route('/blacklist/search')
def blacklist_search():
    q = request.args.get('q','').strip()
    view = request.args.get('view')
    if q:
        blacklists = Blacklist.query.filter(
            Blacklist.phone.like(f"%{q}%") |
            Blacklist.name.like(f"%{q}%")
        ).order_by(Blacklist.created_at.desc()).limit(DASHBOARD_LIMIT).all()
    else:
        blacklists = None
    if view == 'home':
        return render_home(blacklists=blacklists, active_tab='blacklist')
    return render_dashboard(blacklists=blacklists)


@admin_bp.route('/blacklist/add', methods=['POST'])
def blacklist_add():
    phone = request.form.get('phone','').strip()
    name = request.form.get('name','').strip()
    reason = request.form.get('reason','').strip()
    if not phone or not name or not reason:
        flash('黑名單新增資料不完整','warning')
        return redirect(url_for('admin.home', tab='blacklist'))
    if Blacklist.query.filter_by(phone=phone).first():
        flash('手機已存在於黑名單','warning')
        return redirect(url_for('admin.home', tab='blacklist'))
    b = Blacklist()
    b.phone = phone
    b.name = name
    b.reason = reason
    db.session.add(b)
    db.session.commit()
    flash('黑名單新增成功','success')
    return redirect(url_for('admin.home', tab='blacklist'))


@admin_bp.route('/blacklist/delete', methods=['POST'])
def blacklist_delete():
    phone = request.form.get('phone','').strip()
    b = Blacklist.query.filter_by(phone=phone).first()
    if not b:
        flash('找不到該黑名單記錄','danger')
        return redirect(url_for('admin.home', tab='blacklist'))
    db.session.delete(b)
    db.session.commit()
    flash('黑名單刪除成功','info')
    return redirect(url_for('admin.home', tab='blacklist'))


# 暫存名單（待驗證）
@admin_bp.route('/tempverify/verify', methods=['POST'])
def tempverify_verify():
    _id = request.form.get('id')
    tv = TempVerify.query.filter_by(id=_id).first()
    if not tv:
        flash('找不到暫存名單','danger')
        return redirect(url_for('admin.admin_dashboard'))
    # 將暫存資料寫入白名單（快速通關）
    try:
        data = {
            'phone': tv.phone,
            'name': tv.nickname,
            'line_id': tv.line_id,
        }
        record, _ = update_or_create_whitelist_from_data(data, user_id=tv.line_user_id, reverify=True)
        db.session.delete(tv)
        db.session.commit()
        flash(f'已通過並寫入白名單：{record.phone}','success')
        if record.line_user_id:
            try:
                msg = (
                    f"📱 {record.phone}\n"
                    f"🌸 暱稱：{record.name or '用戶'}\n"
                    f"🔗 LINE ID：{record.line_id or '未登記'}\n"
                    f"🕒 {record.created_at}\n"
                    f"✅ 驗證成功，歡迎加入茗殿\n"
                    f"🌟 加入密碼：ming666"
                ) + EXTRA_NOTICE
                line_bot_api.push_message(record.line_user_id, TextSendMessage(text=msg))
            except Exception:
                pass
    except Exception as e:
        db.session.rollback()
        flash(f'寫入白名單時發生錯誤：{e}','danger')
    return redirect(url_for('admin.home', tab='pending'))


@admin_bp.route('/tempverify/delete', methods=['POST'])
def tempverify_delete():
    _id = request.form.get('id')
    tv = TempVerify.query.filter_by(id=_id).first()
    if not tv:
        flash('找不到暫存名單','danger')
        return redirect(url_for('admin.admin_dashboard'))
    db.session.delete(tv)
    db.session.commit()
    flash('暫存名單刪除成功','info')
    return redirect(url_for('admin.home', tab='pending'))


@admin_bp.route('/schedule/')
def admin_schedule():
    return render_template('schedule.html')


def fetch_line_richmenus():
    """呼叫 LINE API 取得 Rich Menu 清單，回傳 (list, error_message)。"""
    access_token = LINE_CHANNEL_ACCESS_TOKEN or os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
    if not access_token:
        return [], '尚未設定 LINE_CHANNEL_ACCESS_TOKEN，無法取得 Rich Menu 清單'
    try:
        url = 'https://api.line.me/v2/bot/richmenu/list'
        headers = {
            'Authorization': f'Bearer {access_token}',
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if 200 <= resp.status_code < 300:
            data = resp.json() or {}
            return data.get('richmenus', []) or [], None
        try:
            detail = resp.json().get('message') or resp.text
        except Exception:
            detail = resp.text
        return [], f'LINE API 讀取 Rich Menu 清單失敗（{resp.status_code}）：{detail}'
    except Exception as e:
        return [], f'呼叫 LINE Rich Menu 清單 API 發生錯誤：{e}'


# ========= LINE Rich Menu 圖片更新 =========
@admin_bp.route('/richmenu', methods=['GET', 'POST'])
def admin_richmenu():
    if request.method == 'POST':
        rich_menu_id = (request.form.get('rich_menu_id') or '').strip()
        file = request.files.get('image')

        if not rich_menu_id or not file:
            flash('請輸入 Rich Menu ID 並選擇圖片檔案', 'warning')
            return redirect(url_for('admin.admin_richmenu'))

        if not (file.mimetype or '').startswith('image/'):
            flash('上傳檔案必須為圖片格式', 'danger')
            return redirect(url_for('admin.admin_richmenu'))

        access_token = LINE_CHANNEL_ACCESS_TOKEN or os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
        if not access_token:
            flash('環境尚未設定 LINE_CHANNEL_ACCESS_TOKEN，無法呼叫 LINE API', 'danger')
            return redirect(url_for('admin.admin_richmenu'))

        try:
            image_bytes = file.stream.read()
            # 根據 LINE 官方文件，上傳 Rich Menu 圖片需使用 api-data.line.me 網域
            url = f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content"
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': file.mimetype,
            }
            resp = requests.post(url, data=image_bytes, headers=headers, timeout=15)
            if 200 <= resp.status_code < 300:
                flash('Rich Menu 圖片更新成功', 'success')
            else:
                try:
                    detail = resp.json().get('message') or resp.text
                except Exception:
                    detail = resp.text

                # 特別處理「圖片已存在」的情況，給出更清楚的中文說明
                if 'An image has already been uploaded to the richmenu' in str(detail):
                    human_msg = 'LINE 回覆：這個 Rich Menu 已經有設定圖片，官方規則不允許覆蓋。若要換圖，必須建立新的 Rich Menu 再上傳圖片。'
                else:
                    human_msg = f'LINE API 回應錯誤（{resp.status_code}）：{detail}'

                flash(human_msg, 'danger')
        except Exception as e:
            flash(f'上傳至 LINE 時發生錯誤：{e}', 'danger')

        return redirect(url_for('admin.admin_richmenu'))

    richmenus, richmenus_error = fetch_line_richmenus()
    return render_template('admin_richmenu.html', richmenus=richmenus, richmenus_error=richmenus_error)


# ========= 儲值金專區 =========
@admin_bp.route('/wallet')
def wallet_home():
    q = (request.args.get('q') or '').strip()
    wallet = None
    txns = []
    coupon_500_total = 0
    coupon_300_total = 0
    coupon_100_total = 0
    wl_user = None
    error = None
    if q:
        try:
            # 以手機或用戶編號查找
            wl = None
            if q.isdigit():
                try:
                    wl = Whitelist.query.filter((Whitelist.phone == q) | (Whitelist.id == int(q))).first()
                except Exception:
                    wl = Whitelist.query.filter_by(phone=q).first()
            else:
                wl = Whitelist.query.filter_by(phone=q).first()
            wallet = None
            if wl:
                wallet = StoredValueWallet.query.filter_by(whitelist_id=wl.id).first()
                if not wallet:
                    wallet = StoredValueWallet()
                    wallet.whitelist_id = wl.id
                    wallet.phone = wl.phone
                    wallet.balance = 0
                    db.session.add(wallet)
                    db.session.commit()
            else:
                wallet = StoredValueWallet.query.filter_by(phone=q).first()
                if not wallet and q.isdigit() and len(q) == 10 and q.startswith('09'):
                    wallet = StoredValueWallet()
                    wallet.phone = q
                    wallet.balance = 0
                    db.session.add(wallet)
                    db.session.commit()
            if wallet:
                # 近期交易
                txns = (StoredValueTransaction.query
                        .filter_by(wallet_id=wallet.id)
                        .order_by(StoredValueTransaction.created_at.desc())
                        .limit(100).all())
                # 轉換時間為台北時區字串
                try:
                    import pytz
                    tz = pytz.timezone('Asia/Taipei')
                    utc = pytz.utc
                    for _t in txns:
                        dt = getattr(_t, 'created_at', None)
                        if dt:
                            if dt.tzinfo is None:
                                dt = utc.localize(dt)
                            local_dt = dt.astimezone(tz)
                            _t.local_time_str = local_dt.strftime('%Y/%m/%d %H:%M')
                        else:
                            _t.local_time_str = ''
                except Exception:
                    for _t in txns:
                        _t.local_time_str = _t.created_at.strftime('%Y/%m/%d %H:%M') if _t.created_at else ''
                # 調整備註：topup 金額=0 且有任一折價券 → 使用折價券
                for _t in txns:
                    try:
                        if (_t.type == 'topup' and (_t.amount or 0) == 0 and ((getattr(_t,'coupon_500_count',0) or 0) or (getattr(_t,'coupon_300_count',0) or 0) or (getattr(_t,'coupon_100_count',0) or 0))):
                            _t.adjusted_remark = '使用折價券'
                        else:
                            _t.adjusted_remark = _t.remark
                    except Exception:
                        _t.adjusted_remark = _t.remark
                # 折價券總數（全量計算避免被limit影響）
                all_txns = StoredValueTransaction.query.filter_by(wallet_id=wallet.id).all()
                c500 = c300 = c100 = 0
                for t in all_txns:
                    sign = 1 if t.type == 'topup' else -1
                    c500 += sign * (t.coupon_500_count or 0)
                    c300 += sign * (t.coupon_300_count or 0)
                    # 可能舊資料無欄位
                    try:
                        c100 += sign * (getattr(t, 'coupon_100_count', 0) or 0)
                    except Exception:
                        pass
                coupon_500_total = max(c500, 0)
                coupon_300_total = max(c300, 0)
                coupon_100_total = max(c100, 0)
                # 用戶資訊（暱稱、LINE ID）
                try:
                    if wallet.whitelist_id:
                        wl_user = Whitelist.query.filter_by(id=wallet.whitelist_id).first()
                    elif wallet.phone:
                        wl_user = Whitelist.query.filter_by(phone=wallet.phone).first()
                except Exception:
                    wl_user = None
        except Exception as e:
            db.session.rollback()
            error = f"資料讀取錯誤，可能尚未執行遷移：{e}"
    return render_template('wallet.html', q=q, wallet=wallet, txns=txns, error=error,
                           coupon_500_total=coupon_500_total, coupon_300_total=coupon_300_total,
                           coupon_100_total=coupon_100_total, wl_user=wl_user)

@admin_bp.route('/wallet/summary')
def wallet_summary():
    """列出所有已有錢包的用戶：手機號碼 / 暱稱 / 編號 / 累計儲值金額 / 目前餘額 / 折價券(500/300/100)。支援手機搜尋。"""
    q = (request.args.get('q') or '').strip()
    base_query = StoredValueWallet.query
    if q:
        base_query = base_query.filter(StoredValueWallet.phone.like(f"%{q}%"))
    wallets = base_query.order_by(StoredValueWallet.created_at.asc()).all()
    rows = []
    import pytz
    tz = pytz.timezone('Asia/Taipei')
    for w in wallets:
        # 計算折價券總數
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
        c500 = max(c500, 0)
        c300 = max(c300, 0)
        c100 = max(c100, 0)
        # 若餘額與所有折價券皆為 0，從總表隱藏
        if (w.balance or 0) == 0 and c500 == 0 and c300 == 0 and c100 == 0:
            continue
        wl = None
        if w.whitelist_id:
            wl = Whitelist.query.filter_by(id=w.whitelist_id).first()
        # 累計儲值：所有 topup 交易金額相加
        topups = StoredValueTransaction.query.filter_by(wallet_id=w.id, type='topup').all()
        total_topup = sum(t.amount for t in topups if t.amount)
        rows.append({
            'phone': w.phone,
            'nickname': (wl.name if wl and wl.name else '—'),
            'code': (wl.id if wl else '—'),
            'total_topup': total_topup,
            'balance': w.balance,
            'c500': c500,
            'c300': c300,
            'c100': c100,
            'created_at': w.created_at.astimezone(tz).strftime('%Y/%m/%d %H:%M') if w.created_at else ''
        })
    return render_template('wallet_summary.html', rows=rows, count=len(rows), q=q)

# ========= 儲值對帳（今日與區間） =========
@admin_bp.route('/wallet/reconcile')
def wallet_reconcile():
    """對帳報表：顯示本日時段（12:00~次日03:00）儲值總額，並提供自訂日期區間查詢與明細、彙總、現金應收。"""
    import pytz
    from datetime import datetime as _dt, timedelta
    import re
    tz = pytz.timezone('Asia/Taipei')

    # 取得查詢參數
    preset = (request.args.get('preset') or '').strip()  # today, yesterday, thisweek, thismonth, lastmonth
    start_str = (request.args.get('start') or '').strip()
    end_str = (request.args.get('end') or '').strip()
    export = (request.args.get('export') or '').strip()  # csv
    cash_kw = (request.args.get('cash_kw') or 'TOPUP_CASH,現金').strip()
    remark_kw = (request.args.get('remark_kw') or '').strip()  # 額外備註篩選
    payment_method_filter = (request.args.get('payment_method') or '').strip()
    reference_kw = (request.args.get('reference_kw') or '').strip()
    cash_keywords = [k.strip() for k in cash_kw.split(',') if k.strip()]

    now_local = _dt.now(tz)

    def business_day_window(base_date):
        """回傳某個基準日期的會計日區間：當日 12:00 ~ 次日 03:00（半開區間）。"""
        start_local = tz.localize(_dt(base_date.year, base_date.month, base_date.day, 12, 0, 0))
        # 次日 03:00
        next_day = start_local + timedelta(days=1)
        end_local = tz.localize(_dt(next_day.year, next_day.month, next_day.day, 3, 0, 0))
        return start_local, end_local

    # 依現在時間決定「今日」基準（淩晨 00:00~03:00 視為前一會計日）
    def current_business_base_date(now_dt):
        if now_dt.hour < 3:  # 00:00~02:59 -> 前一日
            return (now_dt - timedelta(days=1)).date()
        return now_dt.date()

    # 計算查詢區間
    if preset in ('today', 'yesterday') and not start_str and not end_str:
        base_date = current_business_base_date(now_local)
        if preset == 'yesterday':
            base_date = base_date - timedelta(days=1)
        start_local, end_local = business_day_window(base_date)
    elif preset == 'thisweek' and not start_str and not end_str:
        # 本週（以週一為基準），使用會計日窗拼接至今
        weekday = current_business_base_date(now_local).weekday()  # Monday=0
        monday_date = current_business_base_date(now_local) - timedelta(days=weekday)
        start_local, _ = business_day_window(monday_date)
        _, end_local = business_day_window(current_business_base_date(now_local))
    elif preset == 'thismonth' and not start_str and not end_str:
        first_date = current_business_base_date(now_local).replace(day=1)
        start_local, _ = business_day_window(first_date)
        # 到當前會計日的結束
        _, end_local = business_day_window(current_business_base_date(now_local))
    elif preset == 'lastmonth' and not start_str and not end_str:
        # 上個月：從上個月1日到上個月最後一天（以會計日窗包住）
        base = current_business_base_date(now_local)
        first_this = base.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        first_last = last_month_end.replace(day=1)
        start_local, _ = business_day_window(first_last)
        _, end_local = business_day_window(last_month_end)
    else:
        # 自訂日期以會計日窗解讀：起日的 12:00 到 迄日次日 03:00
        if start_str:
            try:
                y, m, d = [int(x) for x in start_str.split('-')]
                start_local, _ = business_day_window(_dt(y, m, d).date())
            except Exception:
                start_local, _ = business_day_window(now_local.date())
        else:
            start_local, _ = business_day_window(now_local.date())
        if end_str:
            try:
                y2, m2, d2 = [int(x) for x in end_str.split('-')]
                _, end_local = business_day_window(_dt(y2, m2, d2).date())
            except Exception:
                _, end_local = business_day_window(now_local.date())
        else:
            _, end_local = business_day_window(now_local.date())

    # 轉為 UTC 過濾
    start_utc = start_local.astimezone(pytz.utc)
    end_utc = end_local.astimezone(pytz.utc)

    # 查詢 topup 交易
    q = (StoredValueTransaction.query
         .filter(StoredValueTransaction.type == 'topup')
         .filter(StoredValueTransaction.created_at >= start_utc)
         .filter(StoredValueTransaction.created_at < end_utc)
         .order_by(StoredValueTransaction.created_at.asc()))
    if payment_method_filter:
        q = q.filter(StoredValueTransaction.payment_method == payment_method_filter)
    txns = q.all()

    # 明細與總計（儲值）
    total_amount = sum(t.amount or 0 for t in txns)
    count = len(txns)
    avg_amount = (total_amount // count) if count else 0
    # 顯示沖正：僅影響頁面展示，不改動資料庫
    display_offset = int(request.args.get('offset') or 0)
    adj_total_amount = total_amount + display_offset
    adj_avg_amount = (adj_total_amount // count) if count else 0

    # 同時期間的支出（consume）統計
    consume_q = (StoredValueTransaction.query
                 .filter(StoredValueTransaction.type == 'consume')
                 .filter(StoredValueTransaction.created_at >= start_utc)
                 .filter(StoredValueTransaction.created_at < end_utc))
    consume_txns = consume_q.all()
    consume_total = sum(t.amount or 0 for t in consume_txns)
    consume_count = len(consume_txns)

    # 顯示剩餘金額（顯示總額 - 本期間支出）
    adj_remaining = adj_total_amount - consume_total

    # 取得電話/姓名/代號與本地時間字串（多重回填）
    rows = []
    phone_pattern = re.compile(r'(09\d{8})')
    for t in txns:
        wallet = StoredValueWallet.query.filter_by(id=t.wallet_id).first() if t.wallet_id else None
        phone = None
        nickname = '—'
        code = '—'
        wl = None
        if wallet:
            phone = wallet.phone or None
            if wallet.whitelist_id:
                wl = Whitelist.query.filter_by(id=wallet.whitelist_id).first()
                if wl:
                    nickname = wl.name or nickname
                    code = wl.id
                    # 若 wallet.phone 缺失，嘗試用 whitelist.phone 回填顯示
                    if not phone:
                        phone = getattr(wl, 'phone', None) or phone
        # 若仍無 phone，嘗試從備註解析
        remark_text = (t.remark or '')
        if not phone:
            m = phone_pattern.search(remark_text)
            if m:
                phone = m.group(1)
        # 顯示字串
        phone_display = phone if phone else '—'

        # 本地時間字串
        try:
            import pytz as _p
            utc = _p.utc
            dt = t.created_at
            if dt and dt.tzinfo is None:
                dt = utc.localize(dt)
            local_dt = dt.astimezone(tz) if dt else None
            time_str = local_dt.strftime('%Y/%m/%d %H:%M') if local_dt else ''
        except Exception:
            time_str = t.created_at.strftime('%Y/%m/%d %H:%M') if t.created_at else ''

        # 判斷是否屬於券使用（amount=0 且有任一 coupon 欄位）
        coupon_only = False
        if (t.type == 'topup' and (t.amount or 0) == 0 and (
            getattr(t, 'coupon_500_count', 0) or getattr(t, 'coupon_300_count', 0) or getattr(t, 'coupon_100_count', 0)
        )):
            coupon_only = True
        remark_show = '使用折價券' if coupon_only else remark_text[:120]
        rows.append({
            'id': t.id,
            'time': time_str,
            'phone': phone_display,
            'nickname': nickname,
            'code': code,
            'amount': t.amount or 0,
            'remark': remark_show,
            'coupon_only': coupon_only,
            'payment_method': getattr(t,'payment_method',None),
            'reference_id': getattr(t,'reference_id',None),
            'operator': getattr(t,'operator',None),
        })

    # 備註過濾（若指定 remark_kw）
    if reference_kw:
        rows = [r for r in rows if reference_kw in (r.get('reference_id') or '')]
    if remark_kw:
        rows = [r for r in rows if (remark_kw in (r['remark'] or '') or remark_kw in (r.get('reference_id') or '') or remark_kw in (r.get('payment_method') or ''))]

    # 依 remark 分組
    by_remark = {}
    for r in rows:
        k = r['remark'] or '—'
        by_remark.setdefault(k, {'amount': 0, 'count': 0})
        by_remark[k]['amount'] += r['amount']
        by_remark[k]['count'] += 1

    # 依會計日（日）彙總：以 12:00~次日03:00 分群
    by_day = {}
    for t in txns:
        dt = t.created_at
        if dt and dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        local_dt = dt.astimezone(tz) if dt else None
        if local_dt is None:
            day_key = '—'
        else:
            # 將 00:00~02:59 歸屬前一日
            bd_date = (local_dt - timedelta(days=1)).date() if local_dt.hour < 3 else local_dt.date()
            day_key = bd_date.strftime('%Y-%m-%d')
        by_day.setdefault(day_key, 0)
        by_day[day_key] += (t.amount or 0)

    # 現金應收：以關鍵字（remark 含任一關鍵字）快速計算
    def is_cash_remark(text):
        if not cash_keywords:
            return False
        lower = text.lower() if text else ''
        for kw in cash_keywords:
            if kw and (kw in text or kw.lower() in lower):
                return True
        return False
    cash_total = sum(r['amount'] for r in rows if is_cash_remark(r['remark']))
    cash_count = sum(1 for r in rows if is_cash_remark(r['remark']))

    # ====== 無效紀錄與重複紀錄偵測 ======
    invalid_rows = []
    for r in rows:
        # 無電話且有金額且備註包含儲值關鍵字或 TOPUP_CASH -> 嘗試修復
        if (r['phone'] == '—' and r['amount'] > 0 and (
            'TOPUP_CASH' in (r['remark'] or '') or '儲值' in (r['remark'] or '')
        )):
            # 嘗試由交易紀錄重新抓 wallet 並補 phone
            tfix = StoredValueTransaction.query.filter_by(id=r['id']).first()
            if tfix:
                wfix = StoredValueWallet.query.filter_by(id=tfix.wallet_id).first()
                repaired = False
                if wfix and wfix.phone:
                    r['phone'] = wfix.phone
                    repaired = True
                else:
                    # 從 remark 解析手機
                    import re as _re
                    m2 = _re.search(r'(09\d{8})', tfix.remark or '')
                    if m2:
                        if wfix and not wfix.phone:
                            wfix.phone = m2.group(1)
                            wfix.updated_at = datetime.utcnow()
                            db.session.commit()
                        r['phone'] = m2.group(1)
                        repaired = True
                if not repaired:
                    invalid_rows.append(r)
            else:
                # 交易不存在 -> 不呈現（幽靈 ID），跳過
                continue

    # 重複判斷：相同 phone != '—'、amount、remark（移除時以最晚時間保留一筆）
    dup_groups = {}
    for r in rows:
        if r['phone'] == '—':
            continue
        key = (r['phone'], r['amount'], r['remark'])
        dup_groups.setdefault(key, []).append(r)
    duplicate_rows = []
    for key, group in dup_groups.items():
        if len(group) > 1:
            # 依時間排序保留第一筆，其餘視為重複
            # 時間字串格式 '%Y/%m/%d %H:%M'
            try:
                group_sorted = sorted(group, key=lambda x: x['time'])
            except Exception:
                group_sorted = group
            # 保留第一筆，其餘列出
            for rr in group_sorted[1:]:
                duplicate_rows.append(rr)

    # 自動清理無效紀錄（選項）
    clean_invalid = request.args.get('clean_invalid') == '1'
    if clean_invalid and invalid_rows:
        removed_ids = []
        for r in invalid_rows:
            tdel = StoredValueTransaction.query.filter_by(id=r['id']).first()
            if tdel:
                # 還原餘額（topup 則扣回）避免影響餘額
                if tdel.type == 'topup' and tdel.amount:
                    wallet = StoredValueWallet.query.filter_by(id=tdel.wallet_id).first()
                    if wallet:
                        wallet.balance -= tdel.amount
                        wallet.updated_at = datetime.utcnow()
                db.session.delete(tdel)
                removed_ids.append(r['id'])
        db.session.commit()
        flash(f'已自動清理 {len(removed_ids)} 筆無效交易','info')
        # 重新導向以刷新
        return redirect(url_for('admin.wallet_reconcile'))

    # CSV 匯出
    if export == 'csv':
        import csv
        from io import StringIO
        si = StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', '時間(台北)', '手機', '名稱', '編號', '金額', '備註'])
        for r in rows:
            cw.writerow([r['id'], r['time'], r['phone'], r['nickname'], r['code'], r['amount'], r['remark']])
        output = si.getvalue()
        from flask import Response
        filename = f"wallet_topups_{start_local.strftime('%Y%m%d_%H%M')}_{end_local.strftime('%Y%m%d_%H%M')}.csv"
        return Response(output, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="{filename}"'})

    # 本日時段總額（以會計日理解）
    base_today = current_business_base_date(now_local)
    today_start_local, today_end_local = business_day_window(base_today)
    today_q = (StoredValueTransaction.query
               .filter(StoredValueTransaction.type == 'topup')
               .filter(StoredValueTransaction.created_at >= today_start_local.astimezone(pytz.utc))
               .filter(StoredValueTransaction.created_at < today_end_local.astimezone(pytz.utc)))
    today_total = sum(t.amount or 0 for t in today_q.all())

    # Debug 資訊：DB URL、交易數量、最大 ID
    from config import DATABASE_URL as _DB_URL
    txn_count = StoredValueTransaction.query.count()
    last_txn = StoredValueTransaction.query.order_by(StoredValueTransaction.id.desc()).first()
    last_txn_id = last_txn.id if last_txn else None

    return render_template('wallet_reconcile.html',
                           rows=rows,
                           total_amount=total_amount,
                           adj_total_amount=adj_total_amount,
                           count=count,
                           avg_amount=avg_amount,
                           adj_avg_amount=adj_avg_amount,
                           adj_remaining=adj_remaining,
                           by_remark=by_remark,
                           by_day=by_day,
                           preset=preset,
                           start=start_str,
                           end=end_str,
                           cash_kw=cash_kw,
                           remark_kw=remark_kw,
                           payment_method_filter=payment_method_filter,
                           reference_kw=reference_kw,
                           cash_total=cash_total,
                           cash_count=cash_count,
                           consume_total=consume_total,
                           consume_count=consume_count,
                           invalid_rows=invalid_rows,
                           duplicate_rows=duplicate_rows,
                           today_total=today_total,
                           start_local_display=(start_local.strftime('%Y-%m-%d %H:%M')),
                           end_local_display=(end_local.strftime('%Y-%m-%d %H:%M')),
                           db_url=_DB_URL,
                           txn_count=txn_count,
                           last_txn_id=last_txn_id)

@admin_bp.route('/wallet/reconcile/consume')
def wallet_reconcile_consume():
    """扣款對帳：顯示 consume 交易，區分使用儲值金與使用折價券（僅券），同會計時段與篩選。"""
    import pytz
    from datetime import datetime as _dt, timedelta
    tz = pytz.timezone('Asia/Taipei')
    preset = (request.args.get('preset') or '').strip()  # today,yesterday,thisweek,thismonth,lastmonth
    start_str = (request.args.get('start') or '').strip()
    end_str = (request.args.get('end') or '').strip()
    remark_kw = (request.args.get('remark_kw') or '').strip()
    only = (request.args.get('only') or '').strip()  # 'stored' or 'coupon'

    now_local = _dt.now(tz)
    def business_day_window(base_date):
        start_local = tz.localize(_dt(base_date.year, base_date.month, base_date.day, 12, 0, 0))
        next_day = start_local + timedelta(days=1)
        end_local = tz.localize(_dt(next_day.year, next_day.month, next_day.day, 3, 0, 0))
        return start_local, end_local
    def current_business_base_date(now_dt):
        if now_dt.hour < 3:
            return (now_dt - timedelta(days=1)).date()
        return now_dt.date()
    if preset in ('today','yesterday') and not start_str and not end_str:
        base_date = current_business_base_date(now_local)
        if preset=='yesterday':
            base_date = base_date - timedelta(days=1)
        start_local, end_local = business_day_window(base_date)
    elif preset=='thisweek' and not start_str and not end_str:
        weekday = current_business_base_date(now_local).weekday()
        monday_date = current_business_base_date(now_local) - timedelta(days=weekday)
        start_local,_ = business_day_window(monday_date)
        _,end_local = business_day_window(current_business_base_date(now_local))
    elif preset=='thismonth' and not start_str and not end_str:
        first_date = current_business_base_date(now_local).replace(day=1)
        start_local,_ = business_day_window(first_date)
        _,end_local = business_day_window(current_business_base_date(now_local))
    elif preset=='lastmonth' and not start_str and not end_str:
        base = current_business_base_date(now_local)
        first_this = base.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        first_last = last_month_end.replace(day=1)
        start_local,_ = business_day_window(first_last)
        _,end_local = business_day_window(last_month_end)
    else:
        if start_str:
            try:
                y,m,d = [int(x) for x in start_str.split('-')]
                start_local,_ = business_day_window(_dt(y,m,d).date())
            except Exception:
                start_local,_ = business_day_window(now_local.date())
        else:
            start_local,_ = business_day_window(now_local.date())
        if end_str:
            try:
                y2,m2,d2 = [int(x) for x in end_str.split('-')]
                _,end_local = business_day_window(_dt(y2,m2,d2).date())
            except Exception:
                _,end_local = business_day_window(now_local.date())
        else:
            _,end_local = business_day_window(now_local.date())
    start_utc = start_local.astimezone(pytz.utc)
    end_utc = end_local.astimezone(pytz.utc)
    txns = (StoredValueTransaction.query
            .filter(StoredValueTransaction.type=='consume')
            .filter(StoredValueTransaction.created_at>=start_utc)
            .filter(StoredValueTransaction.created_at<end_utc)
            .order_by(StoredValueTransaction.created_at.asc()).all())
    rows = []
    stored_sum = 0
    coupon_only_sum = 0
    coupon_value_total = 0
    import re
    phone_pattern = re.compile(r'(09\d{8})')
    for t in txns:
        wallet = StoredValueWallet.query.filter_by(id=t.wallet_id).first() if t.wallet_id else None
        phone = wallet.phone if wallet and wallet.phone else None
        wl = None
        nickname = '—'
        code = '—'
        if wallet and wallet.whitelist_id:
            wl = Whitelist.query.filter_by(id=wallet.whitelist_id).first()
            if wl:
                nickname = wl.name or nickname
                code = wl.id
                if not phone:
                    phone = getattr(wl,'phone',None) or phone
        if not phone and t.remark:
            m = phone_pattern.search(t.remark)
            if m:
                phone = m.group(1)
        phone_display = phone if phone else '—'
        # 判斷使用儲值金或使用折價券
        c500 = (getattr(t,'coupon_500_count',0) or 0)
        c300 = (getattr(t,'coupon_300_count',0) or 0)
        c100 = (getattr(t,'coupon_100_count',0) or 0)
        coupon_used = c500 + c300 + c100
        is_coupon_only = (t.amount or 0) == 0 and coupon_used > 0
        # 篩選：只看使用儲值 or 只看折價券
        if only == 'stored' and is_coupon_only:
            continue
        if only == 'coupon' and not is_coupon_only:
            continue
        if is_coupon_only:
            coupon_only_sum += coupon_used  # 以券張數合計
        else:
            stored_sum += (t.amount or 0)
        # 折價券金額（含非純券也計算券值）
        coupon_value_total += c500*500 + c300*300 + c100*100
        # 顯示 remark
        remark_show = '使用折價券' if is_coupon_only else (t.remark or '')
        # 本地時間
        try:
            import pytz as _p
            dt = t.created_at
            if dt and dt.tzinfo is None:
                dt = _p.utc.localize(dt)
            local_dt = dt.astimezone(tz) if dt else None
            time_str = local_dt.strftime('%Y/%m/%d %H:%M') if local_dt else ''
        except Exception:
            time_str = t.created_at.strftime('%Y/%m/%d %H:%M') if t.created_at else ''
        rows.append({
            'id': t.id,
            'time': time_str,
            'phone': phone_display,
            'nickname': nickname,
            'code': code,
            'amount': t.amount or 0,
            'remark': remark_show,
            'coupon_only': is_coupon_only,
            'coupon_used': coupon_used,
        })
    if remark_kw:
        rows = [r for r in rows if remark_kw in (r['remark'] or '')]
    stored_count = sum(1 for r in rows if not r['coupon_only'])
    coupon_only_count = sum(1 for r in rows if r['coupon_only'])
    # 顯示沖正（扣款頁）：僅影響顯示，不改資料庫；用於調整顯示的使用儲值金總額
    display_offset = int(request.args.get('offset') or 0)
    adj_stored_sum = stored_sum + display_offset
    from config import DATABASE_URL as _DB_URL
    txn_count = StoredValueTransaction.query.filter_by(type='consume').count()
    last_txn = StoredValueTransaction.query.order_by(StoredValueTransaction.id.desc()).first()
    last_txn_id = last_txn.id if last_txn else None
    return render_template('wallet_reconcile_consume.html',
                           rows=rows,
                           stored_sum=stored_sum,
                           adj_stored_sum=adj_stored_sum,
                           stored_count=stored_count,
                           coupon_only_sum=coupon_only_sum,
                           coupon_only_count=coupon_only_count,
                           coupon_value_total=coupon_value_total,
                           preset=preset,
                           only=only,
                           offset=display_offset,
                           start=start_str,
                           end=end_str,
                           remark_kw=remark_kw,
                           start_local_display=start_local.strftime('%Y-%m-%d %H:%M'),
                           end_local_display=end_local.strftime('%Y-%m-%d %H:%M'),
                           db_url=_DB_URL,
                           txn_count=txn_count,
                           last_txn_id=last_txn_id)

@admin_bp.route('/wallet/txn/<int:tid>')
def wallet_txn_detail(tid):
    """單筆交易檢視，協助比對前端顯示 ID 與資料庫真實內容。"""
    t = StoredValueTransaction.query.filter_by(id=tid).first()
    if not t:
        return {'error': 'not found', 'id': tid}, 404
    w = StoredValueWallet.query.filter_by(id=t.wallet_id).first()
    wl = None
    if w and w.whitelist_id:
        wl = Whitelist.query.filter_by(id=w.whitelist_id).first()
    data = {
        'id': t.id,
        'wallet_id': t.wallet_id,
        'type': t.type,
        'amount': t.amount,
        'remark': t.remark,
        'coupon_500_count': getattr(t,'coupon_500_count',0),
        'coupon_300_count': getattr(t,'coupon_300_count',0),
        'coupon_100_count': getattr(t,'coupon_100_count',0),
        'created_at': t.created_at.isoformat() if t.created_at else None,
        'wallet_phone': w.phone if w else None,
        'whitelist_id': w.whitelist_id if w else None,
        'whitelist_name': wl.name if wl else None,
    }
    return data

@admin_bp.route('/wallet/transactions/export')
def wallet_transactions_export():
    """匯出交易：支援 type(topup/consume/all)、日期區間(會計日 12:00~次日03:00)與格式(csv/json)。"""
    import pytz
    from datetime import datetime as _dt, timedelta
    fmt = (request.args.get('fmt') or 'csv').lower()
    tx_type = (request.args.get('type') or 'all').lower()
    start_str = (request.args.get('start') or '').strip()
    end_str = (request.args.get('end') or '').strip()
    tz = pytz.timezone('Asia/Taipei')

    def business_window(d):
        s = tz.localize(_dt(d.year, d.month, d.day, 12, 0, 0))
        e = s + timedelta(days=1, hours=15)  # +1天+15小時 = 次日03:00
        return s, e
    now_local = _dt.now(tz)
    if start_str:
        try:
            y,m,d = [int(x) for x in start_str.split('-')]
            start_local,_ = business_window(_dt(y,m,d).date())
        except Exception:
            start_local,_ = business_window(now_local.date())
    else:
        start_local,_ = business_window(now_local.date())
    if end_str:
        try:
            y2,m2,d2 = [int(x) for x in end_str.split('-')]
            _,end_local = business_window(_dt(y2,m2,d2).date())
        except Exception:
            _,end_local = business_window(now_local.date())
    else:
        _,end_local = business_window(now_local.date())
    su = start_local.astimezone(pytz.utc)
    eu = end_local.astimezone(pytz.utc)
    base_q = StoredValueTransaction.query.filter(StoredValueTransaction.created_at >= su).filter(StoredValueTransaction.created_at < eu)
    if tx_type in ('topup','consume'):
        base_q = base_q.filter(StoredValueTransaction.type == tx_type)
    txns = base_q.order_by(StoredValueTransaction.id.asc()).all()

    # 組資料列
    rows = []
    for t in txns:
        w = StoredValueWallet.query.filter_by(id=t.wallet_id).first()
        wl = None
        name = None
        phone = None
        if w:
            phone = w.phone
            if w.whitelist_id:
                wl = Whitelist.query.filter_by(id=w.whitelist_id).first()
                if wl:
                    name = wl.name
                    if not phone:
                        phone = wl.phone
        coupon_used = (getattr(t,'coupon_500_count',0) or 0) + (getattr(t,'coupon_300_count',0) or 0) + (getattr(t,'coupon_100_count',0) or 0)
        rows.append({
            'id': t.id,
            'created_at': t.created_at.isoformat() if t.created_at else None,
            'type': t.type,
            'wallet_id': t.wallet_id,
            'phone': phone,
            'name': name,
            'amount': t.amount,
            'remark': t.remark,
            'payment_method': getattr(t, 'payment_method', None),
            'reference_id': getattr(t, 'reference_id', None),
            'operator': getattr(t, 'operator', None),
            'coupon_500_count': getattr(t,'coupon_500_count',0),
            'coupon_300_count': getattr(t,'coupon_300_count',0),
            'coupon_100_count': getattr(t,'coupon_100_count',0),
            'coupon_used_total': coupon_used,
        })
    if fmt == 'json':
        return {'start': start_local.isoformat(), 'end': end_local.isoformat(), 'count': len(rows), 'rows': rows}
    # CSV
    import csv
    from io import StringIO
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['id','time','type','wallet_id','phone','name','amount','remark','payment_method','reference_id','operator','c500','c300','c100','coupon_used_total'])
    for r in rows:
        cw.writerow([r['id'], r['created_at'], r['type'], r['wallet_id'], r['phone'], r['name'], r['amount'], r['remark'], r.get('payment_method') or '', r.get('reference_id') or '', r.get('operator') or '', r['coupon_500_count'], r['coupon_300_count'], r['coupon_100_count'], r['coupon_used_total']])
    out = si.getvalue()
    from flask import Response
    fname = f"transactions_{start_local.strftime('%Y%m%d_%H%M')}_{end_local.strftime('%Y%m%d_%H%M')}_{tx_type}.csv"
    return Response(out, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename="{fname}"'})

@admin_bp.route('/wallet/txn/dump')
def wallet_txn_dump():
    """輸出前 N 筆交易 JSON，用於快速對比 ID。"""
    limit = int(request.args.get('limit') or 100)
    txns = StoredValueTransaction.query.order_by(StoredValueTransaction.id.asc()).limit(limit).all()
    data = []
    for t in txns:
        data.append({
            'id': t.id,
            'type': t.type,
            'amount': t.amount,
            'remark': t.remark,
            'wallet_id': t.wallet_id,
            'created_at': t.created_at.isoformat() if t.created_at else None,
        })
    return {'count': len(data), 'rows': data}


def _get_or_create_wallet_by_phone(phone):
    phone = (phone or '').strip()
    wl = Whitelist.query.filter_by(phone=phone).first()
    wallet = StoredValueWallet.query.filter_by(phone=phone).first()
    if not wallet:
        wallet = StoredValueWallet()
        wallet.phone = phone
        wallet.balance = 0
        wallet.whitelist_id = wl.id if wl else None
        db.session.add(wallet)
        db.session.commit()
    return wallet


@admin_bp.route('/wallet/topup', methods=['POST'])
def wallet_topup():
    phone = (request.form.get('phone') or '').strip()
    amount = int(request.form.get('amount') or 0)
    raw_remark = (request.form.get('remark') or '').strip()
    payment_method = (request.form.get('payment_method') or '').strip() or None
    reference_id = (request.form.get('reference_id') or '').strip() or None
    operator = (request.form.get('operator') or '').strip() or None
    c500 = int(request.form.get('coupon_500_count') or 0)
    c300 = int(request.form.get('coupon_300_count') or 0)
    c100 = int(request.form.get('coupon_100_count') or 0)
    if amount <= 0:
        flash('儲值金額必須大於 0','warning')
        return redirect(url_for('admin.wallet_home', q=phone))
    if not phone:
        flash('缺少有效手機號碼，無法儲值','danger')
        return redirect(url_for('admin.wallet_home'))
    wallet = _get_or_create_wallet_by_phone(phone)
    wallet.balance += amount
    wallet.updated_at = datetime.utcnow()
    txn = StoredValueTransaction()
    txn.wallet_id = wallet.id
    txn.type = 'topup'
    txn.amount = amount
    txn.remark = raw_remark if raw_remark else 'TOPUP_CASH'
    # 精準對帳欄位
    try:
        txn.payment_method = payment_method
    except Exception:
        pass
    try:
        txn.reference_id = reference_id
    except Exception:
        pass
    try:
        txn.operator = operator
    except Exception:
        pass
    txn.coupon_500_count = c500
    txn.coupon_300_count = c300
    try:
        txn.coupon_100_count = c100
    except Exception:
        pass
    db.session.add(txn)
    db.session.commit()
    flash(f'已為 {phone} 儲值 {amount} 元，餘額 {wallet.balance}','success')
    return redirect(url_for('admin.wallet_home', q=phone))


@admin_bp.route('/wallet/consume', methods=['POST'])
def wallet_consume():
    phone = (request.form.get('phone') or '').strip()
    amount = int(request.form.get('amount') or 0)
    raw_remark = (request.form.get('remark') or '').strip()
    c500 = int(request.form.get('coupon_500_count') or 0)
    c300 = int(request.form.get('coupon_300_count') or 0)
    c100 = int(request.form.get('coupon_100_count') or 0)
    wallet = _get_or_create_wallet_by_phone(phone)
    if amount < 0:
        flash('金額不可為負數','warning')
        return redirect(url_for('admin.wallet_home', q=phone))
    if amount > 0 and wallet.balance < amount:
        flash('餘額不足','danger')
        return redirect(url_for('admin.wallet_home', q=phone))
    wallet.balance -= amount
    wallet.updated_at = datetime.utcnow()
    txn = StoredValueTransaction()
    txn.wallet_id = wallet.id
    txn.type = 'consume'
    txn.amount = amount
    txn.remark = raw_remark if raw_remark else 'CONSUME_SERVICE'
    txn.coupon_500_count = c500
    txn.coupon_300_count = c300
    try:
        txn.coupon_100_count = c100
    except Exception:
        pass
    db.session.add(txn)
    db.session.commit()
    flash(f'已為 {phone} 扣款 {amount} 元，餘額 {wallet.balance}','info')
    return redirect(url_for('admin.wallet_home', q=phone))

@admin_bp.route('/wallet/txn/delete', methods=['POST'])
def wallet_txn_delete():
    tid = request.form.get('id')
    q = request.form.get('q') or ''
    redirect_url = (request.form.get('redirect_url') or '').strip()
    if not tid:
        flash('缺少交易 ID','warning')
        return redirect(url_for('admin.wallet_home', q=q))
    t = StoredValueTransaction.query.filter_by(id=tid).first()
    if not t:
        flash('找不到交易紀錄','danger')
        return redirect(url_for('admin.wallet_home', q=q))
    try:
        wallet = StoredValueWallet.query.filter_by(id=t.wallet_id).first()
        # 還原餘額（topup 則扣回，consume 則加回）
        if wallet:
            if t.type == 'topup':
                wallet.balance -= (t.amount or 0)
            elif t.type == 'consume':
                wallet.balance += (t.amount or 0)
            wallet.updated_at = datetime.utcnow()
        db.session.delete(t)
        db.session.commit()
        # 若該錢包已無交易且餘額為 0，刪除錢包紀錄（保持總表乾淨）
        if wallet:
            remain_txn = StoredValueTransaction.query.filter_by(wallet_id=wallet.id).count()
            if remain_txn == 0 and (wallet.balance or 0) == 0:
                db.session.delete(wallet)
                db.session.commit()
        flash('已刪除交易並同步更新餘額','info')
    except Exception as e:
        db.session.rollback()
        flash(f'刪除失敗：{e}','danger')
    if redirect_url:
        return redirect(redirect_url)
    return redirect(url_for('admin.wallet_home', q=q))


@admin_bp.route('/wallet/adjust', methods=['POST'])
def wallet_adjust():
    """手動沖正/調整：建立一筆 type='adjust' 的交易，金額可正可負，並同步調整餘額。
    輸入：phone, amount(+/-), remark, operator
    注意：這是管理用途，請務必保留清楚備註與經手人。
    """
    phone = (request.form.get('phone') or '').strip()
    amount = int(request.form.get('amount') or 0)
    remark = (request.form.get('remark') or '').strip()
    operator = (request.form.get('operator') or '').strip() or None
    if not phone:
        flash('缺少手機號碼','warning')
        return redirect(url_for('admin.wallet_home'))
    if amount == 0:
        flash('調整金額不可為 0','warning')
        return redirect(url_for('admin.wallet_home', q=phone))
    wallet = _get_or_create_wallet_by_phone(phone)
    # 調整餘額（可正可負）
    wallet.balance = (wallet.balance or 0) + amount
    wallet.updated_at = datetime.utcnow()
    t = StoredValueTransaction()
    t.wallet_id = wallet.id
    t.type = 'adjust'
    t.amount = amount
    t.remark = remark if remark else 'MANUAL_ADJUST'
    try:
        t.operator = operator
    except Exception:
        pass
    db.session.add(t)
    db.session.commit()
    flash(f'已調整 {phone} 餘額 {amount} 元，目前餘額 {wallet.balance}','info')
    return redirect(url_for('admin.wallet_home', q=phone))


@admin_bp.route('/wallet/reconcile/adjusted')
def wallet_reconcile_adjusted():
    """隱密沖帳總報表：僅顯示調整後的總額/支出/剩餘，不改動資料庫。
    參數：preset/start/end（同會計窗），total_offset、consume_offset（預設0）。
    顯示：
      - 總額：原始儲值總額 + total_offset
      - 支出：原始支出總額 + consume_offset（未提供則顯示原始）
      - 剩餘：上述兩者相減
    """
    import pytz
    from datetime import datetime as _dt, timedelta
    tz = pytz.timezone('Asia/Taipei')
    preset = (request.args.get('preset') or '').strip()
    start_str = (request.args.get('start') or '').strip()
    end_str = (request.args.get('end') or '').strip()
    total_offset = int(request.args.get('total_offset') or 0)
    consume_offset = int(request.args.get('consume_offset') or 0)

    now_local = _dt.now(tz)
    def business_day_window(base_date):
        start_local = tz.localize(_dt(base_date.year, base_date.month, base_date.day, 12, 0, 0))
        next_day = start_local + timedelta(days=1)
        end_local = tz.localize(_dt(next_day.year, next_day.month, next_day.day, 3, 0, 0))
        return start_local, end_local
    def current_business_base_date(now_dt):
        if now_dt.hour < 3:
            return (now_dt - timedelta(days=1)).date()
        return now_dt.date()
    if preset in ('today','yesterday') and not start_str and not end_str:
        base_date = current_business_base_date(now_local)
        if preset=='yesterday':
            base_date = base_date - timedelta(days=1)
        start_local, end_local = business_day_window(base_date)
    elif preset=='thisweek' and not start_str and not end_str:
        weekday = current_business_base_date(now_local).weekday()
        monday_date = current_business_base_date(now_local) - timedelta(days=weekday)
        start_local,_ = business_day_window(monday_date)
        _,end_local = business_day_window(current_business_base_date(now_local))
    elif preset=='thismonth' and not start_str and not end_str:
        first_date = current_business_base_date(now_local).replace(day=1)
        start_local,_ = business_day_window(first_date)
        _,end_local = business_day_window(current_business_base_date(now_local))
    elif preset=='lastmonth' and not start_str and not end_str:
        first_this = current_business_base_date(now_local).replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        first_last = last_month_end.replace(day=1)
        start_local,_ = business_day_window(first_last)
        _,end_local = business_day_window(last_month_end)
    else:
        if start_str:
            try:
                y,m,d = [int(x) for x in start_str.split('-')]
                start_local,_ = business_day_window(_dt(y,m,d).date())
            except Exception:
                start_local,_ = business_day_window(now_local.date())
        else:
            start_local,_ = business_day_window(now_local.date())
        if end_str:
            try:
                y2,m2,d2 = [int(x) for x in end_str.split('-')]
                _,end_local = business_day_window(_dt(y2,m2,d2).date())
            except Exception:
                _,end_local = business_day_window(now_local.date())
        else:
            _,end_local = business_day_window(now_local.date())

    # 原始金額
    su = start_local.astimezone(pytz.utc)
    eu = end_local.astimezone(pytz.utc)
    topup_total = (db.session.query(db.func.sum(StoredValueTransaction.amount))
                   .filter(StoredValueTransaction.type=='topup')
                   .filter(StoredValueTransaction.created_at>=su)
                   .filter(StoredValueTransaction.created_at<eu)
                   .scalar()) or 0
    consume_total = (db.session.query(db.func.sum(StoredValueTransaction.amount))
                     .filter(StoredValueTransaction.type=='consume')
                     .filter(StoredValueTransaction.created_at>=su)
                     .filter(StoredValueTransaction.created_at<eu)
                     .scalar()) or 0

    adj_total = topup_total + total_offset
    adj_consume = consume_total + consume_offset
    adj_remaining = adj_total - adj_consume

    return render_template('wallet_reconcile_adjusted.html',
                           start_local_display=start_local.strftime('%Y-%m-%d %H:%M'),
                           end_local_display=end_local.strftime('%Y-%m-%d %H:%M'),
                           preset=preset,
                           start=start_str,
                           end=end_str,
                           topup_total=topup_total,
                           consume_total=consume_total,
                           adj_total=adj_total,
                           adj_consume=adj_consume,
                           adj_remaining=adj_remaining,
                           total_offset=total_offset,
                           consume_offset=consume_offset)


# ========= 妹妹薪水對帳工具 =========
@admin_bp.route('/wage/reconcile', methods=['GET', 'POST'])
def wage_reconcile():
    """妹妹薪水對帳工具：使用資料庫中的 WageConfig 設定每位妹妹的 90/60/40 分薪水。"""
    import re as _re

    # 前端表單顯示/回填用變數
    salary_config_text = ''  # 已改由資料庫儲存，僅保留給模板 hidden 欄位，不再解析
    records_text = ''
    include_meal = False
    selected_name = ''
    entries = []
    errors = []
    result = None

    # 給前端「輸出區」使用的簡易公式字串
    summary_revenue_expr = ''  # 例如：2300+3000+...=15700
    summary_salary_expr = ''   # 例如：1300*6=7800（若薪水單價一致）
    summary_meal = None        # 例如：2000
    summary_net_expr = ''      # 例如：15700-9800=5900

    action = request.form.get('action') if request.method == 'POST' else ''

    if request.method == 'POST':
        records_text = (request.form.get('records') or '').strip()
        include_meal = bool(request.form.get('include_meal'))
        selected_name = (request.form.get('selected_name') or '').strip()

        # 刪除已設定的妹妹薪資
        if action.startswith('delete_config:'):
            target_name = action.split(':', 1)[1].strip()
            if target_name:
                try:
                    cfg = WageConfig.query.filter_by(name=target_name).first()
                    if cfg:
                        db.session.delete(cfg)
                        db.session.commit()
                        if selected_name == target_name:
                            selected_name = ''
                except Exception as e:
                    db.session.rollback()
                    errors.append(f"刪除妹妹薪資設定時發生錯誤：{e}")

        # 新增或更新妹妹薪資設定：姓名 + 90/60/40 分金額
        if action == 'add_config':
            new_name = (request.form.get('new_name') or '').strip()
            s90 = (request.form.get('salary_90') or '').strip()
            s60 = (request.form.get('salary_60') or '').strip()
            s40 = (request.form.get('salary_40') or '').strip()
            if not new_name or not (s90 and s60 and s40):
                errors.append("請完整填寫：妹妹名稱與 90/60/40 分薪水金額。")
            else:
                try:
                    v90 = int(s90)
                    v60 = int(s60)
                    v40 = int(s40)
                except ValueError:
                    errors.append("90/60/40 分薪水金額必須為數字。")
                else:
                    try:
                        cfg = WageConfig.query.filter_by(name=new_name).first()
                        if not cfg:
                            cfg = WageConfig(name=new_name)
                            db.session.add(cfg)
                        cfg.wage_90 = v90
                        cfg.wage_60 = v60
                        cfg.wage_40 = v40
                        db.session.commit()
                        # 新增或更新完自動選取該妹妹
                        selected_name = new_name
                    except Exception as e:
                        db.session.rollback()
                        errors.append(f"儲存妹妹薪資設定時發生錯誤：{e}")

    # 無論 GET 或 POST，都從資料庫載入所有妹妹薪資設定
    salary_list = []
    salary_map = {}  # { name: { minutes: salary } }
    try:
        configs = WageConfig.query.order_by(WageConfig.name.asc()).all()
        for cfg in configs:
            salary_map[cfg.name] = {
                40: cfg.wage_40 or 0,
                60: cfg.wage_60 or 0,
                90: cfg.wage_90 or 0,
            }
            salary_list.append({
                'name': cfg.name,
                's40': cfg.wage_40,
                's60': cfg.wage_60,
                's90': cfg.wage_90,
            })
    except Exception as e:
        errors.append(f"讀取妹妹薪資設定時發生錯誤，可能尚未執行遷移：{e}")

    # 僅在按下「計算」時進行明細與結果計算
    if request.method == 'POST' and action == 'calculate' and records_text:
        if not selected_name:
            errors.append("請先在左側選擇要計算的妹妹。")
        else:
            total_revenue = 0
            total_salary = 0
            meal_fee = 200 if include_meal else 0

            pattern = _re.compile(r'(?P<time>\d{1,2}:\d{2})(?P<name>[^0-9\s/]+)?(?P<amount>\d+)\s*/\s*(?P<len>\d+)\s*/\s*(?P<count>\d+)')

            for raw in records_text.splitlines():
                raw_line = raw.rstrip('\n')
                line = raw_line.strip()
                if not line:
                    continue
                # 跳過只有日期的行，例如「12/13」
                if _re.fullmatch(r'\d{1,2}/\d{1,2}', line):
                    continue

                m = pattern.search(line)
                if not m:
                    errors.append(f"無法識別的紀錄行：{raw_line}")
                    continue

                time_str = m.group('time')
                name = (m.group('name') or '').strip()
                try:
                    amount = int(m.group('amount'))
                    length = int(m.group('len'))
                    count = int(m.group('count'))
                except ValueError:
                    errors.append(f"金額或分鐘數格式錯誤：{raw_line}")
                    continue

                revenue = amount
                total_revenue += revenue

                salary_each = 0
                note = ''
                # 依「選取的妹妹」之薪水表，對當日每一筆 40/60/90 分鐘紀錄都套用同一套標準，
                # 不再依照行內顯示的姓名分配。
                cfg_map = salary_map.get(selected_name)
                if cfg_map:
                    salary_each = cfg_map.get(length, 0)
                    if salary_each == 0:
                        note = '⚠️ 未找到對應分鐘數的薪水設定（此妹妹）'
                else:
                    note = '⚠️ 尚未為此妹妹設定薪水'

                total_salary += salary_each

                # 若含「儲值扣」字樣，加註提示方便人工檢查
                if '儲值扣' in raw_line:
                    if note:
                        note += '｜含儲值扣'
                    else:
                        note = '含儲值扣'

                entries.append({
                    'raw': raw_line,
                    'time': time_str,
                    'name': name,
                    'amount': amount,
                    'length': length,
                    'count': count,
                    'revenue': revenue,
                    'salary': salary_each,
                    'note': note,
                })

            net = total_revenue - (total_salary + meal_fee)
            result = {
                'total_revenue': total_revenue,
                'total_salary': total_salary,
                'meal_fee': meal_fee,
                'net': net,
            }

            # 構造給「輸出區」用的簡易公式
            # 1) 今日總收：金額相加表達式
            revenue_terms = []
            for e in entries:
                try:
                    revenue_terms.append(str(e.get('revenue') or 0))
                except Exception:
                    pass
            if revenue_terms and total_revenue is not None:
                summary_revenue_expr = "+".join(revenue_terms) + f"={total_revenue}"

            # 2) 妹妹薪水：依不同單價分組，輸出多行公式
            #    例如：1000*5=5000（60 分 5 筆）、1700（90 分 1 筆）
            salary_values = [e.get('salary') for e in entries if (e.get('salary') or 0) > 0]
            if salary_values and total_salary is not None:
                unit_counts = {}
                for v in salary_values:
                    unit_counts[v] = unit_counts.get(v, 0) + 1
                lines = []
                for unit in sorted(unit_counts.keys()):
                    cnt = unit_counts[unit]
                    sub_total = unit * cnt
                    if cnt > 1:
                        lines.append(f"{unit}*{cnt}={sub_total}")
                    else:
                        # 單一筆就直接顯示金額，例如「1700」
                        lines.append(str(sub_total))
                summary_salary_expr = "\n".join(lines)

            # 3) 飯錢與總收的公式
            summary_meal = meal_fee if meal_fee else None
            if total_revenue is not None and total_salary is not None:
                subtotal = total_salary + meal_fee
                summary_net_expr = f"{total_revenue}-{subtotal}={net}"

    return render_template(
        'wage_reconcile.html',
        salary_config_text=salary_config_text,
        records_text=records_text,
        include_meal=include_meal,
        selected_name=selected_name,
        salary_list=salary_list,
        entries=entries,
        errors=errors,
        result=result,
        summary_revenue_expr=summary_revenue_expr,
        summary_salary_expr=summary_salary_expr,
        summary_meal=summary_meal,
        summary_net_expr=summary_net_expr,
    )

