# librio 项目修复全量审查清单

**日期**：2026-07-06
**审查范围**：P1/P2/P3 修复 + AdminService 上帝类拆分 + 证书接口别名
**提交人**：Kimi Code CLI
**项目路径**：`/Users/litianyu/cc-projects/librio`

---

## 一、今日变更总览

| 类别 | 项数 | 状态 |
|---|---|---|
| P1 阻塞项修复 | 3 | ✅ 已完成 |
| P2 风险项修复 | 3 | ✅ 已完成 |
| P3 架构/体验清理 | 3 | ✅ 已完成 |
| 证书接口别名及文档同步 | 4 | ✅ 已完成 |
| 复核后发现的问题 | 3 | ✅ 已完成 |
| AdminService 上帝类拆分 | 14 个 Service | ✅ 已完成（本轮验证通过） |
| 测试验证 | 4 类 | ✅ 全部通过 |

---

## 二、P1 阻塞项修复（专家审查报告要求）

| # | 问题 | 修复文件 | 修复说明 |
|---|---|---|---|
| P1-1 | `reports.html` 状态过滤值与后端状态码错位 | `backend/templates/admin/reports.html` | 状态过滤 `value` 从 `2/3` 改为 `1/2`；统计与状态文本同步修改 |
| P1-2 | Ruff F401 `decimal.Decimal` 未使用导入 | `backend/domain/admin/services/order_service.py` | 当前代码已无该导入；`ruff check backend/` 全绿 |
| P1-3 | `/admin/api/reports` 接口 404 | `backend/domain/admin/routers/admin_reports_router.py` | 新增 `GET /admin/api/reports` 别名路由，返回观察期报告列表 |

---

## 三、P2 风险项修复

| # | 问题 | 修复文件 | 修复说明 |
|---|---|---|---|
| P2-1 | 证书弹窗 `book_count/word_count` 永远显示 0 | `backend/domain/advancement/service.py` | `list_certificates()` / `get_certificate()` 已关联 `Child` 表返回真实累计阅读数据（`total_books_finished`、`total_words_read`） |
| P2-2 | 逾期提醒 `sent_count=0` 时提示"功能暂未实现" | `backend/templates/admin/borrow.html` | 无逾期记录时提示改为"当前无逾期记录" |
| P2-3 | 图书管理 Router 直接 ORM 查询全局统计 | `backend/domain/admin/services/book_service.py`<br>`backend/domain/admin/routers/admin_books_router.py` | 将 `total_books`/`audio_books`/`quiz_books` 统计查询下沉到 `AdminBookService.get_book_stats()`，Router 只负责调用 Service |

---

## 四、P3 架构/体验清理

| # | 问题 | 修复文件 | 修复说明 |
|---|---|---|---|
| P3-1 | `get_dashboard()` Service 重复实现 | `backend/domain/admin/service.py` | 已瘦身成 15 行空类，仅剩 `AdminDashboardService.get_dashboard()`，重复问题自然消除 |
| P3-2 | 证书页面搜索/级别/时间段过滤失效 | `backend/templates/admin/certificates.html` | 表格行设置 `data-level` / `data-period`；级别过滤按真实 `level_name` 动态生成；时间段按 `create_time` 年月生成；删除重复表头 |
| P3-3 | 图书统计基于当前页数量 | `backend/domain/admin/routers/admin_books_router.py`<br>`backend/templates/admin/books.html` | `/admin/api/books` 新增 `stats` 字段（`total_books`/`audio_books`/`quiz_books`）；前端统计基于 `data.total` 和 `data.stats` |

---

## 五、证书接口别名及文档同步

| # | 变更 | 文件 | 说明 |
|---|---|---|---|
| 1 | 新增 `/admin/api/certificates` 别名路由 | `backend/domain/admin/routers/admin_system_router.py` | `GET /admin/api/certificates` 映射到 `AdvancementService.list_certificates()`，与原 `/admin/api/advancement/certificates` 等价 |
| 2 | 更新架构文档路由表 | `ARCHITECTURE.md` | 在路由拆分表中补充证书路径及 `/admin/api/certificates` 别名 |
| 3 | 更新交接文档 | `HANDOFF.md` | 证书列表接口补充别名说明 |
| 4 | 更新检查点文档 | `checkpoint.md` | 证书列表接口补充别名说明 |

---

## 六、复核后新增修复（非阻塞问题）

| # | 问题 | 修复文件 | 修复说明 |
|---|---|---|---|
| 1 | `/admin/api/certificates` 与 `/admin/api/advancement/certificates` 返回格式不一致 | `backend/domain/admin/routers/admin_system_router.py` | 别名路由 `response_model` 改为 `AdminActionResponse`，返回 `{success, message, items, total, page, page_size, has_next}`，与原路径格式一致 |
| 2 | `ARCHITECTURE.md` 路由表存在重复/矛盾行 | `ARCHITECTURE.md` | 删除重复的 `admin_system_router.py` 行，保留含证书别名的一行 |

---

## 七、AdminService 上帝类拆分（本轮复核验证通过）

已从 `backend/domain/admin/service.py` 拆分出 14 个独立 Service：

