
import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from models import Whitelist, Blacklist, Coupon
from extensions import db


from flask_admin import helpers as admin_helpers

class ModernModelView(ModelView):
    # 自訂按鈕 icon
    create_modal = True
    edit_modal = True
    can_view_details = True
    column_display_pk = True
    page_size = 20
    def render(self, template, **kwargs):
        # 注入 FontAwesome 與自訂 CSS
        if 'admin_custom_css' not in kwargs:
            kwargs['admin_custom_css'] = '/static/admin_custom.css'
        return super().render(template, **kwargs)

def init_admin(app):
    admin = Admin(app, name='後台管理', template_mode='bootstrap4', base_template='admin_custom_master.html')
    admin.add_view(ModernModelView(Whitelist, db.session, name='<i class="fa fa-list"></i> 白名單', endpoint='whitelist'))
    admin.add_view(ModernModelView(Blacklist, db.session, name='<i class="fa fa-ban"></i> 黑名單', endpoint='blacklist'))
    admin.add_view(ModernModelView(Coupon, db.session, name='<i class="fa fa-ticket"></i> 抽獎券', endpoint='coupon'))
    # 確保自訂 CSS 被載入
    @app.context_processor
    def override_admin_css():
        return dict(admin_custom_css='/static/admin_custom.css')
    return admin
