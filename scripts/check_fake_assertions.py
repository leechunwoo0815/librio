#!/usr/bin/env python3
"""CI 检查脚本：禁止无注释的 assert True 假绿断言

behave 不支持 pytest.skip，前端交互步骤保留 assert True 但必须有注释说明原因。
"""
import pathlib
import sys

violations = []
for py_file in pathlib.Path("features/steps").rglob("*.py"):
    for i, line in enumerate(py_file.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # assert True 必须有注释说明原因
        if stripped == "assert True":
            violations.append(f"{py_file}:{i}: bare assert True (no comment)")
        elif stripped.startswith("assert True") and "#" not in stripped and "\"" not in stripped and "'" not in stripped:
            violations.append(f"{py_file}:{i}: assert True without explanation")

if violations:
    print(f"FOUND {len(violations)} unexplained assert True:")
    for v in violations:
        print(f"  {v}")
    sys.exit(1)
print("OK: all assert True have explanations")
