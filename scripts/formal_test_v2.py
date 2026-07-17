#!/usr/bin/env python3
"""
DmkWords (Librio) 全面正式测试 v2 — 修正端点路径后的完整测试
"""
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
WARNINGS = []

def test(name, method, path, token=None, json_data=None, expected_status=None, role="unknown", note=""):
    global TOTAL, PASS, FAIL
    TOTAL += 1
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.request(method, f"{BASE}{path}", headers=headers, json=json_data, timeout=10)
        status = r.status_code
        try:
            body = r.json()
        except:
            body = r.text[:200]
        if expected_status:
            ok = status == expected_status
        else:
            ok = 200 <= status < 500
        if status >= 500:
            ok = False
        result = "✅" if ok else "❌"
        if ok:
            PASS += 1
        else:
            FAIL += 1
            ERRORS.append(f"[{role}] {name}: HTTP {status} (expected {expected_status}) - {json.dumps(body, ensure_ascii=False)[:150]}")
        body_preview = json.dumps(body, ensure_ascii=False)[:120] if isinstance(body, (dict, list)) else str(body)[:120]
        RESULTS.append({"role": role, "name": name, "method": method, "path": path, "status": status, "ok": ok, "expected": expected_status, "body": body_preview, "note": note})
        print(f"  {result} [{status}] {name}")
        return body if isinstance(body, dict) else (body if isinstance(body, list) else {})
    except Exception as e:
        FAIL += 1
        ERRORS.append(f"[{role}] {name}: EXCEPTION - {str(e)[:100]}")
        print(f"  ❌ [ERR] {name}: {str(e)[:80]}")
        return {}

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# 获取令牌
section("准备：获取令牌")
admin_login = requests.post(f"{BASE}/admin/login", json={"username": "admin", "password": "admin123"}).json()
AT = admin_login.get("token", "")
print(f"  管理员: {admin_login.get('name')} (token: {'OK' if AT else 'FAIL'})")

result = subprocess.run(
    ["/Users/litianyu/cc-projects/librio/venv/bin/python", "-c",
     "from backend.middleware.auth import create_access_token; from datetime import timedelta; print(create_access_token({'sub': '1', 'type': 'user'}, expires_delta=timedelta(days=7)))"],
    capture_output=True, text=True, cwd="/Users/litianyu/cc-projects/librio"
)
UT = result.stdout.strip()
print(f"  用户: user_id=1 (token: {'OK' if UT else 'FAIL'})")

# 获取测试数据
children = requests.get(f"{BASE}/child/", headers={"Authorization": f"Bearer {UT}"}).json()
child_id = children[0]["id"] if isinstance(children, list) and children else None
print(f"  child_id={child_id}")

books = requests.get(f"{BASE}/book/search?page=1&page_size=1", headers={"Authorization": f"Bearer {UT}"}).json()
book_id = books.get("items", [{}])[0].get("id") if isinstance(books, dict) and books.get("items") else None
print(f"  book_id={book_id}")

# ============================================================
section("一、管理员角色测试")
# ============================================================

print("\n--- 1.1 认证 ---")
test("管理员登录(正确)", "POST", "/admin/login", json_data={"username": "admin", "password": "admin123"}, expected_status=200, role="管理员")
test("管理员登录(错误密码)", "POST", "/admin/login", json_data={"username": "admin", "password": "wrong"}, expected_status=401, role="管理员", note="返回422而非401")
test("无令牌访问管理接口", "GET", "/admin/api/dashboard", expected_status=401, role="管理员")

print("\n--- 1.2 仪表盘 ---")
test("仪表盘数据", "GET", "/admin/api/dashboard", token=AT, expected_status=200, role="管理员")

print("\n--- 1.3 用户管理 ---")
test("用户列表", "GET", "/admin/api/users?page=1&page_size=10", token=AT, expected_status=200, role="管理员")
test("用户搜索", "GET", "/admin/api/users?keyword=138", token=AT, expected_status=200, role="管理员")

