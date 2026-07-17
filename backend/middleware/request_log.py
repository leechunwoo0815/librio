# backend/middleware/request_log.py
"""请求日志中间件 — 记录所有 HTTP 请求与响应，便于排查浏览器端异常。"""

import json as json_lib
import logging
from logging.handlers import RotatingFileHandler
import time
import uuid
from pathlib import Path

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# 确保日志目录存在
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)


class JSONFormatter(logging.Formatter):
    """JSON 结构化日志格式化器 — 每行一个 JSON 对象，兼容 ELK/Loki"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "trace_id"):
            log_entry["trace_id"] = record.trace_id
        if record.exc_info and record.exc_info[0]:
            log_entry["exc"] = self.formatException(record.exc_info)
        return json_lib.dumps(log_entry, ensure_ascii=False)


# 配置请求日志记录器
logger = logging.getLogger("librio.request")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    handler = RotatingFileHandler(
        LOG_DIR / "admin_requests.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=30,
        encoding="utf-8",
    )
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)


def _extract_admin_id(request: Request) -> str | None:
    """从 Authorization Header 中解析 admin/user id（不验证签名，仅用于日志定位）。"""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None
    try:
        import base64

        token = auth.split(" ", 1)[1]
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json_lib.loads(base64.b64decode(payload_b64).decode("utf-8"))
        return str(payload.get("sub") or payload.get("admin_id") or "")
    except Exception:
        return None


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        path = request.url.path
        method = request.method
        client = request.client.host if request.client else "-"
        admin_id = _extract_admin_id(request)
        trace_id = getattr(request.state, "trace_id", None) or request.headers.get(
            "X-Trace-Id", uuid.uuid4().hex[:16]
        )

        try:
            response = await call_next(request)
            duration_ms = round((time.time() - start) * 1000, 2)
            status = response.status_code
            logger.info(
                json_lib.dumps(
                    {
                        "method": method,
                        "path": path,
                        "status": status,
                        "cost_ms": duration_ms,
                        "client": client,
                        "admin_id": admin_id or "-",
                        "trace_id": trace_id,
                    },
                    ensure_ascii=False,
                )
            )
            return response
        except Exception as exc:
            duration_ms = round((time.time() - start) * 1000, 2)
            logger.error(
                json_lib.dumps(
                    {
                        "method": method,
                        "path": path,
                        "status": 500,
                        "cost_ms": duration_ms,
                        "client": client,
                        "admin_id": admin_id or "-",
                        "trace_id": trace_id,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                ),
                exc_info=True,
            )
            raise
