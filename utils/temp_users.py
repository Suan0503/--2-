# -*- coding: utf-8 -*-
"""
Robust temporary user storage used by the verification flow.

Behavior:
- Try to use Redis if available (REDIS_URL or REDIS_HOST/REDIS_PORT env).
- If Redis is unavailable at import time or during an operation, fall back to
  an in-memory dict with expiry. The in-memory store is process-local and not
  shared between workers/replicas.
- Exposes get_temp_user, set_temp_user, pop_temp_user, all_temp_users.
"""

from __future__ import annotations
import os
import json
import time
import logging
from typing import Optional, Dict, Any, Tuple

REDIS_URL = os.getenv("REDIS_URL") or os.getenv("REDIS_URI")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
DEFAULT_EXPIRE = int(os.getenv("TEMP_USER_EXPIRE_SECONDS", "3600"))  # default 1 hour

_use_redis = False
_redis = None

# In-memory fallback store: { user_id: (data_dict, expire_ts) }
_mem_store: Dict[str, Tuple[Dict[str, Any], float]] = {}

try:
    if REDIS_URL:
        import redis
        _redis = redis.from_url(REDIS_URL, db=REDIS_DB, socket_connect_timeout=2)
    else:
        import redis
        _redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, socket_connect_timeout=2)
    # try a quick ping to ensure it's reachable
    try:
        _redis.ping()
        _use_redis = True
        logging.info("temp_users: connected to Redis")
    except Exception:
        logging.warning("temp_users: Redis not reachable at startup; falling back to in-memory store")
        _use_redis = False
except Exception:
    logging.warning("temp_users: redis library not available or failed to init; using in-memory store")
    _use_redis = False


def _redis_key(user_id: str) -> str:
    return f"temp_user:{user_id}"


def _now_ts() -> float:
    return time.time()


def set_temp_user(user_id: str, data: Dict[str, Any], expire: Optional[int] = None) -> None:
    """
    Store temp user data. expire in seconds; default comes from DEFAULT_EXPIRE.
    """
    if expire is None:
        expire = DEFAULT_EXPIRE
    if _use_redis and _redis is not None:
        try:
            _redis.set(_redis_key(user_id), json.dumps(data), ex=expire)
            return
        except Exception:
            logging.exception("temp_users: Redis set failed, switching to in-memory for this operation")
            # fall through to in-memory fallback

    # in-memory fallback
    expire_ts = _now_ts() + expire if expire and expire > 0 else float("inf")
    _mem_store[user_id] = (data, expire_ts)


def get_temp_user(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Return the stored dict for user_id or None if not found/expired.
    """
    if _use_redis and _redis is not None:
        try:
            val = _redis.get(_redis_key(user_id))
            if not val:
                return None
            # val may be bytes
            if isinstance(val, bytes):
                try:
                    return json.loads(val.decode("utf-8"))
                except Exception:
                    try:
                        return json.loads(val)
                    except Exception:
                        logging.exception("temp_users: failed to parse redis value as json")
                        return None
            else:
                try:
                    return json.loads(val)
                except Exception:
                    logging.exception("temp_users: failed to parse redis value as json (non-bytes)")
                    return None
        except Exception:
            logging.exception("temp_users: Redis get failed, falling back to in-memory for this call")
            # fall through to in-memory fallback

    # in-memory fallback
    tup = _mem_store.get(user_id)
    if not tup:
        return None
    data, expire_ts = tup
    if expire_ts is not None and _now_ts() > expire_ts:
        # expired
        try:
            _mem_store.pop(user_id, None)
        except Exception:
            pass
        return None
    return data


def pop_temp_user(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Remove and return the stored data for user_id.
    """
    if _use_redis and _redis is not None:
        try:
            val = _redis.get(_redis_key(user_id))
            _redis.delete(_redis_key(user_id))
            if not val:
                return None
            if isinstance(val, bytes):
                try:
                    return json.loads(val.decode("utf-8"))
                except Exception:
                    try:
                        return json.loads(val)
                    except Exception:
                        logging.exception("temp_users: failed to parse redis pop value as json")
                        return None
            else:
                try:
                    return json.loads(val)
                except Exception:
                    logging.exception("temp_users: failed to parse redis pop value as json (non-bytes)")
                    return None
        except Exception:
            logging.exception("temp_users: Redis pop failed, falling back to in-memory for this call")
            # fall through to in-memory

    # in-memory fallback
    tup = _mem_store.pop(user_id, None)
    if not tup:
        return None
    data, _ = tup
    return data


def all_temp_users() -> Dict[str, Dict[str, Any]]:
    """
    Return a dict of all temp users currently stored (non-expired).
    Note: If Redis is used, this will SCAN keys matching the temp_user: prefix.
    """
    out: Dict[str, Dict[str, Any]] = {}

    if _use_redis and _redis is not None:
        try:
            # use scan_iter to avoid blocking Redis
            pattern = "temp_user:*"
            for k in _redis.scan_iter(match=pattern, count=100):
                try:
                    if isinstance(k, bytes):
                        key = k.decode("utf-8")
                    else:
                        key = str(k)
                    user_id = key.split("temp_user:", 1)[-1]
                    val = _redis.get(key)
                    if not val:
                        continue
                    if isinstance(val, bytes):
                        obj = json.loads(val.decode("utf-8"))
                    else:
                        obj = json.loads(val)
                    out[user_id] = obj
                except Exception:
                    logging.exception("temp_users: failed to read one redis key in all_temp_users")
                    continue
            return out
        except Exception:
            logging.exception("temp_users: Redis scan_iter failed, falling back to in-memory for this call")
            # fall through to in-memory fallback

    # in-memory fallback: purge expired items and return remaining
    now = _now_ts()
    to_delete = []
    for uid, (data, expire_ts) in list(_mem_store.items()):
        if expire_ts is not None and now > expire_ts:
            to_delete.append(uid)
            continue
        out[uid] = data
    for uid in to_delete:
        _mem_store.pop(uid, None)
    return out