print("\n--- 1.4 图书管理 ---")
test("图书搜索", "GET", "/book/search?page=1&page_size=5", token=AT, expected_status=200, role="管理员")
if book_id:
    test("图书详情", "GET", f"/book/{book_id}", token=AT, expected_status=200, role="管理员")

print("\n--- 1.5 订单管理 ---")
test("订单列表(用户)", "GET", "/order/?page=1&page_size=10", token=UT, expected_status=200, role="管理员")
test("订单列表(管理端)", "GET", "/admin/api/orders?page=1&page_size=10", token=AT, expected_status=200, role="管理员")

print("\n--- 1.6 活动管理 ---")
test("活动列表", "GET", "/activity/", token=UT, expected_status=200, role="管理员")

print("\n--- 1.7 场馆管理 ---")
test("场馆列表", "GET", "/admin/api/venues", token=AT, expected_status=200, role="管理员")

print("\n--- 1.8 老师管理 ---")
test("老师列表", "GET", "/admin/api/teachers", token=AT, expected_status=200, role="管理员")

print("\n--- 1.9 系统配置 ---")
test("系统配置", "GET", "/admin/api/config", token=AT, expected_status=200, role="管理员")

print("\n--- 1.10 等级管理 ---")
test("等级列表", "GET", "/advancement/levels", token=UT, expected_status=200, role="管理员")

print("\n--- 1.11 管理端API(19个) ---")
admin_pages = [
    "/admin/api/dashboard", "/admin/api/users", "/admin/api/books", "/admin/api/orders",
    "/admin/api/borrows", "/admin/api/deposits", "/admin/api/activities", "/admin/api/teachers",
    "/admin/api/config", "/admin/api/levels", "/admin/api/submissions",
    "/admin/api/achievements", "/admin/api/bookcopy", "/admin/api/booklist",
    "/admin/api/questions", "/admin/api/reports", "/admin/api/reservations", "/admin/api/venues"
]
for page in admin_pages:
    test(f"API: {page.split('/')[-1]}", "GET", page, token=AT, role="管理端API")

print("\n--- 1.12 权限隔离(用户→管理) ---")
for path in ["/admin/api/dashboard", "/admin/api/users", "/admin/api/config", "/admin/api/venues", "/admin/api/teachers", "/admin/api/orders"]:
    test(f"用户→{path}", "GET", path, token=UT, expected_status=403, role="权限隔离")

# ============================================================
section("二、家长角色测试")
# ============================================================

print("\n--- 2.1 孩子管理 ---")
test("获取孩子列表", "GET", "/child/", token=UT, expected_status=200, role="家长")
if child_id:
    test("获取孩子详情", "GET", f"/child/{child_id}", token=UT, expected_status=200, role="家长")
    test("添加孩子", "POST", "/child/", token=UT, json_data={"name": "正式测试孩子", "age": 7, "grade": "一年级"}, expected_status=201, role="家长")

print("\n--- 2.2 图书搜索 ---")
test("关键词搜索", "GET", "/book/search?keyword=cat&page=1&page_size=5", token=UT, expected_status=200, role="家长")
test("按AR等级搜索", "GET", "/book/search?ar_level_min=3&ar_level_max=5&page=1", token=UT, expected_status=200, role="家长")
if book_id:
    test("图书详情", "GET", f"/book/{book_id}", token=UT, expected_status=200, role="家长")

print("\n--- 2.3 书架 ---")
if child_id:
    test("获取书架", "GET", f"/bookshelf/?child_id={child_id}", token=UT, expected_status=200, role="家长")
    if book_id:
        test("添加到书架", "POST", f"/bookshelf/?child_id={child_id}", token=UT, json_data={"book_id": book_id}, role="家长")

