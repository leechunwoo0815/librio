"""
F-022 终审闭环守护：except 块内的 logger.error 必须带 exc_info。

用 AST 全库扫描（而非字符串匹配），只约束"异常处理器内"的 logger.error——
业务失败分支（无活动异常，如短信网关业务错误）不要求 exc_info。
"""

import ast
from pathlib import Path


def _iter_backend_py():
    root = Path(__file__).resolve().parents[2] / "backend"
    for path in sorted(root.rglob("*.py")):
        if "alembic" in path.parts or "migrations" in path.parts:
            continue
        yield path


def _is_logger_error_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "error"
    )


def _check_except_logger_errors(tree: ast.AST, path: str) -> list[str]:
    """except 块内 logger.error 必须 exc_info=True（真值检查，exc_info=False 视为违规）"""
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        for sub in ast.walk(node):
            if not _is_logger_error_call(sub):
                continue
            kwargs = {kw.arg: kw.value for kw in sub.keywords if kw.arg}
            exc = kwargs.get("exc_info")
            if not (isinstance(exc, ast.Constant) and exc.value is True):
                violations.append(f"{path}:{getattr(sub, 'lineno', '?')}")
    return violations


def test_every_logger_error_inside_except_has_exc_info():
    violations = []
    for path in _iter_backend_py():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(_check_except_logger_errors(tree, str(path)))
    assert not violations, "except 块内 logger.error 缺 exc_info=True：\n" + "\n".join(
        violations
    )


def test_guard_rejects_exc_info_false():
    """自验证：exc_info=False 必须被判违规（防守护退化回'仅查 key 存在'）"""
    tree = ast.parse(
        """\
try:
    pass
except Exception:
    logger.error("boom", exc_info=False)
"""
    )
    assert _check_except_logger_errors(tree, "synthetic"), "exc_info=False 必须报违规"


def test_guard_accepts_exc_info_true():
    tree = ast.parse(
        """\
try:
    pass
except Exception:
    logger.error("boom", exc_info=True)
"""
    )
    assert not _check_except_logger_errors(tree, "synthetic")
