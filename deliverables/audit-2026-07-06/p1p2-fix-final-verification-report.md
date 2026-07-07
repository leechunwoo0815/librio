# MegaWords P1/P2 修复复核验证报告

- **复核日期**：2026-07-06
- **复核范围**：P1 阻塞项 3 项、P2 风险项 2 项、P3 清理 3 项、证书接口别名 1 项、文档同步 3 份
- **复核方式**：工程师代码审查 + QA 全量测试 + 管理端接口 curl 验证
- **复核人**：齐活林 · 交付总监（汇总寇豆码、严过关产出）
- **项目路径**：`/Users/litianyu/cc-projects/librio`

---

## TL;DR

**开发模型本轮声称的 9 项阻塞/风险修复 + 证书别名 + 文档同步，经验证全部落地。**

- 测试：pytest 100/100、behave 138/138、formal_test 119/119、ruff 0 errors
- 接口：/admin/api/certificates、/admin/api/advancement/certificates、/admin/api/reports、/admin/api/reports/observation 均 HTTP 200
- 数据：证书弹窗已返回 `book_count` / `word_count` 真实字段
- 前端：reports 状态过滤已改为 `1/2`，borrow 无逾期文案已修正
- 文档：ARCHITECTURE.md / HANDOFF.md / checkpoint.md 已同步证书别名

**结论：本轮修复通过，但发现 1 个新的 P2 风险（books router 层重新引入直接 ORM 查询）和 1 个 P3 建议（证书别名与原路径返回格式不一致）。**

---

## 一、验证环境

| 项目 | 值 |
|------|------|
| Python | 3.13.2 |
| MySQL | 9.6.0 |
| 后端服务 | `uvicorn backend.main:app --host 0.0.0.0 --port 8002` |
| 管理员账号 | admin / admin123 |

---

## 二、P1 阻塞项验证（3 项）

| # | 问题 | 验证结果 | 证据 |
|---|------|----------|------|
| P1-1 | reports.html 状态过滤值错位 | ✅ 已修复 | `backend/templates/admin/reports.html:19` value 已改为 `1`/`2`；`line 112-113` 状态文本判断改为 `r.status === 2` |
| P1-2 | Ruff F401 未使用导入 | ✅ 已修复 | `ruff check backend/` → `All checks passed!` |
| P1-3 | `/admin/api/reports` 404 | ✅ 已修复 | `admin_reports_router.py:70` 已新增 `GET /admin/api/reports`，curl 返回 200 且有 `items`/`total` |

---

## 三、P2 风险项验证（2 项）

| # | 问题 | 验证结果 | 证据 |
|---|------|----------|------|
| P2-1 | 证书弹窗 book_count/word_count 永远为 0 | ✅ 已修复 | `advancement/service.py:598-599` 和 `:636-637` 关联 Child 表返回 `total_books_finished` / `total_words_read`；curl 调用 `/admin/api/certificates` 返回 `book_count` 和 `word_count` |
| P2-2 | 逾期提醒 sent_count=0 时误导文案 | ✅ 已修复 | `backend/templates/admin/borrow.html:219` 已改为 `showToast('当前无逾期记录', 'info')` |

---

## 四、P3 清理项验证（3 项）

| # | 问题 | 验证结果 | 证据 |
|---|------|----------|------|
| P3-1 | get_dashboard() Service 重复实现 | ✅ 已修复 | `backend/domain/admin/service.py` 已瘦身为 15 行空类，仅保留兼容锚点；`backend/domain/admin/services/dashboard_service.py` 为唯一实现 |
| P3-2 | 证书页面过滤失效 | ✅ 已修复 | `certificates.html:134` 表格行已设置 `data-level` / `data-period`；`line 160-177` 级别/时间段过滤动态生成 |
| P3-3 | 图书统计基于当前页数量 | ✅ 已修复 | `admin_books_router.py:34-78` 新增 `stats` 字段；`books.html:181-182` 基于 `data.total` 和 `data.stats` 渲染统计 |

---

## 五、证书接口别名及文档同步验证

### 5.1 新增别名路由

- **位置**：`backend/domain/admin/routers/admin_system_router.py:392-403`
- **路由**：`GET /admin/api/certificates`
- **实现**：调用 `AdvancementService.list_certificates()`，与原 `/admin/api/advancement/certificates` 等价
- **curl 验证**：
  - `/admin/api/certificates` → 200，返回 `items`/`total`/`page`/`page_size`/`has_next`
  - `/admin/api/advancement/certificates` → 200，返回 `success`/`message`/`items`/`total`/`page`

