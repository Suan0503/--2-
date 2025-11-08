import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from models import Whitelist, Blacklist, Coupon, TempVerify
from extensions import db


from flask_admin import helpers as admin_helpers


class ModernModelView(ModelView):
    create_modal = True
    edit_modal = True
    can_view_details = True
    column_display_pk = True
    page_size = 20
    def render(self, template, **kwargs):
        if 'admin_custom_css' not in kwargs:
            kwargs['admin_custom_css'] = '/static/admin_custom.css'
        return super().render(template, **kwargs)


class WhitelistModelView(ModernModelView):
    column_searchable_list = ['phone', 'line_id', 'name']
    column_labels = {
        'created_at': '建立時間',
        'date': '日期',
        'phone': '手機',
        'reason': '原因',
        'name': '姓名',
        'line_id': 'LINE ID',
        'line_user_id': 'LINE用戶ID'
    }

class BlacklistModelView(ModernModelView):
    column_searchable_list = ['phone', 'name']
    column_labels = {
        'created_at': '建立時間',
        'date': '日期',
        'phone': '手機',
        'reason': '原因',
        'name': '姓名'
    }

    def _search(self, query, search_term):
        # 手機欄位自動補齊 10 碼
        term = search_term.strip()
        if term.isdigit() and (len(term) == 8 or len(term) == 9):
            if len(term) == 8:
                term = '09' + term
            elif len(term) == 9:
                term = '0' + term
        return super()._search(query, term)

    def on_model_change(self, form, model, is_created):
        from flask import flash
        try:
            super().on_model_change(form, model, is_created)
            if is_created:
                flash('新增黑名單成功！', 'success')
            else:
                flash('黑名單資料已更新！', 'info')
        except Exception as e:
            flash(f'操作失敗：{str(e)}', 'danger')

class CouponModelView(ModernModelView):
    column_searchable_list = ['line_user_id', 'report_no', 'type', 'date']
    column_labels = {
        'id': '編號',
        'line_user_id': 'LINE用戶ID',
        'date': '日期',
        'amount': '金額',
        'created_at': '建立時間',
        'report_no': '抽獎券編號',
        'type': '來源類型'
    }

    def render(self, template, **kwargs):
        # 注入自訂按鈕
        if 'extra_actions' not in kwargs:
            kwargs['extra_actions'] = [
                {'label': '新增白名單', 'url': '/admin_panel/fa_whitelist/new', 'icon': 'fa fa-user-plus'},
                {'label': '新增黑名單', 'url': '/admin_panel/fa_blacklist/new', 'icon': 'fa fa-user-times'},
            ]
        return super().render(template, **kwargs)

class TempVerifyModelView(ModernModelView):
    column_searchable_list = ['phone', 'line_id', 'nickname']
    column_labels = {
        'id': '編號',
        'phone': '手機',
        'line_id': 'LINE ID',
        'nickname': '暱稱',
        'status': '狀態',
        'created_at': '建立時間'
    }
    column_choices = {
        'status': [
            ('pending', '待驗證'),
            ('verified', '已通過'),
            ('failed', '失敗')
        ]
    }
    can_create = False
    can_edit = True
    can_delete = True
    page_size = 20
    def on_model_change(self, form, model, is_created):
        from flask import flash
        super().on_model_change(form, model, is_created)
        if model.status == 'verified':
            flash('已通過驗證，請同步至白名單！', 'success')
        elif model.status == 'failed':
            flash('已標記為失敗。', 'warning')

def init_admin(app):
    # 將 Flask-Admin 掛在 /admin_panel，並指定 endpoint 名稱避免與自訂 'admin' 藍圖衝突
    common_kwargs = dict(name='後台管理', url='/admin_panel', endpoint='admin_panel')
    admin = None
    try:
        admin = Admin(app, base_template='admin/custom_master.html', **common_kwargs)
    except TypeError:
        try:
            admin = Admin(app, **common_kwargs)
        except TypeError:
            admin = Admin(app)
    admin.add_view(WhitelistModelView(Whitelist, db.session, name='<i class="fa fa-list"></i> 白名單', endpoint='fa_whitelist'))
    admin.add_view(BlacklistModelView(Blacklist, db.session, name='<i class="fa fa-ban"></i> 黑名單', endpoint='fa_blacklist'))
    admin.add_view(CouponModelView(Coupon, db.session, name='<i class="fa fa-ticket"></i> 抽獎券', endpoint='fa_coupon'))
    admin.add_view(TempVerifyModelView(TempVerify, db.session, name='<i class="fa fa-clock"></i> 暫存名單驗證', endpoint='fa_tempverify'))
    # 確保自訂 CSS 被載入
    @app.context_processor
    def override_admin_css():
        # 仍保留舊變數以兼容，實際樣式由 admin_panel_new.css 提供
        return dict(admin_custom_css='/static/admin_panel_new.css')
    # 若應用有啟用 CSRFProtect，豁免 Flask-Admin 內建的 POST 視圖，避免 400 錯誤
    try:
        csrf = app.extensions.get('csrf')
        if csrf:
            for view in admin._views:
                for method_name in ('create_view', 'edit_view', 'delete_view'):
                    if hasattr(view, method_name):
                        try:
                            csrf.exempt(getattr(view, method_name))
                        except Exception:
                            pass
    except Exception:
        pass
    return admin
