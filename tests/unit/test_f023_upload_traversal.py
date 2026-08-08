# tests/unit/test_f023_upload_traversal.py
"""F-023 分片上传路径遍历回归测试（P2 四层防御）

根因：upload_id 无格式校验，直拼 CHUNK_DIR / upload_id → `../../` 逃逸可任意写文件。
防御：① router 参数 pattern ② service session_dir resolve+前缀校验 ③ 分片参数上限
④ 单分片 ≤10MB。
"""

import pytest

from backend.common.exceptions import ValidationError
from backend.domain.admin.services.upload_service import UploadService


class TestF023UploadTraversal:
    def test_traversal_upload_id_rejected(self, monkeypatch, tmp_path):
        """upload_id=../../escape → ValidationError，且不得在 CHUNK_DIR 外创建文件"""
        chunks = tmp_path / "_chunks"
        chunks.mkdir()
        monkeypatch.setattr(
            "backend.domain.admin.services.upload_service.CHUNK_DIR", chunks
        )
        svc = UploadService()
        with pytest.raises(ValidationError, match="非法上传会话"):
            svc.save_chunk("../../escape", 0, 1, "a.pdf", b"x")
        assert not (tmp_path / "escape").exists()

    def test_oversize_chunk_rejected(self, monkeypatch, tmp_path):
        chunks = tmp_path / "_chunks"
        chunks.mkdir()
        monkeypatch.setattr(
            "backend.domain.admin.services.upload_service.CHUNK_DIR", chunks
        )
        svc = UploadService()
        with pytest.raises(ValidationError, match="10MB"):
            svc.save_chunk(
                "valid-upload-id-0001", 0, 1, "a.pdf", b"x" * (10 * 1024 * 1024 + 1)
            )

    def test_normal_upload_works(self, monkeypatch, tmp_path):
        chunks = tmp_path / "_chunks"
        chunks.mkdir()
        monkeypatch.setattr(
            "backend.domain.admin.services.upload_service.CHUNK_DIR", chunks
        )
        svc = UploadService()
        result = svc.save_chunk("valid-upload-id-0001", 0, 1, "a.pdf", b"hello")
        assert result["success"] is True
        assert (chunks / "valid-upload-id-0001" / "chunk_000000").exists()