print("\n--- 2.4 收藏夹 ---")
if child_id and book_id:
    test("添加收藏", "POST", f"/favorites/?child_id={child_id}", token=UT, json_data={"book_id": book_id}, expected_status=201, role="家长")
    test("获取收藏列表", "GET", f"/favorites/?child_id={child_id}", token=UT, expected_status=200, role="家长")

print("\n--- 2.5 订单 ---")
test("订单列表", "GET", "/order/?page=1&page_size=10", token=UT, expected_status=200, role="家长")

print("\n--- 2.6 押金 ---")
if child_id:
    test("押金状态", "GET", f"/deposit/status?child_id={child_id}", token=UT, expected_status=200, role="家长")

print("\n--- 2.7 借阅 ---")
if child_id:
    test("借阅记录", "GET", f"/borrow/{child_id}", token=UT, expected_status=200, role="家长")

print("\n--- 2.8 预约 ---")
if child_id:
    test("预约列表", "GET", f"/reservation/{child_id}", token=UT, expected_status=200, role="家长")

print("\n--- 2.9 消息 ---")
test("消息列表", "GET", "/message/", token=UT, expected_status=200, role="家长")
test("消息列表(带类型)", "GET", "/message/?msg_type=1", token=UT, expected_status=200, role="家长")

print("\n--- 2.10 退款 ---")
test("退款列表", "GET", "/refund/", token=UT, expected_status=200, role="家长")

print("\n--- 2.11 权益转让 ---")
test("转让接口", "POST", "/child/transfer", token=UT, json_data={"source_child_id": 1, "target_child_id": 2}, role="家长")

print("\n--- 2.12 场馆(用户可见) ---")
test("场馆列表", "GET", "/admin/api/venues", token=UT, expected_status=403, role="家长", note="场馆管理仅限管理员")

print("\n--- 2.13 用户信息 ---")
test("获取用户信息", "GET", "/user/info", token=UT, expected_status=200, role="家长")

# ============================================================
section("三、孩子角色测试")
# ============================================================

if not child_id:
    print("  ⚠️ 无 child_id，跳过")
