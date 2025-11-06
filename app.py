
import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))  # ✅ 確保 handler 可被 import

from flask import Flask, render_template, request
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()

from extensions import db
from routes.message import message_bp

app = Flask(__name__)
# 設定 secret_key，支援 session/flash
import secrets
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))
import sys
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))  # ✅ 確保 handler 可被 import

from flask import Flask
from dotenv import load_dotenv

load_dotenv()

from extensions import db
from routes.message import message_bp


app = Flask(__name__)
# 設定 secret_key，支援 session/flash
import secrets
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

# 資料庫連線字串轉換（Heroku/Railway 相容性處理）
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# Blueprint 註冊


app.register_blueprint(message_bp)
from routes.pending_verify import pending_bp
app.register_blueprint(pending_bp)

# 即時班表更新頁面
@app.route("/admin/schedule/")
def admin_schedule():
    return render_template("schedule.html")

# 初始化 admin panel，確保 /admin 路徑可用
from hander.admin_panel import init_admin
with app.app_context():
    db.create_all()
    init_admin(app)


@app.route("/home")
def home():
    try:
        db.session.execute(text("SELECT 1"))
        db_status = "資料庫連線正常"
    except Exception as e:
        db_status = "資料庫連線異常: " + str(e)
    return f"LINE Bot 正常運作中～🍵\n{db_status}"

@app.route("/")
def index():
    from flask import redirect
    return redirect("/home")


# 搜尋功能
from flask import render_template, request
from models import Whitelist, Blacklist, Coupon

@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        # 搜尋白名單
        wl = Whitelist.query.filter(Whitelist.phone.like(f"%{q}%") | Whitelist.name.like(f"%{q}%") | Whitelist.line_id.like(f"%{q}%")).all()
        for w in wl:
            results.append({"type": "白名單", "phone": w.phone, "name": w.name, "line_id": w.line_id})
        # 搜尋黑名單
        bl = Blacklist.query.filter(Blacklist.phone.like(f"%{q}%") | Blacklist.name.like(f"%{q}%")).all()
        for b in bl:
            results.append({"type": "黑名單", "phone": b.phone, "name": b.name})
        # 搜尋抽獎券
        cp = Coupon.query.filter(Coupon.line_user_id.like(f"%{q}%") | Coupon.report_no.like(f"%{q}%")).all()
        for c in cp:
            results.append({"type": "抽獎券", "line_user_id": c.line_user_id, "report_no": c.report_no, "amount": c.amount})
    return render_template("search_result.html", q=q, results=results)

if __name__ == "__main__":
    # 初始化 admin panel
    from hander.admin_panel import init_admin
    with app.app_context():
        db.create_all()
        init_admin(app)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
