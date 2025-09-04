
import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from models import Whitelist, Blacklist, Coupon
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
                {'label': '新增白名單', 'url': '/admin/whitelist/new', 'icon': 'fa fa-user-plus'},
                {'label': '新增黑名單', 'url': '/admin/blacklist/new', 'icon': 'fa fa-user-times'},
            ]
        return super().render(template, **kwargs)

def init_admin(app):
    admin = Admin(app, name='後台管理', template_mode='bootstrap4', base_template='admin_custom_master.html')
    admin.add_view(WhitelistModelView(Whitelist, db.session, name='<i class="fa fa-list"></i> 白名單', endpoint='whitelist'))
    admin.add_view(BlacklistModelView(Blacklist, db.session, name='<i class="fa fa-ban"></i> 黑名單', endpoint='blacklist'))
    admin.add_view(CouponModelView(Coupon, db.session, name='<i class="fa fa-ticket"></i> 抽獎券', endpoint='coupon'))
    # 確保自訂 CSS 被載入
    @app.context_processor
    def override_admin_css():
        return dict(admin_custom_css='/static/admin_custom.css')
    return admin
