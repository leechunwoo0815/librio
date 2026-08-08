# tests/unit/test_f024_voice_delete_traversal.py
"""F-024 delete_voice_files 路径穿越回归测试（任意文件删除）

根因：audio_url 三分支直拼路径无 resolve 校验——`../../` 可逃逸 uploads 删除任意文件
（deletion_service 同款防御已存在，file_utils 为同类漏改）。
"""

from backend.common.file_utils import delete_voice_files


class TestF024VoiceDeleteTraversal:
    def test_traversal_blocked(self, tmp_path):
        (tmp_path / "uploads" / "voice").mkdir(parents=True)  # 生产语音目录存在
        victim = tmp_path / "victim.txt"
        victim.write_text("重要文件")
        # 逃逸目标：tmp_path 根下的 victim.txt（uploads 之外）；先正常写一个语音文件占位
        (tmp_path / "uploads" / "voice" / "real.wav").write_bytes(b"x")
        deleted = delete_voice_files(
            ["../../victim.txt", "voice/real.wav"], base_dir=tmp_path
        )
        assert deleted == 0
        assert victim.exists()
        assert (tmp_path / "uploads" / "voice" / "real.wav").exists()

    def test_uploads_prefix_traversal_blocked(self, tmp_path):
        (tmp_path / "uploads" / "voice").mkdir(parents=True)
        victim = tmp_path / "victim.txt"
        victim.write_text("重要文件")
        (tmp_path / "uploads" / "voice" / "real.wav").write_bytes(b"x")
        deleted = delete_voice_files(
            ["uploads/../../victim.txt", "uploads/voice/real.wav"], base_dir=tmp_path
        )
        # 逃逸 URL 被拦（victim 保留）；合法 URL 正常删除（deleted=1）
        assert deleted == 1
        assert victim.exists()
        assert not (tmp_path / "uploads" / "voice" / "real.wav").exists()

    def test_normal_voice_file_deleted(self, tmp_path):
        voice_dir = tmp_path / "uploads" / "voice"
        voice_dir.mkdir(parents=True)
        target = voice_dir / "ok.wav"
        target.write_bytes(b"audio")
        deleted = delete_voice_files(["uploads/voice/ok.wav"], base_dir=tmp_path)
        assert deleted == 1
        assert not target.exists()
