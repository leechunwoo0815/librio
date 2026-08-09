# backend/common/distributed_lock.py
import functools
import logging
import uuid
from contextlib import contextmanager

import redis

from backend.config import get_settings

logger = logging.getLogger(__name__)


def get_redis_client():
    """获取 Redis 客户端（供分布式锁/缓存等共用）"""
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
        client = get_redis_client()
        lock_value = str(uuid.uuid4())
        acquired = client.set(lock_key, lock_value, nx=True, ex=timeout)
        if not acquired:
            yield False
            return

        yield True
    except redis.RedisError:
        # RedisError 覆盖 ConnectionError / TimeoutError / 连接池耗尽等（审查 P1-3）
        fail_open = get_settings().REDIS_LOCK_FAIL_OPEN
        if fail_open:
            logger.warning(
                f"Redis 不可用，任务 {lock_key} 本地降级执行（无分布式锁，"
                "多实例部署请设 REDIS_LOCK_FAIL_OPEN=false）"
            )
            client = None
            yield True
        else:
            logger.error(
                f"Redis 不可用且 FAIL_OPEN=false，任务 {lock_key} 跳过执行",
                exc_info=True,
            )
            client = None
            yield False
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
                # F-021 终审：任务入口生成 trace_id，全任务日志可用同一 ID 关联
                trace_id = str(uuid.uuid4())[:12]
                logger.info(f"TASK_START trace_id={trace_id} job={lock_key}")
                try:
                    return func(*args, **kwargs)
                finally:
                    logger.info(f"TASK_END trace_id={trace_id} job={lock_key}")

        return wrapper

    return decorator
