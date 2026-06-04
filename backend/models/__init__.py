# backend/models/__init__.py
"""
[What] 模型包初始化文件
[Why] 统一导出所有模型
[How] 导入所有模型类
"""

from backend.models.user import User
from backend.models.child import Child

__all__ = ["User", "Child"]