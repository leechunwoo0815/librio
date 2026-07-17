# backend/common/distributed_lock.py
import functools
import logging
import uuid
from contextlib import contextmanager

import redis

from backend.config import get_settings

logger = logging.getLogger(__name__)


def _get_redis_client():
    settings = get_settings()
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
    )


@contextmanager
def redis_lock(lock_key: str, timeout: int = 300):
    client = None
    try:
        client = _get_redis_client()
        lock_value = str(uuid.uuid4())
        acquired = client.set(lock_key, lock_value, nx=True, ex=timeout)
        if not acquired:
            yield False
            return

        yield True
    except redis.ConnectionError:
        logger.warning(f"Redis 不可用，任务 {lock_key} 本地降级执行（无分布式锁）")
        client = None
        yield True
    finally:
        if client is not None:
            _safe_release(client, lock_key, lock_value)


def _safe_release(client, lock_key: str, lock_value: str):
    try:
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        client.eval(lua_script, 1, lock_key, lock_value)
    except Exception:
        logger.warning(f"Failed to release lock {lock_key}", exc_info=True)


def distributed_lock(lock_key: str, timeout: int = 300):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with redis_lock(lock_key, timeout) as acquired:
                if not acquired:
                    logger.info(f"Lock not acquired for {lock_key}, skipping")
                    return
                return func(*args, **kwargs)

        return wrapper

    return decorator