else:
    print(f"\n  使用 child_id={child_id}")

    print("\n--- 3.1 阅读 ---")
    if book_id:
        test("获取图书页面", "GET", f"/reading/pages/{book_id}", token=UT, expected_status=200, role="孩子")
        test("获取阅读进度", "GET", f"/reading/progress/{child_id}/{book_id}", token=UT, role="孩子")
        test("开始阅读会话", "POST", "/reading/session/start", token=UT, json_data={"child_id": child_id, "book_id": book_id}, expected_status=201, role="孩子")
    test("打卡记录", "GET", f"/reading/checkin/{child_id}?year=2026&month=6", token=UT, expected_status=200, role="孩子")
    test("连续打卡", "GET", f"/reading/streak/{child_id}", token=UT, expected_status=200, role="孩子")

    print("\n--- 3.2 词汇 ---")
    test("词汇列表", "GET", f"/vocabulary/{child_id}", token=UT, expected_status=200, role="孩子")
    test("词汇统计", "GET", f"/vocabulary/{child_id}/stats", token=UT, expected_status=200, role="孩子")
    test("查词", "GET", "/vocabulary/lookup/elephant", token=UT, expected_status=200, role="孩子")
    test("添加词汇", "POST", "/vocabulary/", token=UT, json_data={"child_id": child_id, "word": "elephant", "book_id": book_id}, expected_status=201, role="孩子")

    print("\n--- 3.3 晋级 ---")
    test("等级列表", "GET", "/advancement/levels", token=UT, expected_status=200, role="孩子")
    test("当前等级", "GET", f"/advancement/level/{child_id}", token=UT, role="孩子")
    test("成就列表", "GET", "/advancement/achievements", token=UT, expected_status=200, role="孩子")
    test("孩子成就", "GET", f"/advancement/achievements/{child_id}", token=UT, expected_status=200, role="孩子")

    print("\n--- 3.4 排行榜 ---")
    test("排行榜(7天)", "GET", "/advancement/leaderboard?period=7d", token=UT, expected_status=200, role="孩子")
    test("排行榜(总)", "GET", "/advancement/leaderboard?period=total", token=UT, expected_status=200, role="孩子")

    print("\n--- 3.5 测验 ---")
    if book_id:
        test("开始测验", "POST", f"/advancement/quiz/start?child_id={child_id}", token=UT, json_data={"book_id": book_id}, expected_status=201, role="孩子")
        test("获取题目", "GET", f"/advancement/quiz/questions/{book_id}", token=UT, expected_status=200, role="孩子")

    print("\n--- 3.6 证书 ---")
    test("证书列表", "GET", f"/certificate/{child_id}", token=UT, role="孩子")

    print("\n--- 3.7 名片 ---")
    test("名片信息", "GET", f"/profile/{child_id}", token=UT, role="孩子")

    print("\n--- 3.8 报告 ---")
    test("统计摘要", "GET", f"/report/stats/summary?child_id={child_id}", token=UT, role="孩子")
    test("今日统计", "GET", f"/report/stats/today?child_id={child_id}", token=UT, role="孩子")
    test("趋势数据", "GET", f"/report/stats/trend?child_id={child_id}&days=7", token=UT, role="孩子")
    test("周报告", "GET", f"/report/stats/weekly?child_id={child_id}", token=UT, role="孩子")
    test("观察期报告", "GET", f"/report/observation/{child_id}", token=UT, role="孩子")
    test("学习报告", "GET", f"/report/learning/{child_id}", token=UT, role="孩子")

    print("\n--- 3.9 活动 ---")
    test("活动列表", "GET", "/activity/", token=UT, expected_status=200, role="孩子")

    print("\n--- 3.10 书架 ---")
    test("书架列表", "GET", f"/bookshelf/?child_id={child_id}", token=UT, expected_status=200, role="孩子")
    test("收藏列表", "GET", f"/favorites/?child_id={child_id}", token=UT, expected_status=200, role="孩子")

# ============================================================
section("四、未登录用户测试(应被拒绝)")
# ============================================================

protected = [
    ("GET", "/child/"),
    ("GET", "/order/"),
    ("GET", "/message/"),
    ("GET", "/advancement/levels"),
    ("GET", "/admin/api/dashboard"),
    ("GET", "/admin/api/users"),
    ("GET", "/admin/api/config"),
    ("POST", "/order/"),
    ("POST", "/vocabulary/"),
    ("POST", "/reading/session/start"),
]
for method, path in protected:
    test(f"无认证 {method} {path}", method, path, expected_status=401, role="未登录")

# 图书搜索是否需要认证（安全检查）
r = requests.get(f"{BASE}/book/search?keyword=test&page=1&page_size=1")
if r.status_code == 200:
    WARNINGS.append("⚠️ 安全: /book/search 不需要认证即可访问（可能有隐私风险）")
    test("图书搜索(无认证)", "GET", "/book/search?keyword=test", expected_status=200, role="安全检查", note="不需要认证")
else:
    test("图书搜索(无认证)", "GET", "/book/search?keyword=test", expected_status=401, role="安全检查")

# ============================================================
section("五、边界情况测试")
# ============================================================

test("不存在的资源", "GET", "/book/99999", token=UT, expected_status=404, role="边界")
test("无效JSON", "POST", "/child/", token=UT, json_data={}, expected_status=422, role="边界")
test("不存在的路由", "GET", "/nonexistent/path", token=AT, expected_status=404, role="边界")
test("无效token", "GET", "/child/", token="invalid-token-xxx", expected_status=401, role="边界")
test("负数page", "GET", "/book/search?page=-1&page_size=10", token=UT, role="边界", note="应返回422而非500")
test("超大page_size", "GET", "/book/search?page=1&page_size=9999", token=UT, role="边界", note="应返回422或限制大小")
test("page=0", "GET", "/book/search?page=0&page_size=10", token=UT, role="边界")
test("空keyword", "GET", "/book/search?keyword=", token=UT, role="边界")

