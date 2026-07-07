# backend/domain/admin/services/book_service.py
"""管理端图书/题库 Service — 从 AdminService 拆分出来的独立域服务。"""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.common.exceptions import NotFoundError
from backend.domain.advancement.models import QuestionBank
from backend.domain.admin.schemas import (
    BulkImportBookItem,
    BulkImportQuestionItem,
    UpdateQuestionRequest,
)


class AdminBookService:
    """管理端图书相关操作：副本、批量导入、题库搜索/更新、全局统计。"""

    def __init__(self, db: Session):
        self.db = db

    def get_book_stats(self) -> dict:
        """获取图书全局统计：总数 / 有音频 / 有测验题"""
        from sqlalchemy import func
        from backend.domain.book.models import Book
        from backend.domain.advancement.models import QuestionBank

        total_books = (
            self.db.query(func.count(Book.id)).filter(Book.is_deleted == 0).scalar()
            or 0
        )
        audio_books = (
            self.db.query(func.count(Book.id))
            .filter(Book.is_deleted == 0, Book.has_audio == 1)
            .scalar()
            or 0
        )
        quiz_books = (
            self.db.query(func.count(func.distinct(QuestionBank.book_id)))
            .filter(QuestionBank.is_deleted == 0)
            .scalar()
            or 0
        )
        return {
            "total_books": total_books,
            "audio_books": audio_books,
            "quiz_books": quiz_books,
        }

    def list_bookcopies(self) -> list[dict]:
        """获取所有副本列表"""
        from backend.domain.book.models import BookCopy

        copies = (
            self.db.query(BookCopy).filter(BookCopy.is_deleted == 0).limit(500).all()
        )
        return [
            {
                "id": c.id,
                "barcode": c.barcode,
                "book_id": c.book_id,
                "status": c.status,
                "location": c.location,
                "create_time": c.create_time.isoformat() if c.create_time else None,
            }
            for c in copies
        ]

    def bulk_import_books(self, books: list[BulkImportBookItem]) -> dict:
        """批量导入图书（PC-008）"""
        from backend.domain.book.models import Book

        results = []
        for item in books:
            try:
                isbn = item.isbn.strip()
                if not isbn:
                    results.append(
                        {"isbn": isbn, "status": "error", "reason": "ISBN 为空"}
                    )
                    continue
                existing = (
                    self.db.query(Book)
                    .filter(Book.isbn == isbn, Book.is_deleted == 0)
                    .first()
                )
                if existing:
                    results.append(
                        {"isbn": isbn, "status": "skip", "reason": "ISBN 已存在"}
                    )
                    continue
                book = Book(
                    isbn=isbn,
                    title=item.title,
                    author=item.author,
                    ar_value=item.ar_value,
                    age_min=item.age_min,
                    age_max=item.age_max,
                    word_count=item.word_count,
                )
                self.db.add(book)
                self.db.flush()
                results.append({"isbn": isbn, "status": "ok", "id": book.id})
            except Exception as e:
                results.append({"isbn": item.isbn, "status": "error", "reason": str(e)})
        self.db.commit()
        ok_count = sum(1 for r in results if r["status"] == "ok")
        return {"total": len(books), "success": ok_count, "results": results}

    def bulk_import_questions(self, questions: list[BulkImportQuestionItem]) -> dict:
        """批量导入题目（PC-016）"""
        from backend.domain.book.models import Book

        results = []
        for item in questions:
            try:
                book_isbn = item.isbn.strip()
                book = (
                    self.db.query(Book)
                    .filter(Book.isbn == book_isbn, Book.is_deleted == 0)
                    .first()
                )
                if not book:
                    results.append(
                        {"isbn": book_isbn, "status": "error", "reason": "ISBN 不存在"}
                    )
                    continue
                q = QuestionBank(
                    book_id=book.id,
                    question_text=item.question_text,
                    option_a=item.option_a,
                    option_b=item.option_b,
                    option_c=item.option_c,
                    option_d=item.option_d,
                    correct_answer=item.correct_answer,
                    difficulty=item.difficulty,
                )
                self.db.add(q)
                self.db.flush()
                results.append({"isbn": book_isbn, "status": "ok", "id": q.id})
            except Exception as e:
                results.append({"isbn": item.isbn, "status": "error", "reason": str(e)})
        self.db.commit()
        ok_count = sum(1 for r in results if r["status"] == "ok")
        return {"total": len(questions), "success": ok_count, "results": results}

    def search_questions_by_book(self, keyword: str) -> dict:
        """按书名/ISBN搜索题库"""
        from backend.domain.book.models import Book

        books = (
            self.db.query(Book)
            .filter(
                Book.is_deleted == 0,
                or_(
                    Book.title.like(f"%{keyword}%"),
                    Book.isbn.like(f"%{keyword}%"),
                ),
            )
            .all()
        )

        results = []
        for book in books:
            questions = (
                self.db.query(QuestionBank)
                .filter(
                    QuestionBank.book_id == book.id,
                    QuestionBank.is_deleted == 0,
                )
                .order_by(QuestionBank.difficulty)
                .all()
            )
            for q in questions:
                results.append(
                    {
                        "id": q.id,
                        "book_id": book.id,
                        "book_title": book.title,
                        "book_isbn": book.isbn,
                        "question_text": q.question_text,
                        "option_a": q.option_a,
                        "option_b": q.option_b,
                        "option_c": q.option_c,
                        "option_d": q.option_d,
                        "correct_answer": q.correct_answer,
                        "explanation": q.explanation,
                        "difficulty": q.difficulty,
                    }
                )
        return {"items": results, "total": len(results)}

    def update_question(self, question_id: int, data: UpdateQuestionRequest) -> dict:
        """更新题目"""
        q = (
            self.db.query(QuestionBank)
            .filter(QuestionBank.id == question_id, QuestionBank.is_deleted == 0)
            .first()
        )
        if not q:
            raise NotFoundError("题目不存在")

        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(q, field, value)

        self.db.commit()
        return {"success": True, "id": q.id}

    def batch_generate_copies(self, isbn: str, count: int) -> dict:
        """批量生成实体书副本条码（PC-009）"""
        from backend.domain.book.models import Book, BookCopy

        book = (
            self.db.query(Book).filter(Book.isbn == isbn, Book.is_deleted == 0).first()
        )
        if not book:
            raise NotFoundError(f"ISBN {isbn} 不存在")

        results = []
        for i in range(count):
            barcode = f"{isbn}-{i + 1:04d}"
            existing = (
                self.db.query(BookCopy).filter(BookCopy.barcode == barcode).first()
            )
            if existing:
                results.append(
                    {"barcode": barcode, "status": "skip", "reason": "条码已存在"}
                )
                continue
            copy = BookCopy(book_id=book.id, barcode=barcode)
            self.db.add(copy)
            self.db.flush()
            # 更新库存
            book.total_stock = (book.total_stock or 0) + 1
            book.available_stock = (book.available_stock or 0) + 1
            results.append({"barcode": barcode, "status": "ok", "id": copy.id})

        self.db.commit()
        ok_count = sum(1 for r in results if r["status"] == "ok")
        return {
            "isbn": isbn,
            "book_title": book.title,
            "total": count,
            "success": ok_count,
            "results": results,
        }
