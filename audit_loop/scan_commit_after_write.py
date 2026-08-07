"""循环审查维度 1.1 辅助脚本：定位 commit() 之后的写操作（静态扫描）。

审查指令：无限循环审查指令-opencode.md §四 维度 1.1
规则：
- 在 commit() 之后、下一个 commit()/函数定义之前，若出现写操作
  （db.add / db.delete / db.execute / 属性赋值），则列为可疑点。
- 只报不修；输出用于人工核对。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = [ROOT / "backend" / "domain", ROOT / "backend" / "admin"]
SKIP_DIRS = {"__pycache__"}

WRITE_PATTERNS = [
    (r"\bdb\.add\(", "db.add("),
    (r"\bdb\.delete\(", "db.delete("),
    (r"\bdb\.execute\(", "db.execute("),
    (r"\bdb\.bulk_", "db.bulk_*"),
]
ATTR_ASSIGN = re.compile(r"^\s{4,}\w[\w.]*\.[a-zA-Z_]\w*\s*=")  # obj.field = xxx


def scan_file(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    findings = []
    for i, line in enumerate(lines):
        if ".commit()" not in line:
            continue
        # 从 commit 行后开始，扫到下一个 commit / def / return 为止
        for j in range(i + 1, min(i + 40, len(lines))):
            lj = lines[j]
            if ".commit()" in lj or lj.strip().startswith(("def ", "async def ")):
                break
            # 首个 return（含紧邻 commit 的 return）即截断，避免跨 if 分支误报
            if lj.strip().startswith(("return ", "raise ")):
                break
            for pattern, label in WRITE_PATTERNS:
                if re.search(pattern, lj):
                    findings.append(
                        {
                            "commit_line": i + 1,
                            "write_line": j + 1,
                            "kind": label,
                            "text": lj.strip()[:120],
                        }
                    )
                    break
            else:
                if ATTR_ASSIGN.match(lj):
                    findings.append(
                        {
                            "commit_line": i + 1,
                            "write_line": j + 1,
                            "kind": "attr-assign",
                            "text": lj.strip()[:120],
                        }
                    )
    return findings


def main() -> int:
    total = 0
    for d in SCAN_DIRS:
        if not d.exists():
            continue
        for f in sorted(d.rglob("*.py")):
            if any(s in f.parts for s in SKIP_DIRS):
                continue
            hits = scan_file(f)
            if hits:
                rel = f.relative_to(ROOT)
                for h in hits:
                    print(
                        f"{rel}:{h['commit_line']} commit -> "
                        f"L{h['write_line']} {h['kind']}: {h['text']}"
                    )
                    total += 1
    print(f"\nTOTAL suspicious: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
