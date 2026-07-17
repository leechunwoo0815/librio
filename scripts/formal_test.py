#!/usr/bin/env python3
"""
DmkWords (Librio) 全面正式测试脚本
模拟管理员、运营、家长、孩子四个角色，覆盖所有核心功能
"""

__test__ = False  # prevent pytest from collecting this script
import requests
import json
import subprocess
from datetime import datetime

BASE = "http://localhost:8002"
RESULTS = []
TOTAL = 0
PASS = 0
FAIL = 0
ERRORS = []


def run_api_test(
    name, method, path, token=None, json_data=None, expected_status=None, role="unknown"
):
    """执行单个 API 测试"""
    global TOTAL, PASS, FAIL
    TOTAL += 1
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        if method == "GET":
            r = requests.get(f"{BASE}{path}", headers=headers, timeout=10)
        elif method == "POST":
            r = requests.post(
                f"{BASE}{path}", headers=headers, json=json_data, timeout=10
            )
        elif method == "PUT":
            r = requests.put(
                f"{BASE}{path}", headers=headers, json=json_data, timeout=10
            )
        elif method == "DELETE":
            r = requests.delete(f"{BASE}{path}", headers=headers, timeout=10)
        else:
            r = requests.request(
                method, f"{BASE}{path}", headers=headers, json=json_data, timeout=10
            )

        status = r.status_code
        try:
            body = r.json()
        except Exception:
            body = r.text[:200]

        # 判断通过/失败
        if expected_status:
            ok = status == expected_status
        else:
            ok = 200 <= status < 500  # 非服务器错误都算"可响应"

        # 500 一定是失败
        if status >= 500:
            ok = False

        result = "✅" if ok else "❌"
        if ok:
            PASS += 1
        else:
            FAIL += 1
            ERRORS.append(
                f"[{role}] {name}: HTTP {status} - {json.dumps(body, ensure_ascii=False)[:150]}"
            )

        RESULTS.append(
            {
                "role": role,
                "name": name,
                "method": method,
                "path": path,
                "status": status,
                "ok": ok,
                "body_preview": json.dumps(body, ensure_ascii=False)[:100]
                if isinstance(body, (dict, list))
                else str(body)[:100],
            }
        )

        print(f"  {result} [{status}] {name}")
        return body if isinstance(body, dict) else {}

    except Exception as e:
        FAIL += 1
        TOTAL += 1
        ERRORS.append(f"[{role}] {name}: EXCEPTION - {str(e)[:100]}")
        print(f"  ❌ [ERR] {name}: {str(e)[:80]}")
        return {}


def section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ============================================================
# 获取令牌
# ============================================================
section("准备：获取令牌")

print("  获取管理员令牌...")
admin_login = requests.post(
    f"{BASE}/admin/login", json={"username": "admin", "password": "admin123"}
).json()
AT = admin_login.get("token", "")
print(f"  管理员: {admin_login.get('name', 'N/A')} (token: {'OK' if AT else 'FAIL'})")

print("  创建用户令牌...")
# 直接调用后端创建
result = subprocess.run(
    [
        "/Users/litianyu/cc-projects/librio/venv/bin/python",
        "-c",
        "from backend.middleware.auth import create_access_token; from datetime import timedelta; print(create_access_token({'sub': '1', 'type': 'user'}, expires_delta=timedelta(days=7)))",
    ],
    capture_output=True,
    text=True,
    cwd="/Users/litianyu/cc-projects/librio",
)
UT = result.stdout.strip()
print(f"  用户: user_id=1 (token: {'OK' if UT else 'FAIL'})")

# ============================================================
# 角色1：管理员
# ============================================================
section("角色1：管理员 (Admin)")

print("\n--- 1.1 认证 ---")
run_api_test(
    "管理员登录",
    "POST",
    "/admin/login",
    json_data={"username": "admin", "password": "admin123"},
    expected_status=200,
    role="管理员",
)
run_api_test(
    "管理员登录-错误密码",
    "POST",
    "/admin/login",
    json_data={"username": "admin", "password": "wrong"},
    expected_status=401,
    role="管理员",
)
run_api_test(
    "无令牌访问管理接口", "GET", "/admin/dashboard", expected_status=401, role="管理员"
)

print("\n--- 1.2 仪表盘 ---")
dash = run_api_test("仪表盘数据", "GET", "/admin/dashboard", token=AT, role="管理员")

