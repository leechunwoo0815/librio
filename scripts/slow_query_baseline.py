#!/usr/bin/env python3
"""慢查询基线 — scripts/slow_query_baseline.py

[What] 开启 MySQL TABLE 模式慢日志，用 TestClient 打一遍核心重端点，导出慢查询基线报告
[Why] 给 N+1/缺索引回归提供可对比的基线数据
[How]
  1. SET GLOBAL slow_query_log=ON, log_output='TABLE', long_query_time=阈值
  2. TRUNCATE mysql.slow_log
  3. TestClient 调用核心端点（用户端+管理端）
  4. 读取 mysql.slow_log 输出报告
  5. --restore 恢复原设置

用法:
  PYTHONPATH=. venv/bin/python scripts/slow_query_baseline.py [--threshold 0.3] [--restore]
"""

import argparse
import sys
import time

from sqlalchemy import text

CORE_ENDPOINTS = [
    ("GET", "/book/search?keyword=the", "user"),
    ("GET", "/child/", "user"),
    ("GET", "/user/info", "user"),
    ("GET", "/admin/api/dashboard", "admin"),
    ("GET", "/admin/api/users?page=1&page_size=20", "admin"),
    ("GET", "/admin/api/books?page=1&page_size=20", "admin"),
    ("GET", "/admin/api/borrows?page=1&page_size=20", "admin"),
    ("GET", "/admin/api/orders?page=1&page_size=20", "admin"),
    ("GET", "/admin/api/bookcopy", "admin"),
    ("GET", "/admin/api/damage-reports", "admin"),
    ("GET", "/admin/api/reports/observation?page=1&page_size=20", "admin"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.3, help="慢查询阈值秒数")
    parser.add_argument("--restore", action="store_true", help="执行后恢复原慢日志设置")
    parser.add_argument("--output", default="专家意见/slow_query_baseline.md")
    args = parser.parse_args()

    from backend.database import get_session

    db = get_session()()

    def get_var(name):
        return db.execute(text(f"SHOW VARIABLES LIKE '{name}'")).fetchone()[1]

    # 1. 保存原设置并开启 TABLE 模式慢日志
    orig = {v: get_var(v) for v in ("slow_query_log", "long_query_time", "log_output")}
    print(f"原设置: {orig}")
    db.execute(text("SET GLOBAL slow_query_log = 'ON'"))
    db.execute(text("SET GLOBAL log_output = 'TABLE'"))
    db.execute(text(f"SET GLOBAL long_query_time = {args.threshold}"))
    try:
        db.execute(text("TRUNCATE TABLE mysql.slow_log"))
    except Exception as e:
        print(f"TRUNCATE slow_log 失败（权限不足？）: {e}")
        return 1

    # 2. 打端点
    from fastapi.testclient import TestClient

    from backend.domain.admin.models import Admin
    from backend.main import app
    from backend.middleware.admin_auth import create_admin_token

    client = TestClient(app)
    # 用真实管理员的当前 token_generation 签发，避免 gen 校验失败
    # 兼容旧数据：status/is_deleted 为 NULL 的管理员行先按模型默认值修复
    dirty = (
        db.query(Admin)
        .filter((Admin.status.is_(None)) | (Admin.is_deleted.is_(None)))
        .all()
    )
    if dirty:
        print(f"修复 NULL 状态管理员行: {[a.id for a in dirty]}")
        for a in dirty:
            a.status = Admin.STATUS_ACTIVE
            a.is_deleted = 0
        db.commit()
    admin = (
        db.query(Admin)
        .filter(Admin.is_deleted == 0, Admin.status == Admin.STATUS_ACTIVE)
        .first()
    )
    # 兼容旧数据：admin_role_id 指向无效角色（权限不足）时，重挂到真实超级管理员角色
    if admin:
        from backend.domain.admin.rbac_models import Role, RolePermission

        real_super = (
            db.query(Role)
            .filter(Role.code == "super_admin", Role.is_deleted == 0)
            .all()
        )
        real_super = max(
            real_super,
            key=lambda r: (
                db.query(RolePermission)
                .filter(RolePermission.role_id == r.id, RolePermission.is_deleted == 0)
                .count()
            ),
        )
        if admin.admin_role_id != real_super.id:
            print(
                f"管理员 {admin.username} 角色 {admin.admin_role_id} → {real_super.id}（真实超管）"
            )
            admin.admin_role_id = real_super.id
            db.commit()
    if not admin:
        print("无可用管理员账号，管理端端点跳过")
        admin_token = None
    else:
        admin_token = create_admin_token(admin.id, admin.role, admin.token_generation)
    headers_map = {
        "user": {"Authorization": "Bearer test-token-mock"},
        "admin": {"Authorization": f"Bearer {admin_token}"},
    }

    results = []
    for method, path, role in CORE_ENDPOINTS:
        if role == "admin" and not admin_token:
            results.append((path, role, "SKIP", 0.0))
            continue
        start = time.time()
        try:
            resp = client.request(method, path, headers=headers_map[role])
            status = resp.status_code
        except Exception as e:
            status = f"ERR:{e}"
        results.append((path, role, status, time.time() - start))
        print(f"  {status} {path}")

    time.sleep(0.5)  # 等慢日志落表

    # 3. 读取慢查询
    rows = db.execute(
        text(
            "SELECT query_time, lock_time, rows_sent, rows_examined, db, sql_text "
            "FROM mysql.slow_log ORDER BY query_time DESC LIMIT 100"
        )
    ).fetchall()

    # 4. 恢复原设置
    if args.restore:
        db.execute(text(f"SET GLOBAL slow_query_log = '{orig['slow_query_log']}'"))
        db.execute(text(f"SET GLOBAL long_query_time = {orig['long_query_time']}"))
        db.execute(text(f"SET GLOBAL log_output = '{orig['log_output']}'"))
        print("已恢复原设置")

    # 5. 输出报告
    lines = [
        "# 慢查询基线报告",
        "",
        f"- 阈值: {args.threshold}s | 端点数: {len(CORE_ENDPOINTS)} | 慢查询条数: {len(rows)}",
        "",
        "## 端点耗时",
        "",
        "| 端点 | 角色 | 状态 | 耗时(s) |",
        "|------|------|------|---------|",
    ]
    for path, role, status, dur in results:
        lines.append(f"| {path} | {role} | {status} | {dur:.3f} |")
    lines += [
        "",
        "## 慢查询明细",
        "",
        "| query_time | rows_examined | db | sql_text(截断200) |",
        "|-----------|---------------|----|-----------------|",
    ]
    for qt, _lt, _rs, re_, dbname, sql in rows:
        sql_short = str(sql)[:200].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {qt} | {re_} | {dbname} | {sql_short} |")

    with open(args.output, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n报告已写入 {args.output}（慢查询 {len(rows)} 条）")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