| 文件 | Service | 负责域 |
|---|---|---|
| `backend/domain/admin/services/venue_service.py` | AdminVenueService | 场馆 |
| `backend/domain/admin/services/teacher_service.py` | AdminTeacherService | 教师 |
| `backend/domain/admin/services/upload_service.py` | UploadService / AdminUploadService | 上传 |
| `backend/domain/admin/services/export_service.py` | AdminExportService | 导出 |
| `backend/domain/admin/services/book_service.py` | AdminBookService | 图书/题库/副本 |
| `backend/domain/admin/services/report_service.py` | AdminReportService | 观察报告/阅读数据 |
| `backend/domain/admin/services/system_service.py` | AdminSystemService | 系统配置/管理员 |
| `backend/domain/admin/services/account_service.py` | AdminAccountService | 账户/认证/押金 |
| `backend/domain/admin/services/message_service.py` | AdminMessageService | 消息/通知 |
| `backend/domain/admin/services/borrow_service.py` | AdminBorrowService | 借阅/预约 |
| `backend/domain/admin/services/order_service.py` | AdminOrderService | 订单 |
| `backend/domain/admin/services/refund_service.py` | AdminRefundService | 退款 |
| `backend/domain/admin/services/user_service.py` | AdminUserService | 用户/孩子 |
| `backend/domain/admin/services/dashboard_service.py` | AdminDashboardService | 仪表盘 |

- `backend/domain/admin/service.py` 已瘦身为 15 行空类（兼容锚点）
- `backend/common/dependencies.py` 已添加全部 `get_admin_xxx_service` 工厂
- 所有 admin router 已改用新的依赖注入
- 无残留 `AdminService` 直接调用

---

## 八、测试验证结果

| 检查项 | 命令 | 结果 |
|---|---|---|
| 静态检查 | `ruff check backend/` | All checks passed |
| 单元测试 | `pytest tests/unit/ -q` | 100 passed |
| BDD 测试 | `behave features/ -q` | 16 features, 138 scenarios passed |
| 接口测试 | `python3 scripts/formal_test_v2.py` | 119/119 (100%) |

### 管理端接口抽查

| 接口 | 状态 | 关键返回 |
|---|---|---|
| `GET /admin/api/certificates` | HTTP 200 ✅ | `success: True, message: 获取证书列表成功, total: 1, items: 1` |
| `GET /admin/api/advancement/certificates` | HTTP 200 ✅ | `success: True, total: 1, items: 1` |
| `GET /admin/api/reports` | HTTP 200 ✅ | 观察期报告列表 |
| `GET /admin/api/reports/observation` | HTTP 200 ✅ | 观察期报告列表 |
| `GET /admin/api/books` | HTTP 200 ✅ | `stats: {total_books: 19, audio_books: 0, quiz_books: 5}` |
| `GET /admin/api/advancement/certificates` | HTTP 200 ✅ | `book_count: 8, word_count: 42000` |

---

## 九、建议专家重点复核项

1. **证书弹窗数据语义**：当前 `book_count`/`word_count` 取的是孩子累计阅读数据，而非"获得该证书时所在级别"的数据。需确认业务上是否接受。
2. **图书全局统计**：`/admin/api/books` 的 `stats` 为全局统计，不随 `keyword` 过滤条件变化。需确认搜索场景下的统计行为。
3. **AdminService 拆分边界**：部分 Service 之间是否仍存在隐式耦合（如共享事件、缓存状态）。
4. **证书别名设计**：`/admin/api/certificates` 仅作为 `/admin/api/advancement/certificates` 的别名，后续新增证书相关接口是否继续保留双路径。
5. **前端过滤性能**：`certificates.html` 的搜索/级别/时间段过滤为前端本地过滤，数据量大时需评估是否改为后端过滤。

---

## 十、已修改文件清单（本轮）

### 后端
- `backend/domain/admin/service.py`
- `backend/domain/admin/services/*.py`（14 个 Service）
- `backend/common/dependencies.py`
- `backend/domain/admin/routers/admin_venues_router.py`
- `backend/domain/admin/routers/admin_teachers_router.py`
- `backend/domain/admin/routers/admin_books_router.py`
- `backend/domain/admin/routers/admin_advancement_router.py`
- `backend/domain/admin/routers/admin_activities_router.py`
- `backend/domain/admin/routers/admin_borrow_router.py`
- `backend/domain/admin/routers/admin_reports_router.py`
- `backend/domain/admin/routers/admin_system_router.py`
- `backend/domain/advancement/service.py`

### 前端模板
- `backend/templates/admin/reports.html`
- `backend/templates/admin/borrow.html`
- `backend/templates/admin/books.html`
- `backend/templates/admin/certificates.html`

### 测试
- `tests/unit/test_teacher_service.py`

### 文档
- `ARCHITECTURE.md`
- `HANDOFF.md`
- `checkpoint.md`
- `deliverables/audit-ready-2026-07-06.md`（本文件）

---

## 十一、运行环境

- 后端启动：`uvicorn backend.main:app --port 8002`
- 管理员账号：`admin / admin123`
- 验证命令：
  ```bash
  ruff check backend/
  pytest tests/unit/ -q
  behave features/ -q
  python3 scripts/formal_test_v2.py
  ```
