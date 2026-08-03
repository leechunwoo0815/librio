# backend/common/file_utils.py
"""本地文件工具 — 语音录音等上传文件的物理删除"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent


def delete_voice_files(audio_urls: list[str], base_dir: Path | None = None) -> int:
    """根据 audio_url 列表删除本地音频文件。

    audio_url 可能是相对路径 (uploads/voice/xxx.wav)、绝对路径 (/uploads/...)
    或远程 URL（http 开头，跳过）。base_dir 供测试注入。
    """
    root = base_dir or PROJECT_DIR
    deleted_count = 0
    for audio_url in audio_urls:
        if audio_url.startswith("uploads/"):
            file_path = root / audio_url
        elif audio_url.startswith("/uploads/"):
            file_path = root / audio_url[1:]
        elif audio_url.startswith("http"):
            continue  # 远程 URL，跳过本地文件删除
        else:
            file_path = root / "uploads" / "voice" / audio_url

        if file_path.exists():
            file_path.unlink()
            deleted_count += 1

    return deleted_count
