from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@localhost/你的資料庫'
db = SQLAlchemy(app)

# 匯入或複製 whitelist 資料表
class Whitelist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True)
    name = db.Column(db.String(80))

ADMIN_USER = 'admin'
ADMIN_PASS_HASH = 'pbkdf2:sha256:...'  # 用 werkzeug 產生的密碼雜湊

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USER and check_password_hash(ADMIN_PASS_HASH, request.form['password']):
            session['admin'] = ADMIN_USER
            return redirect(url_for('dashboard'))
        flash('登入失敗')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'admin' not in session:
        return redirect(url_for('login'))
    whitelists = Whitelist.query.all()
    return render_template('dashboard.html', whitelists=whitelists)

@app.route('/add_whitelist', methods=['POST'])
def add_whitelist():
    if 'admin' not in session:
        return redirect(url_for('login'))
    phone = request.form['phone']
    name = request.form['name']
    if Whitelist.query.filter_by(phone=phone).first():
        flash('電話已存在')
    else:
        db.session.add(Whitelist(phone=phone, name=name))
        db.session.commit()
        flash('新增成功')
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(port=5001, debug=True)
