from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.temp_users import temp_users, pop_temp_user
from models import Whitelist
from extensions import db

pending_bp = Blueprint('pending_verify', __name__)

@pending_bp.route('/admin/pending_verify/', methods=['GET', 'POST'])
def pending_verify():
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        user = temp_users.get(user_id)
        if user:
            # 自動補齊 line_user_id
            line_user_id = user.get('line_user_id') or user.get('user_id') or user_id
            from datetime import datetime
            wl = Whitelist(
                phone=user.get('phone'),
                name=user.get('nickname'),
                line_id=user.get('line_id'),
                line_user_id=line_user_id,
                date=datetime.now().strftime('%Y-%m-%d'),
                created_at=datetime.now()
            )
            db.session.add(wl)
            db.session.commit()
            pop_temp_user(user_id)
            flash(f"已通過驗證並加入白名單：{user.get('nickname')}", 'success')
            return redirect(url_for('pending_verify.pending_verify'))
        else:
            flash("找不到該暫存用戶資料。", 'danger')
            return redirect(url_for('pending_verify.pending_verify'))
    # 顯示所有暫存用戶
    users = [ {'user_id': uid, **data} for uid, data in temp_users.items() ]
    return render_template('pending_verify.html', users=users)