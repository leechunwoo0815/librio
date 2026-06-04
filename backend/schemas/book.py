# backend/schemas/book.py
"""
[What] 图书Pydantic模型
[Why] 用于API请求/响应数据验证
[How] 使用Pydantic定义数据结构
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class BookBase(BaseModel):
    """图书基础字段"""
    isbn: str = Field(..., description="ISBN号")
    title: str = Field(..., description="书名")
    author: str = Field(..., description="作者")
    publisher: Optional[str] = Field(None, description="出版社")
    ar_value: Decimal = Field(..., description="AR阅读等级")
    lexile_value: Optional[int] = Field(None, description="蓝思值")
    age_min: int = Field(..., description="适合最小年龄")
    age_max: int = Field(..., description="适合最大年龄")
    theme: Optional[str] = Field(None, description="主题")
    summary: Optional[str] = Field(None, description="内容简介")
    cover: Optional[str] = Field(None, description="封面URL")
    total_pages: Optional[int] = Field(None, description="总页数")


class BookCreate(BookBase):
    """创建图书请求"""
    pass


class BookResponse(BookBase):
    """图书响应"""
    id: int
    create_time: datetime

    class Config:
        from_attributes = True


class BookSearch(BaseModel):
    """图书搜索请求"""
    keyword: Optional[str] = Field(None, description="关键词（书名/作者）")
    ar_level: Optional[str] = Field(None, description="AR等级范围，如 AR1-AR3")
    age_min: Optional[int] = Field(None, description="最小年龄")
    age_max: Optional[int] = Field(None, description="最大年龄")
    theme: Optional[str] = Field(None, description="主题")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class BookListResponse(BaseModel):
    """图书列表响应"""
    total: int
    items: list[BookResponse]


class ReservationCreate(BaseModel):
    """创建预约请求"""
    book_id: int = Field(..., description="图书ID")
    child_id: int = Field(..., description="孩子ID")


class ReservationResponse(BaseModel):
    """预约响应"""
    id: int
    status: str

    class Config:
        from_attributes = True
