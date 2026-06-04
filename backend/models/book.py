# backend/models/book.py
"""
[What] 图书模型
[Why] 定义图书表结构
[How] 使用SQLAlchemy ORM映射
"""

from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime, SmallInteger, Numeric, Integer, Text
from backend.database import Base


class Book(Base):
    __tablename__ = "book"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True, comment="主键")
    isbn = Column(String(20), nullable=False, unique=True, index=True, comment="ISBN号")
    title = Column(String(255), nullable=False, index=True, comment="书名")
    author = Column(String(100), nullable=False, comment="作者")
    publisher = Column(String(100), nullable=True, comment="出版社")
    ar_value = Column(Numeric(3, 1), nullable=False, index=True, comment="AR阅读等级")
    lexile_value = Column(Integer, nullable=True, comment="蓝思值")
    age_min = Column(SmallInteger, nullable=False, comment="适合最小年龄")
    age_max = Column(SmallInteger, nullable=False, comment="适合最大年龄")
    theme = Column(String(50), nullable=True, comment="主题")
    summary = Column(Text, nullable=True, comment="内容简介")
    cover = Column(String(255), nullable=True, comment="封面URL")
    total_pages = Column(Integer, nullable=True, comment="总页数")
    create_time = Column(DateTime, default=datetime.now, comment="创建时间")
    update_time = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    is_deleted = Column(SmallInteger, default=0, comment="软删除标记")

    def __repr__(self):
        return f"<Book(id={self.id}, title='{self.title}', ar_value={self.ar_value})>"