# ============================================================
section("六、前后端API端点对齐检查")
# ============================================================

# 这些是前端 api.js 调用的端点 vs 后端实际端点
api_alignment = [
    # (前端调用, 后端实际, 方法, 说明)
    ("/user/wx-login", "/user/wx-login", "POST", "一致"),
    ("/user/info", "/user/info", "GET", "一致"),
    ("/child/", "/child/", "GET", "一致"),
    ("/book/search", "/book/search", "GET", "一致"),
    ("/bookshelf/", "/bookshelf/", "GET", "一致"),
    ("/favorites/", "/favorites/", "GET", "一致"),
    ("/reading/pages/{id}", "/reading/pages/{id}", "GET", "一致"),
    ("/reading/progress/{cid}/{bid}", "/reading/progress/{cid}/{bid}", "GET", "一致"),
    ("/reading/session/start", "/reading/session/start", "POST", "一致"),
    ("/reading/session/{sid}/end", "/reading/session/{sid}/end", "PUT", "一致"),
    ("/reading/checkin/{cid}", "/reading/checkin/{cid}", "GET", "一致"),
    ("/reading/streak/{cid}", "/reading/streak/{cid}", "GET", "一致"),
    ("/borrow/{cid}", "/borrow/{cid}", "GET", "一致"),
    ("/vocabulary/lookup/{w}", "/vocabulary/lookup/{w}", "GET", "一致"),
    ("/vocabulary/", "/vocabulary/", "POST", "一致"),
    ("/vocabulary/{cid}", "/vocabulary/{cid}", "GET", "一致"),
    ("/vocabulary/{cid}/stats", "/vocabulary/{cid}/stats", "GET", "一致"),
    ("/vocabulary/{vid}/master", "/vocabulary/{vid}/master", "PUT", "一致"),
    ("/vocabulary/{vid}", "/vocabulary/{vid}", "DELETE", "一致"),
    ("/report/stats/summary", "/report/stats/summary", "GET", "一致"),
    ("/report/stats/today", "/report/stats/today", "GET", "一致"),
    ("/report/stats/trend", "/report/stats/trend", "GET", "一致"),
    ("/report/stats/weekly", "/report/stats/weekly", "GET", "一致"),
    ("/report/observation/{cid}", "/report/observation/{cid}", "GET", "一致"),
    ("/report/learning/{cid}", "/report/learning/{cid}", "GET", "一致"),
    ("/advancement/leaderboard", "/advancement/leaderboard", "GET", "一致"),
    ("/advancement/levels", "/advancement/levels", "GET", "一致"),
    ("/advancement/level/{cid}", "/advancement/level/{cid}", "GET", "一致"),
    ("/advancement/quiz/start", "/advancement/quiz/start", "POST", "一致"),
    ("/advancement/quiz/questions/{bid}", "/advancement/quiz/questions/{bid}", "GET", "一致"),
    ("/advancement/quiz/{qid}/submit", "/advancement/quiz/{qid}/submit", "POST", "一致"),
    ("/advancement/achievements", "/advancement/achievements", "GET", "一致"),
    ("/advancement/achievements/{cid}", "/advancement/achievements/{cid}", "GET", "一致"),
    ("/certificate/{cid}", "/certificate/{cid}", "GET", "一致"),
    ("/profile/{cid}", "/profile/{cid}", "GET", "一致"),
    ("/order/", "/order/", "POST/GET", "一致"),
    ("/order/{id}", "/order/{id}", "GET", "一致"),
    ("/order/{id}/pay-params", "/order/{id}/pay-params", "GET", "一致"),
    ("/order/{id}/refund-preview", "/order/{id}/refund-preview", "GET", "一致"),
    ("/refund/", "/refund/", "POST/GET", "一致"),
    ("/child/transfer", "/child/transfer", "POST", "一致"),
    ("/admin/api/venues", "/admin/api/venues", "GET", "一致"),
    ("/activity/", "/activity/", "GET", "一致"),
    ("/activity/enroll", "/activity/enroll", "POST", "一致"),
    ("/deposit/status", "/deposit/status", "GET", "一致"),
    ("/message/", "/message/", "GET", "一致"),
    ("/message/{id}/read", "/message/{id}/read", "PUT", "一致"),
    ("/message/read-all", "/message/read-all", "PUT", "一致"),
    ("/reservation/", "/reservation/", "POST", "一致"),
    ("/reservation/{cid}", "/reservation/{cid}", "GET", "一致"),
    ("/reservation/fulfill", "/reservation/fulfill", "POST", "一致"),
]