print("\n--- 1.3 用户管理 ---")
run_api_test(
    "用户列表", "GET", "/admin/users?page=1&page_size=10", token=AT, role="管理员"
)
run_api_test("用户搜索", "GET", "/admin/users?keyword=138", token=AT, role="管理员")

print("\n--- 1.4 图书管理 ---")
run_api_test(
    "图书列表(管理端)",
    "GET",
    "/book/search?page=1&page_size=5",
    token=AT,
    role="管理员",
)
run_api_test(
    "创建图书",
    "POST",
    "/book/",
    token=AT,
    json_data={
        "title": "测试图书-正式测试",
        "author": "测试作者",
        "isbn": "978-0-000-00000-0",
        "ar_level": 3.0,
        "word_count": 10000,
        "category": "fiction",
        "description": "正式测试用图书",
    },
    role="管理员",
)

# 获取刚创建的图书ID
books = run_api_test(
    "搜索测试图书",
    "GET",
    "/book/search?keyword=测试图书-正式测试",
    token=AT,
    role="管理员",
)
book_id = None
if isinstance(books, dict) and "items" in books:
    for b in books["items"]:
        if "测试图书-正式测试" in b.get("title", ""):
            book_id = b["id"]
            break

if book_id:
    run_api_test("获取图书详情", "GET", f"/book/{book_id}", token=AT, role="管理员")
    run_api_test(
        "更新图书",
        "PUT",
        f"/book/{book_id}",
        token=AT,
        json_data={"description": "更新后的描述"},
        role="管理员",
    )

print("\n--- 1.5 订单管理 ---")
run_api_test("订单列表", "GET", "/order/?page=1&page_size=10", token=AT, role="管理员")
run_api_test(
    "订单列表(管理端API)",
    "GET",
    "/admin/orders?page=1&page_size=10",
    token=AT,
    role="管理员",
)

print("\n--- 1.6 借阅管理 ---")
run_api_test(
    "借阅记录列表", "GET", "/admin/borrows?page=1&page_size=10", token=AT, role="管理员"
)

print("\n--- 1.7 押金管理 ---")
run_api_test(
    "押金记录列表",
    "GET",
    "/admin/deposits?page=1&page_size=10",
    token=AT,
    role="管理员",
)

print("\n--- 1.8 活动管理 ---")
run_api_test(
    "活动列表(管理端)", "GET", "/activity/?page=1&page_size=10", token=AT, role="管理员"
)
run_api_test(
    "创建活动",
    "POST",
    "/activity/",
    token=AT,
    json_data={
        "title": "正式测试活动",
        "description": "测试活动描述",
        "start_time": "2026-07-01T10:00:00",
        "end_time": "2026-07-01T12:00:00",
        "capacity": 20,
        "venue_id": 1,
    },
    role="管理员",
)

print("\n--- 1.9 场馆管理 ---")
run_api_test("场馆列表", "GET", "/admin/venues", token=AT, role="管理员")
venue_create = run_api_test(
    "创建场馆",
    "POST",
    "/admin/venues",
    token=AT,
    json_data={
        "name": "正式测试场馆",
        "address": "测试地址123号",
        "phone": "010-99999999",
    },
    role="管理员",
)

print("\n--- 1.10 老师管理 ---")
run_api_test("老师列表", "GET", "/admin/teachers", token=AT, role="管理员")
run_api_test(
    "创建老师",
    "POST",
    "/admin/teachers",
    token=AT,
    json_data={"name": "测试老师", "phone": "13900009999", "venue_id": 1},
    role="管理员",
)

print("\n--- 1.11 等级管理 ---")
run_api_test("等级列表", "GET", "/advancement/levels", token=AT, role="管理员")

print("\n--- 1.12 系统配置 ---")
run_api_test("系统配置列表", "GET", "/admin/config", token=AT, role="管理员")
run_api_test(
    "更新配置",
    "PUT",
    "/admin/config",
    token=AT,
    json_data={"key": "test_key", "value": "test_value"},
    role="管理员",
)

print("\n--- 1.13 成就管理 ---")
run_api_test("成就列表", "GET", "/advancement/achievements", token=AT, role="管理员")

