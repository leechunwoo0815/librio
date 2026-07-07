# backend/middleware/trace.py
"""
[What] 请求追踪中间件
[Why] 每个请求分配唯一TraceID，贯穿所有日志
[How] 从Header提取或自动生成，注入request.state和response header
"""

import logging
import uuid

from fastapi import Request

logger = logging.getLogger(__name__)


async def trace_middleware(request: Request, call_next):
    """
    [What] 注入TraceID到请求生命周期
    [Why] 方便日志追踪和问题排查
    [How] 优先使用客户端传入的X-Trace-ID，否则自动生成
    """
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4())[:8])
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    return response
