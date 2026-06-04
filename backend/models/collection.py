# backend/models/collection.py
"""
[What] 图书收藏模型
[Why] 定义图书收藏表结构
[How] 使用SQLAlchemy ORM映射
"""

from datetime import datetime
from sqlalchemy import Column, BigInteger, DateTime, SmallInteger, Integer
from backend.database import Base


class Collection(Base):
    __tablename__ = "collection"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, comment="主键")
    child_id = Column(BigInteger, nullable=False, index=True, comment="孩子ID")
    book_id = Column(BigInteger, nullable=False, index=True, comment="图书ID")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    is_deleted = Column(SmallInteger, default=0, comment="软删除标记")

    def __repr__(self):
        return f"<Collection(id={self.id}, child_id={self.child_id}, book_id={self.book_id})>"
