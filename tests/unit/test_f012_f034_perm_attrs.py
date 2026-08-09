"""F-012/F-034 终审闭环守护（前端静态断言）：data-perm 必须与后端权限码一致"""

from pathlib import Path


def _read(relative: str) -> str:
    root = Path(__file__).resolve().parents[2] / "backend" / "static" / "admin"
    path = root / relative
    assert path.exists(), f"文件不存在: {path}"
    return path.read_text(encoding="utf-8")


def test_content_js_page_edit_uses_book_edit():
    """编辑页面（PUT pages 后端要求 book.edit）前端 data-perm 必须一致"""
    source = _read("js/pages/content.js")
    assert 'data-perm="book.edit" data-action="edit-page"' in source
    assert 'data-perm="content.edit" data-action="edit-page"' not in source


def test_content_js_audio_delete_uses_content_delete():
    """删除音频（后端 DELETE /audio 要求 content.delete）前端 data-perm 必须一致"""
    source = _read("js/pages/content.js")
    assert 'data-perm="content.delete" data-action="delete-audio"' in source
    assert 'data-perm="content.edit" data-action="delete-audio"' not in source


def test_audio_js_delete_button_has_perm():
    """音频管理页删除按钮必须有 data-perm（此前漏标 → 有权限的按钮所有人可见）"""
    source = _read("js/pages/audio.js")
    assert 'data-perm="content.delete" data-action="delete-audio"' in source
