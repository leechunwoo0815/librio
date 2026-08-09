"""
F-011 终审闭环守护（前端静态断言）：
quiz 页 onUnload 必须销毁 TTS 音频上下文（F-057 修复时一并补齐）。
无浏览器环境，以源码静态断言兜底，标注"需前端真机验证"。
"""

from pathlib import Path


def _quiz_js() -> str:
    root = Path(__file__).resolve().parents[2] / "frontend"
    path = root / "pages" / "reading-pkg" / "quiz" / "quiz.js"
    assert path.exists(), f"quiz.js 不存在: {path}"
    return path.read_text(encoding="utf-8")


def test_quiz_onunload_destroys_tts_context():
    source = _quiz_js()
    onunload = source.split("onUnload() {", 1)[1].split("},", 1)[0]
    assert "_ttsCtx" in onunload
    assert "destroy()" in onunload


def test_quiz_never_reads_correct_answer_locally():
    """F-057：前端不得再依赖取题接口的 correct_answer 做本地判分"""
    source = _quiz_js()
    assert "_correctAnswers" not in source
    assert "q.correct_answer" not in source
