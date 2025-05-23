from main import db, User

# 建立初始白名單資料
data = [
    {"line_user_id": "Uxxxxxxxxxxxx", "phone_number": "0987654321"},
    {"line_user_id": "Uyyyyyyyyyyyy", "phone_number": "0911222333"}
]

for item in data:
    user = User(**item)
    db.session.add(user)

db.session.commit()
print("白名單已新增！")
