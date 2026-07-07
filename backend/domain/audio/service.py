# backend/domain/audio/service.py
"""音频域业务逻辑"""

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.domain.audio.models import AudioFile
from backend.domain.audio.schemas import (
    AudioCreateRequest,
    AudioUpdateRequest,
    AudioResponse,
    AudioListResponse,
)
from backend.common.exceptions import NotFoundError


class AudioService:
    """音频服务"""

    def __init__(self, db: Session):
        self.db = db

    def list_audios(
        self,
        keyword: str | None = None,
        reader: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AudioListResponse:
        """获取音频列表"""
        query = self.db.query(AudioFile).filter(AudioFile.is_deleted == 0)

        if keyword:
            query = query.filter(AudioFile.filename.contains(keyword))
        if reader:
            query = query.filter(AudioFile.reader == reader)

        total = query.count()
        items = query.order_by(AudioFile.create_time.desc()).offset((page - 1) * page_size).limit(page_size).all()

        result = []
        for a in items:
            result.append(AudioResponse(
                id=a.id,
                filename=a.filename,
                file_url=a.file_url,
                book_id=a.book_id,
                book_title=a.book_title,
                page_number=a.page_number,
                page_label=a.page_label or "全文",
                duration=a.duration,
                duration_seconds=a.duration_seconds,
                reader=a.reader,
                status=a.status,
                file_size=a.file_size,
                create_time=a.create_time,
            ))

        # 统计数据（使用 SQL 聚合，避免全表加载）
        # 关联图书数
        book_count = self.db.query(func.count(func.distinct(AudioFile.book_id))).filter(
            AudioFile.is_deleted == 0,
            AudioFile.book_id.isnot(None)
        ).scalar() or 0

        # 总时长
        total_duration_seconds = self.db.query(
            func.sum(AudioFile.duration_seconds)
        ).filter(
            AudioFile.is_deleted == 0,
            AudioFile.duration_seconds.isnot(None)
        ).scalar() or 0

        stats = {
            "total": total,
            "book_count": book_count,
            "total_duration": self._format_duration(total_duration_seconds),
        }

        return AudioListResponse(items=result, stats=stats, total=total)

    def get_audio(self, audio_id: int) -> AudioResponse:
        """获取音频详情"""
        a = self.db.query(AudioFile).filter(AudioFile.id == audio_id, AudioFile.is_deleted == 0).first()
        if not a:
            raise NotFoundError("音频不存在")

        return AudioResponse(
            id=a.id,
            filename=a.filename,
            file_url=a.file_url,
            book_id=a.book_id,
            book_title=a.book_title,
            page_number=a.page_number,
            page_label=a.page_label or "全文",
            duration=a.duration,
            duration_seconds=a.duration_seconds,
            reader=a.reader,
            status=a.status,
            file_size=a.file_size,
            create_time=a.create_time,
        )

    def create_audio(self, data: AudioCreateRequest) -> AudioResponse:
        """创建音频"""
        # 如果有 book_id，获取书名
        book_title = None
        page_label = "全文"
        if data.book_id:
            from backend.domain.book.models import Book
            book = self.db.query(Book).filter(Book.id == data.book_id, Book.is_deleted == 0).first()
            if book:
                book_title = book.title
        if data.page_number:
            page_label = f"P{data.page_number}"

        audio = AudioFile(
            filename=data.filename,
            file_url=data.file_url,
            book_id=data.book_id,
            book_title=book_title,
            page_number=data.page_number,
            page_label=page_label,
            duration=data.duration,
            duration_seconds=data.duration_seconds,
            reader=data.reader,
            status="linked" if data.book_id else "pending",
            file_size=data.file_size,
        )
        self.db.add(audio)
        self.db.commit()
        self.db.refresh(audio)

        return self.get_audio(audio.id)

    def update_audio(self, audio_id: int, data: AudioUpdateRequest) -> AudioResponse:
        """更新音频"""
        audio = self.db.query(AudioFile).filter(AudioFile.id == audio_id, AudioFile.is_deleted == 0).first()
        if not audio:
            raise NotFoundError("音频不存在")

        if data.filename is not None:
            audio.filename = data.filename
        if data.reader is not None:
            audio.reader = data.reader
        if data.status is not None:
            audio.status = data.status
        if data.book_id is not None:
            audio.book_id = data.book_id
            if data.book_id:
                from backend.domain.book.models import Book
                book = self.db.query(Book).filter(Book.id == data.book_id, Book.is_deleted == 0).first()
                if book:
                    audio.book_title = book.title
                    audio.status = "linked"
        if data.page_number is not None:
            audio.page_number = data.page_number
            audio.page_label = f"P{data.page_number}" if data.page_number else "全文"

        self.db.commit()
        return self.get_audio(audio_id)

    def delete_audio(self, audio_id: int) -> dict:
        """删除音频"""
        audio = self.db.query(AudioFile).filter(AudioFile.id == audio_id, AudioFile.is_deleted == 0).first()
        if not audio:
            raise NotFoundError("音频不存在")

        audio.is_deleted = 1
        self.db.commit()
        return {"success": True, "message": "音频已删除"}

    def _format_duration(self, seconds: int) -> str:
        """格式化时长"""
        if seconds < 60:
            return f"{seconds}s"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}h{minutes}m"
