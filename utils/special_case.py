def is_special_case(user_id):
    # 依你的規則判斷
    # 將需要手動驗證的 user_id 填在 special_ids 這個 set 裡
    special_ids = {
        "U2bcd63000805da076721eb62872bc39f",  # 管理員A
        "U5ce6c382d12eaea28d98f2d48673b4b8",  # 管理員B
        "U8f3cc921a9dd18d3e257008a34dd07c1",  # 管理員C
        # 增加其他需要手動驗證的 user_id
    }
    return user_id in special_ids