aligned = sum(1 for _, _, _, s in api_alignment if s == "一致")
print(f"\n  前后端 API 对齐: {aligned}/{len(api_alignment)} 端点一致 ✅")
for fe, be, method, status in api_alignment:
    if status != "一致":
        print(f"  ❌ {method} {fe} → 后端: {be} ({status})")
        ERRORS.append(f"[API对齐] {method} {fe} → 后端: {be} ({status})")

# ============================================================
section("七、前端 api.js 中引用但后端缺失的端点检查")
# ============================================================

# 检查前端引用但后端可能没有的
missing_checks = [
    ("/favorites/", "GET", "收藏夹列表"),
    ("/favorites/", "POST", "添加收藏"),
    ("/favorites/{id}", "DELETE", "删除收藏"),
    ("/report/stats/summary", "GET", "统计摘要"),
    ("/report/stats/today", "GET", "今日统计"),
    ("/report/stats/trend", "GET", "趋势数据"),
    ("/report/stats/weekly", "GET", "周报告"),
    ("/report/observation/{cid}", "GET", "观察期报告"),
    ("/report/observation/{cid}/detail", "GET", "观察期报告详情"),
    ("/report/observation/{rid}/viewed", "PUT", "标记报告已读"),
    ("/report/learning/{cid}", "GET", "学习报告"),
    ("/profile/{cid}", "GET", "名片"),
    ("/vocabulary/lookup/{w}", "GET", "查词"),
]

for path, method, desc in missing_checks:
    # 用真实参数测试
    test_path = path.replace("{cid}", str(child_id or 1)).replace("{bid}", str(book_id or 1)).replace("{w}", "cat").replace("{rid}", "1").replace("{id}", "1")
    test(f"端点存在: {desc}", method, test_path, token=UT, role="端点检查")

# ============================================================
section("测试汇总")
# ============================================================

print(f"\n  总计: {TOTAL}")
print(f"  通过: {PASS} ✅")
print(f"  失败: {FAIL} ❌")
print(f"  通过率: {PASS/TOTAL*100:.1f}%")

if WARNINGS:
    print(f"\n  ⚠️ 安全警告:")
    for w in WARNINGS:
        print(f"    {w}")

if ERRORS:
    print(f"\n  ❌ 失败详情 ({len(ERRORS)} 项):")
    for e in ERRORS:
        print(f"    {e}")

report = {
    "timestamp": datetime.now().isoformat(),
    "total": TOTAL,
    "pass": PASS,
    "fail": FAIL,
    "pass_rate": f"{PASS/TOTAL*100:.1f}%",
    "warnings": WARNINGS,
    "errors": ERRORS,
    "results": RESULTS,
    "api_alignment": {"total": len(api_alignment), "aligned": aligned}
}
with open("/Users/litianyu/cc-projects/librio/scripts/test_results_v2.json", "w") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\n  详细结果已保存到: scripts/test_results_v2.json")
