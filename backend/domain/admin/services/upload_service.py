# backend/domain/admin/services/upload_service.py
"""文件上传服务 — 从 AdminService 拆分

负责：
  - 文件扩展名校验
  - 单文件上传
  - 分片上传（保存/合并/查询进度）
"""

import json
import logging
import os
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from backend.common.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


# 上传目录（与原 AdminService 保持一致）
UPLOAD_DIR = Path(__file__).parent.parent.parent.parent.parent / "uploads"
CHUNK_DIR = UPLOAD_DIR / "_chunks"


class UploadService:
    """文件上传服务"""

    ALLOWED_IMAGE_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".bmp",
        ".webp",
    }
    ALLOWED_AUDIO_EXTENSIONS = {
        ".mp3",
        ".m4a",
        ".wav",
    }
    ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS | {".pdf"}

    _MIME_MAGIC: dict[bytes, str] = {
        b"\x89PNG\r\n\x1a\n": "image/png",
        b"\xff\xd8\xff": "image/jpeg",
        b"GIF8": "image/gif",
        b"BM": "image/bmp",
        b"RIFF": "image/webp",
        b"%PDF": "application/pdf",
        b"ID3": "audio/mpeg",
    }

    @staticmethod
    def _detect_mime(data: bytes) -> str:
        for magic, mime in UploadService._MIME_MAGIC.items():
            if data[:len(magic)] == magic:
                return mime
        return "application/octet-stream"

    def validate_file_extension(
        self, filename: str, file_type: str | None = None
    ) -> str:
        """校验文件扩展名，返回小写扩展名

        Args:
            filename: 文件名
            file_type: "image" | "audio" | None(不过滤)
        """
        ext = Path(filename).suffix.lower()
        if file_type == "image":
            allowed = self.ALLOWED_IMAGE_EXTENSIONS
            label = "图片"
        elif file_type == "audio":
            allowed = self.ALLOWED_AUDIO_EXTENSIONS
            label = "音频"
        else:
            allowed = self.ALLOWED_EXTENSIONS
            label = "文件"
        if ext not in allowed:
            raise ValidationError(
                f"不支持的{label}格式: {ext}，允许: {', '.join(sorted(allowed))}"
            )
        return ext

    @staticmethod
    def validate_file_content(data: bytes, filename: str) -> None:
        mime = UploadService._detect_mime(data)
        ext = Path(filename).suffix.lower()
        ext_to_mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".webp": "image/webp",
            ".pdf": "application/pdf",
            ".mp3": "audio/mpeg",
        }
        expected = ext_to_mime.get(ext)
        if expected and mime != expected:
            raise ValidationError(f"文件内容与扩展名不匹配，疑似伪造文件: {filename}")

    def save_upload(self, filename: str, content: bytes) -> dict:
        """保存上传文件并返回文件信息"""
        if len(content) > 10 * 1024 * 1024:
            raise ValidationError("单文件上传限制 10MB，请使用分片上传")

        self.validate_file_content(content, filename)

        import uuid as _uuid

        safe_name = f"{_uuid.uuid4().hex[:12]}_{os.path.basename(filename)}"
        save_path = UPLOAD_DIR / safe_name
        save_path.write_bytes(content)

        return {
            "success": True,
            "filename": safe_name,
            "original_name": os.path.basename(filename),
            "size": len(content),
            "url": f"/uploads/{safe_name}",
        }

    def save_chunk(
        self,
        upload_id: str,
        chunk_index: int,
        total_chunks: int,
        filename: str,
        content: bytes,
    ) -> dict:
        """保存分片"""
        # 校验扩展名（仅校验，内容交给 complete_upload 做魔数检测）
        ext = Path(filename).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"不支持的格式: {ext}，允许: {', '.join(sorted(self.ALLOWED_EXTENSIONS))}"
            )
        session_dir = CHUNK_DIR / upload_id
        session_dir.mkdir(exist_ok=True)

        chunk_path = session_dir / f"chunk_{chunk_index:06d}"
        chunk_path.write_bytes(content)

        # 记录元信息
        meta_path = session_dir / "meta.json"
        meta = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
        meta["filename"] = os.path.basename(filename)
        meta["total_chunks"] = total_chunks
        meta["uploaded_chunks"] = list(
            set(meta.get("uploaded_chunks", []) + [chunk_index])
        )
        meta_path.write_text(json.dumps(meta))

        return {
            "success": True,
            "upload_id": upload_id,
            "chunk_index": chunk_index,
            "uploaded": len(meta["uploaded_chunks"]),
            "total": total_chunks,
        }

    def complete_upload(self, upload_id: str) -> dict:
        """合并分片，完成上传"""
        import uuid as _uuid

        session_dir = CHUNK_DIR / upload_id
        meta_path = session_dir / "meta.json"

        if not meta_path.exists():
            raise NotFoundError("上传会话不存在")

        meta = json.loads(meta_path.read_text())
        filename = meta["filename"]
        total_chunks = meta["total_chunks"]
        uploaded = meta.get("uploaded_chunks", [])

        # 检查所有分片是否齐全
        missing = [i for i in range(total_chunks) if i not in uploaded]
        if missing:
            raise ValidationError(f"缺少分片: {missing}，请重新上传缺失分片")

        # 合并分片
        safe_name = f"{_uuid.uuid4().hex[:12]}_{os.path.basename(filename)}"
        save_path = UPLOAD_DIR / safe_name

        with open(save_path, "wb") as f:
            for i in range(total_chunks):
                chunk_path = session_dir / f"chunk_{i:06d}"
                f.write(chunk_path.read_bytes())

        # 魔数校验合并后的文件
        head = save_path.read_bytes()[:32]
        try:
            self.validate_file_content(head, filename)
        except ValidationError:
            save_path.unlink(missing_ok=True)
            raise

        # 清理分片临时文件
        shutil.rmtree(session_dir, ignore_errors=True)

        file_size = save_path.stat().st_size

        return {
            "success": True,
            "filename": safe_name,
            "original_name": os.path.basename(filename),
            "size": file_size,
            "url": f"/uploads/{safe_name}",
            "chunks_merged": total_chunks,
        }

    def get_upload_status(self, upload_id: str) -> dict:
        """查询分片上传进度"""
        session_dir = CHUNK_DIR / upload_id
        meta_path = session_dir / "meta.json"

        if not meta_path.exists():
            return {"exists": False, "uploaded_chunks": [], "total_chunks": 0}

        meta = json.loads(meta_path.read_text())
        return {
            "exists": True,
            "upload_id": upload_id,
            "filename": meta.get("filename"),
            "total_chunks": meta.get("total_chunks", 0),
            "uploaded_chunks": meta.get("uploaded_chunks", []),
            "progress": len(meta.get("uploaded_chunks", []))
            / max(meta.get("total_chunks", 1), 1)
            * 100,
        }


class AdminUploadService:
    """管理端上传服务入口 — 委托给 UploadService。

    保留该薄封装，使 admin router 的依赖注入风格与 AdminXxxService 保持一致。
    """

    def __init__(self, db: Session | None = None):
        self._upload_service = UploadService()

    def validate_file_extension(
        self, filename: str, file_type: str | None = None
    ) -> str:
        return self._upload_service.validate_file_extension(filename, file_type)

    def save_upload(self, filename: str, content: bytes) -> dict:
        return self._upload_service.save_upload(filename, content)

    def save_chunk(
        self,
        upload_id: str,
        chunk_index: int,
        total_chunks: int,
        filename: str,
        content: bytes,
    ) -> dict:
        return self._upload_service.save_chunk(
            upload_id, chunk_index, total_chunks, filename, content
        )

    def complete_upload(self, upload_id: str) -> dict:
        return self._upload_service.complete_upload(upload_id)

    def get_upload_status(self, upload_id: str) -> dict:
        return self._upload_service.get_upload_status(upload_id)
