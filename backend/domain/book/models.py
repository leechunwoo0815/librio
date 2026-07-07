# backend/domain/book/models.py
"""图书域模型 — 图书信息 + 实体书副本(BookCopy)

V3.1 变更：
  - 新增 BookCopy 模型：每本实体书对应一个副本，有唯一条码
  - Book 模型补充 V3.1 字段：total_stock, offline_available, audio_timeline 等
"""

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.common.base_model import BaseModel
from backend.common.types import BookCopyStatus


class Book(BaseModel):
    """图书模型"""

    __tablename__ = "book"
    __table_args__ = {"extend_existing": True}

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

    # V2.0 在线阅读扩展字段
    word_count = Column(Integer, nullable=True, comment="总词数")
    estimated_reading_minutes = Column(
        Integer, nullable=True, comment="预计阅读时间(分钟)"
    )
    has_audio = Column(SmallInteger, default=0, comment="是否配有音频: 0=无 1=有")
    audio_url = Column(String(255), nullable=True, comment="整书音频URL")
    series_name = Column(String(100), nullable=True, comment="所属系列")
    difficulty_level = Column(
        String(10), nullable=True, comment="难度标签(入门/初级/中级/高级)"
    )
    format = Column(
        SmallInteger, default=0, comment="图书格式: 0=电子+纸质 1=仅电子 2=仅纸质"
    )

    # V3.1 新增字段（OMO 模式）
    price = Column(
        Numeric(10, 2), nullable=True, comment="图书定价（元），用于丢书罚款计算"
    )
    total_stock = Column(Integer, default=0, comment="实体书库存总数")
    available_stock = Column(Integer, default=0, comment="实体书可借数量")
    offline_available = Column(
        SmallInteger, default=0, comment="是否支持线下借阅: 0=否 1=是"
    )
    audio_timeline = Column(
        Text, nullable=True, comment="音频时间线JSON（段落+时间戳）"
    )
    core_vocabulary = Column(Text, nullable=True, comment="核心词汇JSON列表")
    is_published = Column(SmallInteger, default=1, comment="是否上架: 0=下架 1=上架")

    # 关系
    copies = relationship(
        "BookCopy", back_populates="book", foreign_keys="BookCopy.book_id"
    )

    def __repr__(self):
        return f"<Book(id={self.id}, title='{self.title}', isbn='{self.isbn}')>"


class BookCopy(BaseModel):
    """实体书副本 — V3.1 新增

    每本实体书对应一个副本，通过条码唯一标识。
    借阅操作基于 BookCopy，而不是 Book。
    """

    __tablename__ = "book_copy"
    __table_args__ = {"extend_existing": True}

    book_id = Column(
        BigInteger,
        ForeignKey("book.id"),
        nullable=False,
        index=True,
        comment="关联图书ID",
    )
    barcode = Column(
        String(50), unique=True, nullable=False, index=True, comment="副本条码（唯一）"
    )
    status = Column(SmallInteger, default=BookCopyStatus.AVAILABLE, comment="副本状态")

    # 入库信息
    condition_note = Column(String(255), nullable=True, comment="入库时状况备注")
    location = Column(String(50), nullable=True, comment="存放位置（如'1号书架A层'）")

    # 关系
    book = relationship("Book", back_populates="copies", foreign_keys=[book_id])

    def __repr__(self):
        return (
            f"<BookCopy(id={self.id}, barcode='{self.barcode}', status={self.status})>"
        )
