# backend/bootstrap.py
"""
[What] 应用启动引导 — 事件处理器注册
[Why] 集中管理所有领域事件处理器的注册
[How] 在 main.py lifespan 中调用 register_event_handlers()

事件处理器已按域拆分到 backend/events/ 目录：
  - quiz_handlers.py — 测验相关（6 个 handler）
  - order_handlers.py — 订单/押金（2 个 handler）
  - borrow_handlers.py — 借阅/预约/逾期（6 个 handler）
  - misc_handlers.py — 打卡/晋级证书（2 个 handler）
  - registry.py — 注册表（subscribe 调用）
"""

from backend.events.registry import register_event_handlers  # noqa: F401

__all__ = ["register_event_handlers"]
