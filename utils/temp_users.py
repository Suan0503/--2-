# utils/temp_users.py
# 全局暫存用戶流程資料，供多個 handler 模組共用


import os
import json

temp_users = {}
manual_verify_pending = {}

# Redis 物件（如有）
redis_client = None
try:
	import redis
	REDIS_URL = os.getenv("REDIS_URL")
	if REDIS_URL:
		redis_client = redis.StrictRedis.from_url(REDIS_URL)
except Exception:
	redis_client = None

def get_temp_user(user_id):
	if redis_client:
		data = redis_client.get(f"temp_user:{user_id}")
		return json.loads(data) if data else None
	return temp_users.get(user_id)

def set_temp_user(user_id, data):
	# 強制補齊 user_id 欄位
	data["user_id"] = user_id
	# 強制補齊 line_user_id 欄位
	data["line_user_id"] = user_id
	# 強制補齊 nickname 欄位（優先 name, display_name, 其次空字串）
	if "nickname" not in data or not data["nickname"]:
		data["nickname"] = data.get("name") or data.get("display_name") or ""
	if redis_client:
		redis_client.set(f"temp_user:{user_id}", json.dumps(data), ex=3600)
	temp_users[user_id] = data

def pop_temp_user(user_id):
	if redis_client:
		redis_client.delete(f"temp_user:{user_id}")
	return temp_users.pop(user_id, None)