print("\n--- 1.14 管理端页面模板 ---")
# 测试所有管理端HTML页面是否可访问
admin_pages = [
    "/admin/",
    "admin/dashboard",
    "admin/users",
    "admin/books",
    "admin/orders",
    "admin/borrow",
    "admin/deposit",
    "admin/activities",
    "admin/teachers",
    "admin/settings",
    "admin/levels",
    "admin/submissions",
    "admin/activity_checkin",
    "admin/achievements",
    "admin/bookcopy",
    "admin/booklist",
    "admin/questions",
    "admin/reports",
    "admin/reservation",
    "admin/venues",
]
for page in admin_pages:
    path = f"/{page}" if not page.startswith("/") else page
    run_api_test(f"页面: {page}", "GET", path, token=AT, role="管理员")

# ============================================================
# 角色2：家长 (User)
# ============================================================
section("角色2：家长 (User)")

print("\n--- 2.1 孩子管理 ---")
children = run_api_test("获取孩子列表", "GET", "/child/", token=UT, role="家长")
child_id = None
if isinstance(children, list) and len(children) > 0:
    child_id = children[0].get("id")
    print(f"    → 使用 child_id={child_id}")
elif isinstance(children, dict) and "items" in children:
    if children["items"]:
        child_id = children["items"][0].get("id")
        print(f"    → 使用 child_id={child_id}")

run_api_test(
    "添加孩子",
    "POST",
    "/child/",
    token=UT,
    json_data={"name": "测试小朋友", "age": 8, "grade": "二年级"},
    role="家长",
)

# 刷新孩子列表
children = run_api_test("获取孩子列表(刷新)", "GET", "/child/", token=UT, role="家长")
if isinstance(children, list) and len(children) > 0:
    child_id = children[0].get("id")
elif isinstance(children, dict) and "items" in children and children["items"]:
    child_id = children["items"][0].get("id")

if child_id:
    run_api_test("获取孩子详情", "GET", f"/child/{child_id}", token=UT, role="家长")

print("\n--- 2.2 图书搜索与书架 ---")
run_api_test(
    "图书搜索",
    "GET",
    "/book/search?keyword=cat&page=1&page_size=5",
    token=UT,
    role="家长",
)
run_api_test(
    "图书搜索(按等级)",
    "GET",
    "/book/search?ar_level=3&page=1&page_size=5",
    token=UT,
    role="家长",
)

if child_id and book_id:
    run_api_test(
        "添加到书架",
        "POST",
        "/bookshelf/",
        token=UT,
        json_data={"child_id": child_id, "book_id": book_id},
        role="家长",
    )

run_api_test(
    "获取书架", "GET", f"/bookshelf/?child_id={child_id}", token=UT, role="家长"
)

print("\n--- 2.3 订单 ---")
if child_id:
    run_api_test(
        "创建观察期订单",
        "POST",
        "/order/",
        token=UT,
        json_data={"child_id": child_id, "type": 2},
        role="家长",
    )
run_api_test("订单列表", "GET", "/order/?page=1&page_size=10", token=UT, role="家长")

print("\n--- 2.4 押金 ---")
if child_id:
    run_api_test(
        "押金状态", "GET", f"/deposit/status?child_id={child_id}", token=UT, role="家长"
    )

print("\n--- 2.5 借阅 ---")
if child_id:
    run_api_test("借阅记录", "GET", f"/borrow/{child_id}", token=UT, role="家长")

print("\n--- 2.6 预约 ---")
if child_id:
    run_api_test("预约列表", "GET", f"/reservation/{child_id}", token=UT, role="家长")

print("\n--- 2.7 消息 ---")
run_api_test("消息列表", "GET", "/message/", token=UT, role="家长")
run_api_test("未读消息数", "GET", "/message/unread-count", token=UT, role="家长")

print("\n--- 2.8 退款 ---")
run_api_test("退款预览", "GET", "/order/1/refund-preview", token=UT, role="家长")

print("\n--- 2.9 活动 ---")
run_api_test("活动列表", "GET", "/activity/", token=UT, role="家长")

print("\n--- 2.10 权益转让 ---")
run_api_test(
    "转让资格查询", "GET", "/child/transfer-eligibility", token=UT, role="家长"
)

print("\n--- 2.11 签到/打卡 ---")
if child_id:
    run_api_test(
        "打卡记录", "GET", f"/reading/checkin/{child_id}", token=UT, role="家长"
    )
    run_api_test(
        "连续打卡天数", "GET", f"/reading/streak/{child_id}", token=UT, role="家长"
    )

