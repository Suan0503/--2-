
# utils/temp_users.py
# Redis 版 temp_users，支援 get/set/pop，並自動 fallback 為本地 dict（方便本地測試）
import os
import json
try:
	import redis
	REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
	r = redis.Redis.from_url(REDIS_URL)
	USE_REDIS = True
except Exception:
	r = None
	USE_REDIS = False

_local_temp_users = {}
_local_manual_verify_pending = {}

def _redis_key(user_id):
	return f"temp_users:{user_id}"

def get_temp_user(user_id):
	if USE_REDIS:
		data = r.get(_redis_key(user_id))
		return json.loads(data) if data else None
	return _local_temp_users.get(user_id)

def set_temp_user(user_id, value):
	if USE_REDIS:
		r.set(_redis_key(user_id), json.dumps(value), ex=3600)
	else:
		_local_temp_users[user_id] = value

def pop_temp_user(user_id):
	if USE_REDIS:
		r.delete(_redis_key(user_id))
	else:
		_local_temp_users.pop(user_id, None)

def all_temp_users():
	if USE_REDIS:
		keys = r.keys("temp_users:*")
		result = {}
		for k in keys:
			uid = k.decode().split(":",1)[1]
			result[uid] = json.loads(r.get(k))
		return result
	return dict(_local_temp_users)

# manual_verify_pending 也改為 Redis
def _manual_key(user_id):
	return f"manual_verify_pending:{user_id}"

def get_manual_pending(user_id):
	if USE_REDIS:
		data = r.get(_manual_key(user_id))
		return json.loads(data) if data else None
	return _local_manual_verify_pending.get(user_id)

def set_manual_pending(user_id, value):
	if USE_REDIS:
		r.set(_manual_key(user_id), json.dumps(value), ex=3600)
	else:
		_local_manual_verify_pending[user_id] = value

def pop_manual_pending(user_id):
	if USE_REDIS:
		r.delete(_manual_key(user_id))
	else:
		_local_manual_verify_pending.pop(user_id, None)

def all_manual_pending():
	if USE_REDIS:
		keys = r.keys("manual_verify_pending:*")
		result = {}
		for k in keys:
			uid = k.decode().split(":",1)[1]
			result[uid] = json.loads(r.get(k))
		return result
	return dict(_local_manual_verify_pending)
