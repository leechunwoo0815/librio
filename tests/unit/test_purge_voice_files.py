"""tests/unit/test_purge_voice_files.py

验证 purge_soft_deleted.py 修正3：voice_recording 物理删除时
同步删除音频文件，且调用顺序正确（DELETE 前收集 url，DELETE 后删文件）。
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.database import Base

# 导入所有模型确保 create_all 覆盖全部表
import backend.domain.user.models  # noqa: F401
import backend.domain.child.models  # noqa: F401
import backend.domain.voice.models  # noqa: F401
import backend.domain.admin.models  # noqa: F401
import backend.domain.admin.rbac_models  # noqa: F401
import backend.domain.book.models  # noqa: F401
import backend.domain.book.damage_model  # noqa: F401
import backend.common.dead_letter_model  # noqa: F401
import backend.common.config_audit_model  # noqa: F401


@pytest.fixture
def purge_engine(tmp_path):
    """SQLite 内存引擎 + 临时 uploads/voice 目录。"""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)

    voice_dir = tmp_path / "uploads" / "voice"
    voice_dir.mkdir(parents=True)

    # 创建 2 个假音频文件（对应软删除+过期的记录）
    (voice_dir / "audio_001.wav").write_bytes(b"fake audio 001")
    (voice_dir / "audio_002.wav").write_bytes(b"fake audio 002")

    yield engine, tmp_path, voice_dir

    Base.metadata.drop_all(bind=engine)


def _insert_voice_data(engine, days_old=200):
    """插入测试 voice_recording 数据，返回 cutoff datetime。"""
    Session = sessionmaker(bind=engine)
    session = Session()

    cutoff = datetime.now() - timedelta(days=days_old)
    # create_time 比 cutoff 更早 1 天，确保被 < cutoff 查到
    old_time = cutoff - timedelta(days=1)

    # 2 条软删除+过期的记录
    session.execute(
        text(
            "INSERT INTO voice_recording (id, child_id, book_id, page_id, text_content, "
            "audio_url, duration_seconds, is_deleted, create_time, update_time) "
            "VALUES (1, 1, 1, 1, 'text', 'uploads/voice/audio_001.wav', 30, 1, :t, :t)"
        ),
        {"t": old_time},
    )

    session.execute(
        text(
            "INSERT INTO voice_recording (id, child_id, book_id, page_id, text_content, "
            "audio_url, duration_seconds, is_deleted, create_time, update_time) "
            "VALUES (2, 1, 1, 1, 'text', 'uploads/voice/audio_002.wav', 45, 1, :t, :t)"
        ),
        {"t": old_time},
    )

    # 1 条未软删除的记录（不应被清理）
    recent = datetime.now() - timedelta(days=10)
    session.execute(
        text(
            "INSERT INTO voice_recording (id, child_id, book_id, page_id, text_content, "
            "audio_url, duration_seconds, is_deleted, create_time, update_time) "
            "VALUES (3, 1, 1, 1, 'text', 'uploads/voice/audio_003.wav', 20, 0, :r, :r)"
        ),
        {"r": recent},
    )

    session.commit()
    session.close()
    return cutoff


class TestPurgeVoiceFiles:
    """测试 purge 脚本的 voice 文件同步删除逻辑。"""

    def test_collect_before_delete(self, purge_engine, monkeypatch):
        """修正3 核心：collect_voice_files 在 DELETE 之前调用，能查到 audio_url。"""
        engine, tmp_path, voice_dir = purge_engine
        cutoff = _insert_voice_data(engine)

        import scripts.purge_soft_deleted as purge_mod

        monkeypatch.setattr(purge_mod, "PROJECT_DIR", tmp_path)

        # 1. DELETE 之前收集 audio_url
        urls = purge_mod.collect_voice_files(engine, cutoff)
        assert len(urls) == 2
        assert "uploads/voice/audio_001.wav" in urls
        assert "uploads/voice/audio_002.wav" in urls

        # 2. 音频文件存在
        assert (voice_dir / "audio_001.wav").exists()
        assert (voice_dir / "audio_002.wav").exists()

        # 3. DELETE 行
        with engine.connect() as conn:
            conn.execute(
                text(
                    "DELETE FROM voice_recording WHERE is_deleted=1 AND create_time < :c"
                ),
                {"c": cutoff},
            )
            conn.commit()

        # 4. DELETE 之后按列表删文件
        deleted = purge_mod.delete_voice_files(urls)
        assert deleted == 2

        # 5. 文件已删除
        assert not (voice_dir / "audio_001.wav").exists()
        assert not (voice_dir / "audio_002.wav").exists()

    def test_collect_after_delete_returns_empty(self, purge_engine, monkeypatch):
        """反面测试：DELETE 之后才 collect，查不到任何 url（验证旧 bug 模式）。"""
        engine, tmp_path, voice_dir = purge_engine
        cutoff = _insert_voice_data(engine)

        import scripts.purge_soft_deleted as purge_mod

        monkeypatch.setattr(purge_mod, "PROJECT_DIR", tmp_path)

        # 先 DELETE
        with engine.connect() as conn:
            conn.execute(
                text(
                    "DELETE FROM voice_recording WHERE is_deleted=1 AND create_time < :c"
                ),
                {"c": cutoff},
            )
            conn.commit()

        # DELETE 之后再 collect —— 应返回空（旧 bug 的行为）
        urls = purge_mod.collect_voice_files(engine, cutoff)
        assert len(urls) == 0

        # 文件仍在（因为没收集到 url）
        assert (voice_dir / "audio_001.wav").exists()

    def test_unsoft_deleted_not_purged(self, purge_engine, monkeypatch):
        """未软删除的 voice_recording 不受影响。"""
        engine, tmp_path, voice_dir = purge_engine
        cutoff = _insert_voice_data(engine)

        import scripts.purge_soft_deleted as purge_mod

        monkeypatch.setattr(purge_mod, "PROJECT_DIR", tmp_path)

        # 创建第 3 个文件
        (voice_dir / "audio_003.wav").write_bytes(b"keep me")

        urls = purge_mod.collect_voice_files(engine, cutoff)
        assert len(urls) == 2
        assert "uploads/voice/audio_003.wav" not in urls

        purge_mod.delete_voice_files(urls)
        assert (voice_dir / "audio_003.wav").exists()

    def test_remote_url_skipped(self, purge_engine, monkeypatch):
        """远程 URL (http) 跳过本地文件删除。"""
        engine, tmp_path, voice_dir = purge_engine

        import scripts.purge_soft_deleted as purge_mod

        monkeypatch.setattr(purge_mod, "PROJECT_DIR", tmp_path)

        (voice_dir / "local.wav").write_bytes(b"local")

        urls = [
            "uploads/voice/local.wav",
            "https://oss.example.com/remote.wav",
            "http://cdn.example.com/another.wav",
        ]

        deleted = purge_mod.delete_voice_files(urls)
        assert deleted == 1, "只有本地文件被删除，远程 URL 跳过"
