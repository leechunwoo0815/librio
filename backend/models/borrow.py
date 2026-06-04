# backend/models/borrow.py
"""
[What] 借阅模型
[Why] 定义借阅表结构
[How] 使用SQLAlchemy ORM映射
"""

from datetime import datetime
from sqlalchemy import Column, BigInteger, DateTime, SmallInteger, Integer, String
from backend.database import Base


class Borrow(Base):
    __tablename__ = "borrow"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, comment="主键")
    child_id = Column(BigInteger, nullable=False, index=True, comment="孩子ID")
    book_id = Column(BigInteger, nullable=False, index=True, comment="图书ID")
    status = Column(String(20), nullable=False, default="borrowed", comment="状态: borrowed/returned/overdue")
    borrow_time = Column(DateTime, default=datetime.now, comment="借阅时间")
    due_time = Column(DateTime, nullable=True, comment="应还时间")
    return_time = Column(DateTime, nullable=True, comment="实际归还时间")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    is_deleted = Column(SmallInteger, default=0, comment="软删除标记")

    def __repr__(self):
        return f"<Borrow(id={self.id}, child_id={self.child_id}, book_id={self.book_id}, status='{self.status}')>"
