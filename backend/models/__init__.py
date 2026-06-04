# backend/models/__init__.py
"""
[What] 模型包初始化文件
[Why] 统一导出所有模型
[How] 导入所有模型类
"""

from backend.models.user import User
from backend.models.child import Child
from backend.models.book import Book
from backend.models.collection import Collection
from backend.models.borrow import Borrow
from backend.models.order import Order

__all__ = ["User", "Child", "Book", "Collection", "Borrow", "Order"]