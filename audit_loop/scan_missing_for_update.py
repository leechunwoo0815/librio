"""循环审查维度 1.2 辅助脚本：定位"先查后改"但查询未加 with_for_update() 的路径。

审查指令：无限循环审查指令-opencode.md §四 维度 1.2
规则：
- 函数内若存在 db.query(...)...first()/one()/all()（无 with_for_update），且结果对象
  后续被属性赋值（obj.field = x），则列为可疑（可能缺行锁）。
- 只报不修；输出用于人工核对。SQLite 下行锁为 no-op，结论需 MySQL 实证。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = [ROOT / "backend" / "domain"]
SKIP_DIRS = {"__pycache__"}

QUERY_RE = re.compile(r"\b(db|self\.db)\.query\(.*?\)\.filter\(.*?\.(first|one|all)\(\)")
FOR_UPDATE_RE = re.compile(r"with_for_update")
ATTR_ASSIGN_RE = re.compile(r"^\s{4,}(\w+)\.([a-zA-Z_]\w*)\s*=")

# 通过 db 直连查询返回的变量名（保守：仅 first/one，all 列表不跟踪）
RESULT_CALLS = re.compile(r"(\w+)\s*=\s*(self\.)?db\.query\(.*?\)\.filter\(.*?\.(first|one)\(\)")


def scan_file(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    findings = []
    cur_func = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("def ", "async def ")):
            cur_func = stripped[:60]
        if "with_for_update" in line or "db.query" not in line:
            continue
        m = RESULT_CALLS.search(line)
        if not m:
            continue
        var = m.group(1)
        # 该函数内该变量后续是否被属性赋值
        for j in range(i + 1, min(i + 60, len(lines))):
            lj = lines[j]
            if lj.strip().startswith(("def ", "async def ")):
                break
            am = ATTR_ASSIGN_RE.match(lj)
            if am and am.group(1) == var:
                findings.append(
                    {
                        "query_line": i + 1,
                        "assign_line": j + 1,
                        "func": cur_func or "?",
                        "var": var,
                        "assign": lj.strip()[:100],
                    }
                )
                break
    return findings


def main() -> int:
    total = 0
    for d in SCAN_DIRS:
        if not d.exists():
            continue
        for f in sorted(d.rglob("service.py")):
            if any(s in f.parts for s in SKIP_DIRS):
                continue
            hits = scan_file(f)
            if hits:
                rel = f.relative_to(ROOT)
                for h in hits:
                    print(
                        f"{rel}:{h['query_line']} 查询 {h['var']}(无锁) -> "
                        f"L{h['assign_line']} 赋值: {h['assign']}  [func: {h['func']}]"
                    )
                    total += 1
    print(f"\nTOTAL suspicious: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
