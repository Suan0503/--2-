from main import db, User
from datetime import datetime

data = [
    {"phone_number": "0988888888", "line_user_id": "USER_ID1", "status": "white"},
    {"phone_number": "0911222333", "line_user_id": "USER_ID2", "status": "black"},
]

with db.session.begin():
    for d in data:
        if not User.query.filter_by(phone_number=d["phone_number"]).first():
            user = User(
                phone_number=d["phone_number"],
                line_user_id=d["line_user_id"],
                status=d["status"],
                verified_at=datetime.now() if d["status"] == "white" else None
            )
            db.session.add(user)

print("✅ 初始白名單／黑名單資料新增完成")