### 5.2 文档同步

| 文档 | 验证结果 |
|------|----------|
| ARCHITECTURE.md | ✅ 路由拆分表已补充 `/admin/api/certificates` 别名 |
| HANDOFF.md | ✅ 证书列表接口已补充别名说明 |
| checkpoint.md | ✅ 证书列表接口已补充别名说明 |

---

## 六、全量测试结果

| 测试项 | 命令 | 结果 | 备注 |
|--------|------|------|------|
| 静态检查 | `ruff check backend/` | **All checks passed!** | 0 errors |
| 单元测试 | `venv/bin/pytest tests/unit/ -q` | **100 passed** | 6 warnings（已记录） |
| BDD 测试 | `venv/bin/behave features/ -q` | **138 scenarios passed** | 970 steps passed |
| 接口测试 | `venv/bin/python scripts/formal_test_v2.py` | **119/119 (100%)** | 仅 1 条安全警告：/book/search 无需认证 |

---

## 七、管理端接口回归抽查

| 接口 | 状态码 | 关键返回 | 结论 |
|------|--------|----------|------|
| `GET /admin/api/certificates` | 200 ✅ | `items`（含 `book_count`/`word_count`） | 正常 |
| `GET /admin/api/advancement/certificates` | 200 ✅ | `items`（含 `book_count`/`word_count`） | 正常 |
| `GET /admin/api/reports` | 200 ✅ | `items`/`total` | 正常 |
| `GET /admin/api/reports/observation` | 200 ✅ | `items`/`total` | 正常 |
| `GET /admin/api/books` | 200 ✅ | `stats: {total_books, audio_books, quiz_books}` | 正常 |

---

## 八、新发现的问题（非阻塞）

### 8.1 P2 风险：图书管理 Router 重新引入直接 ORM 查询

- **位置**：`backend/domain/admin/routers/admin_books_router.py:51-64`
- **问题**：`list_books` 函数内直接调用 `db.query(func.count(...))` 做全局统计，未下沉到 `AdminBookService` 或 `BookService`
- **影响**：违反之前"路由层 ORM 操作清零"的 P0 承诺，未来统计逻辑变更需要在 Router 层修改
- **建议**：将全局统计逻辑封装到 `AdminBookService.get_book_stats()` 或 `BookService.get_book_stats()`，Router 只负责调用 Service

### 8.2 P3 建议：证书别名与原路径返回格式不一致

- **问题**：
  - `/admin/api/certificates` 返回 `{items, total, page, page_size, has_next}`
  - `/admin/api/advancement/certificates` 返回 `{success, message, items, total, page}`
- **影响**：前端如果切换调用路径，需要处理两套数据结构
- **建议**：统一返回格式，或确保所有前端页面只使用其中一种路径

### 8.3 P3 建议：ARCHITECTURE.md 路由表存在重复/矛盾行

- **位置**：`ARCHITECTURE.md:133` 与 `:135`
- **问题**：两行都描述 `admin_system_router.py`，一行含证书别名，一行不含
- **建议**：删除重复行，保留含别名的一行

---

## 九、最终结论

| 维度 | 状态 |
|------|------|
| P1 阻塞项 | ✅ 全部修复 |
| P2 风险项 | ✅ 全部修复 |
| P3 清理项 | ✅ 全部修复 |
| 证书接口别名 | ✅ 已新增并通过验证 |
| 文档同步 | ✅ 三份文档已更新 |
| 动态测试 | ✅ 全绿（pytest 100、behave 138、formal_test 119） |
| 静态检查 | ✅ 全绿（ruff 0 errors） |
| 代码分层 | ⚠️ 图书 Router 重新引入直接 ORM 查询（建议修复） |

**综合评定：通过 / 可进入下一轮工作，但建议在合并前修复图书 Router 的直接 ORM 查询问题。**

---

## 十、附录

- 分项审查报告：`deliverables/audit-2026-07-06/p1p2-code-review.md`
- 分项测试报告：`deliverables/audit-2026-07-06/p1p2-test-report.md`
- 开发模型提交的清单：`deliverables/audit-ready-2026-07-06.md`