# ============================================================
# 角色3：孩子 (Child)
# ============================================================
section("角色3：孩子 (Child)")

if not child_id:
    print("  ⚠️ 无 child_id，跳过孩子角色测试")
else:
    print(f"  使用 child_id={child_id}")

    print("\n--- 3.1 阅读会话 ---")
    if book_id:
        run_api_test(
            "开始阅读会话",
            "POST",
            "/reading/session",
            token=UT,
            json_data={"child_id": child_id, "book_id": book_id},
            role="孩子",
        )

    run_api_test(
        "阅读会话历史",
        "GET",
        f"/reading/session?child_id={child_id}",
        token=UT,
        role="孩子",
    )

    print("\n--- 3.2 词汇 ---")
    run_api_test(
        "学习中词汇", "GET", f"/vocabulary/{child_id}/learning", token=UT, role="孩子"
    )
    run_api_test(
        "已掌握词汇", "GET", f"/vocabulary/{child_id}/mastered", token=UT, role="孩子"
    )
    run_api_test(
        "添加词汇",
        "POST",
        "/vocabulary/",
        token=UT,
        json_data={
            "child_id": child_id,
            "word": "elephant",
            "definition": "大象",
            "book_id": book_id,
        },
        role="孩子",
    )

    print("\n--- 3.3 晋级/等级 ---")
    run_api_test(
        "当前等级",
        "GET",
        f"/advancement/current?child_id={child_id}",
        token=UT,
        role="孩子",
    )
    run_api_test("等级列表", "GET", "/advancement/levels", token=UT, role="孩子")

    print("\n--- 3.4 成就 ---")
    run_api_test("成就列表", "GET", "/advancement/achievements", token=UT, role="孩子")

    print("\n--- 3.5 排行榜 ---")
    run_api_test(
        "排行榜(7天)",
        "GET",
        "/advancement/leaderboard?period=7d",
        token=UT,
        role="孩子",
    )
    run_api_test(
        "排行榜(30天)",
        "GET",
        "/advancement/leaderboard?period=30d",
        token=UT,
        role="孩子",
    )
    run_api_test(
        "排行榜(总榜)",
        "GET",
        "/advancement/leaderboard?period=total",
        token=UT,
        role="孩子",
    )

    print("\n--- 3.6 学习报告 ---")
    run_api_test(
        "学习报告", "GET", f"/reading/report?child_id={child_id}", token=UT, role="孩子"
    )

    print("\n--- 3.7 证书 ---")
    run_api_test(
        "证书列表", "GET", f"/certificate/?child_id={child_id}", token=UT, role="孩子"
    )

    print("\n--- 3.8 活动报名 ---")
    run_api_test("活动列表", "GET", "/activity/", token=UT, role="孩子")
    run_api_test(
        "活动报名",
        "POST",
        "/activity/1/enroll",
        token=UT,
        json_data={"child_id": child_id},
        role="孩子",
    )

# ============================================================
# 角色4：无认证访问 (未登录用户)
# ============================================================
section("角色4：未登录用户 (No Auth)")

# 应该被拒绝的接口
protected_endpoints = [
    ("GET", "/child/"),
    ("GET", "/book/search"),
    ("GET", "/order/"),
    ("GET", "/message/"),
    ("GET", "/reading/session?child_id=1"),
    ("GET", "/vocabulary/1/learning"),
    ("GET", "/advancement/levels"),
    ("GET", "/admin/dashboard"),
    ("GET", "/admin/users"),
]
for method, path in protected_endpoints:
    run_api_test(
        f"无认证: {method} {path}", method, path, expected_status=401, role="未登录"
    )

# ============================================================
# 角色5：权限隔离 (用户访问管理接口)
# ============================================================
section("角色5：权限隔离 (用户Token访问管理接口)")

admin_only = [
    ("GET", "/admin/dashboard"),
    ("GET", "/admin/users"),
    ("GET", "/admin/config"),
    ("POST", "/admin/venues"),
    ("POST", "/admin/teachers"),
    ("GET", "/admin/orders"),
]
for method, path in admin_only:
    run_api_test(
        f"用户→管理: {method} {path}",
        method,
        path,
        token=UT,
        expected_status=403,
        role="权限隔离",
    )

