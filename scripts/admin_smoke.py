#!/usr/bin/env python3
"""管理端+用户端冒烟检查 — scripts/admin_smoke.py

[What] TestClient 级冒烟：覆盖浏览器验证清单（分页/加载/按钮对应端点）
[Why] 无浏览器条件下的可重复验证手段，替代"人工浏览器点一遍"
[How] 真实管理员 token 打管理端核心端点 + consent 链路，全部 200/预期码即通过

用法:
  MOCK_PAYMENT=true MOCK_SMS=true DEBUG=true ENABLE_TEST_TOKEN=true \
    PYTHONPATH=. venv/bin/python scripts/admin_smoke.py
"""

import sys

from fastapi.testclient import TestClient


def main() -> int:
    from backend.database import get_session
    from backend.domain.admin.models import Admin
    from backend.main import app
    from backend.middleware.admin_auth import create_admin_token

    db = get_session()()
    admin = (
        db.query(Admin)
        .filter(Admin.is_deleted == 0, Admin.status == Admin.STATUS_ACTIVE)
        .first()
    )
    if not admin:
        print("FAIL: 无可用管理员")
        return 1
    token = create_admin_token(admin.id, admin.role, admin.token_generation)
    client = TestClient(app, raise_server_exceptions=False)
    AH = {"Authorization": f"Bearer {token}"}
    UH = {"Authorization": "Bearer test-token-mock"}

    failures = 0

    def check(name, condition, detail=""):
        nonlocal failures
        mark = "✅" if condition else "❌"
        if not condition:
            failures += 1
        print(f"{mark} {name} {detail}")

    # ── 浏览器验证清单对应端点 ──
    for name, path in [
        ("图书分页", "/admin/api/books?page=2&page_size=5"),
        ("词库搜索", "/admin/api/dictionary/search?page=1&page_size=5"),
        ("测验题目", "/admin/api/advancement/questions"),
        ("测验实例", "/admin/api/advancement/quizzes"),
        ("押金列表", "/admin/api/deposits"),
        ("预约列表", "/admin/api/reservations"),
        ("消息分页", "/admin/api/messages?page=1&page_size=5"),
        ("活动列表", "/admin/api/activities"),
        ("损坏定责", "/admin/api/damage-reports"),
        ("仪表盘", "/admin/api/dashboard"),
    ]:
        r = client.get(path, headers=AH)
        check(f"{name} {path}", r.status_code == 200, f"({r.status_code})")

    # ── 消息发送（全部用户 + 指定老师）──
    from backend.domain.admin.models import Teacher
    from backend.domain.message.models import SystemMessage, TeacherMessage

    r = client.post(
        "/admin/api/messages/send",
        headers=AH,
        json={"title": "冒烟自净消息", "content": "全部用户", "target": "all"},
    )
    check(
        "消息发全部用户",
        r.status_code == 200 and r.json().get("success"),
        f"({r.status_code})",
    )

    teacher = db.query(Teacher).filter(Teacher.is_deleted == 0).first()
    if teacher:
        r = client.post(
            "/admin/api/messages/send",
            headers=AH,
            json={
                "title": "冒烟自净消息",
                "content": "指定老师",
                "target": "teacher",
                "target_teacher_id": teacher.id,
            },
        )
        check(
            "消息发指定老师",
            r.status_code == 200 and r.json().get("sent_count") == 1,
            f"({r.status_code})",
        )
    else:
        print("⚠ 无老师数据，跳过发老师检查")

    # ── consent 链路（403→同意→201）──
    r = client.get("/user/consent", headers=UH)
    check("GET /user/consent", r.status_code == 200, f"({r.status_code})")

    r = client.post(
        "/child/", headers=UH, json={"name": "冒烟自净娃", "age": 5, "grade": "中班"}
    )
    check(
        "无同意创建孩子 403+consent_required",
        r.status_code == 403 and r.json().get("error_code") == "consent_required",
        f"({r.status_code})",
    )

    r = client.post("/user/consent", headers=UH, json={"consent_type": "child_data"})
    check("POST /user/consent", r.status_code == 201, f"({r.status_code})")

    r = client.post(
        "/child/", headers=UH, json={"name": "冒烟自净娃", "age": 5, "grade": "中班"}
    )
    check("同意后创建孩子 201", r.status_code == 201, f"({r.status_code})")

    # ── 清理冒烟数据 ──
    from backend.domain.child.models import Child
    from backend.domain.user.consent_model import ConsentRecord

    db.query(Child).filter(Child.name == "冒烟自净娃").delete()
    db.query(ConsentRecord).filter(
        ConsentRecord.user_id == 1, ConsentRecord.consent_type == "child_data"
    ).delete()
    db.query(SystemMessage).filter(SystemMessage.title == "冒烟自净消息").delete()
    db.query(TeacherMessage).filter(TeacherMessage.title == "冒烟自净消息").delete()
    db.commit()
    db.close()

    print(f"\n{'全部通过 ✅' if failures == 0 else f'{failures} 项失败 ❌'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