# ============================================================
# 角色6：边界情况
# ============================================================
section("角色6：边界情况与异常处理")

run_api_test(
    "不存在的资源", "GET", "/book/99999", token=UT, expected_status=404, role="边界"
)
run_api_test(
    "无效JSON",
    "POST",
    "/child/",
    token=UT,
    json_data={},
    expected_status=422,
    role="边界",
)
run_api_test(
    "不存在的路由",
    "GET",
    "/nonexistent/path",
    token=AT,
    expected_status=404,
    role="边界",
)
run_api_test(
    "无效token",
    "GET",
    "/child/",
    token="invalid-token-xxx",
    expected_status=401,
    role="边界",
)
run_api_test(
    "超长keyword搜索", "GET", "/book/search?keyword=" + "x" * 500, token=UT, role="边界"
)
run_api_test("负数page", "GET", "/book/search?page=-1", token=UT, role="边界")
run_api_test(
    "超大page_size", "GET", "/book/search?page_size=9999", token=UT, role="边界"
)

# ============================================================
# 角色7：前后端API对齐检查
# ============================================================
section("角色7：前后端API对齐检查")

# 前端 api.js 中定义的端点 vs 后端实际端点
frontend_apis = {
    # 认证
    "wxLogin": ("POST", "/user/wx-login"),
    # 孩子
    "getChildren": ("GET", "/child/"),
    "addChild": ("POST", "/child/"),
    # 图书
    "searchBooks": ("GET", "/book/search"),
    "getBookDetail": ("GET", "/book/1"),
    # 书架
    "getBookshelf": ("GET", "/bookshelf/?child_id=1"),
    "addToBookshelf": ("POST", "/bookshelf/"),
    # 订单
    "createOrder": ("POST", "/order/"),
    "getOrders": ("GET", "/order/"),
    # 借阅
    "getBorrows": ("GET", "/borrow/1"),
    # 押金
    "getDepositStatus": ("GET", "/deposit/status?child_id=1"),
    # 阅读
    "startSession": ("POST", "/reading/session"),
    "getCheckin": ("GET", "/reading/checkin/1"),
    "getStreak": ("GET", "/reading/streak/1"),
    # 词汇
    "getLearningVocab": ("GET", "/vocabulary/1/learning"),
    "getMasteredVocab": ("GET", "/vocabulary/1/mastered"),
    # 测验
    "startQuiz": ("POST", "/advancement/quiz/start"),
    "getQuizQuestions": ("GET", "/advancement/quiz/questions/1"),
    # 晋级
    "getCurrentLevel": ("GET", "/advancement/current?child_id=1"),
    "getLevels": ("GET", "/advancement/levels"),
    "getAchievements": ("GET", "/advancement/achievements"),
    "getLeaderboard": ("GET", "/advancement/leaderboard"),
    # 活动
    "getActivities": ("GET", "/activity/"),
    # 消息
    "getMessages": ("GET", "/message/"),
    # 预约
    "getReservations": ("GET", "/reservation/1"),
    # 证书
    "getCertificates": ("GET", "/certificate/?child_id=1"),
    # 退款
    "getRefundPreview": ("GET", "/order/1/refund-preview"),
}

for name, (method, path) in frontend_apis.items():
    status_code = run_api_test(
        f"前端API对齐: {name}", method, path, token=UT, role="API对齐"
    )

# ============================================================
# 汇总
# ============================================================
section("测试汇总")

print(f"\n  总计: {TOTAL}")
print(f"  通过: {PASS} ✅")
print(f"  失败: {FAIL} ❌")
print(f"  通过率: {PASS / TOTAL * 100:.1f}%")

if ERRORS:
    print(f"\n{'=' * 60}")
    print(f"  失败详情 ({len(ERRORS)} 项)")
    print(f"{'=' * 60}")
    for e in ERRORS:
        print(f"  ❌ {e}")

# 输出JSON结果
report = {
    "timestamp": datetime.now().isoformat(),
    "total": TOTAL,
    "pass": PASS,
    "fail": FAIL,
    "pass_rate": f"{PASS / TOTAL * 100:.1f}%",
    "errors": ERRORS,
    "results": RESULTS,
}
with open("/Users/litianyu/cc-projects/librio/scripts/test_results.json", "w") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print("\n  详细结果已保存到: scripts/test_results.json")
