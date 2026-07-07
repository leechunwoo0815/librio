# P1/P2 修复后全量测试审计报告

- **测试日期**: 2026-07-06
- **测试人员**: Edward（QA Engineer）
- **项目路径**: `/Users/litianyu/cc-projects/librio`
- **测试环境**:
  - 操作系统: macOS 26.5.1
  - Python: 3.13.2
  - MySQL: 9.6.0 (Homebrew, 本地)
  - 后端服务: `uvicorn backend.main:app --host 0.0.0.0 --port 8002`
  - 服务端口: 8002
- **测试范围**: 单元测试、BDD 测试、Ruff 静态检查、formal_test_v2 接口测试、P1/P2 相关接口回归抽查、后端启动日志检查

---

## 总体结果

| 检查项 | 结果 | 备注 |
|--------|------|------|
| 后端服务可启动 | 通过 | 端口 8002 已启动，健康检查 `/health` 返回 200 |
| 单元测试 | 100/100 通过 | 无失败 |
| BDD 测试 | 138/138 通过 | 无失败 |
| Ruff 静态检查 | 1 处错误 | 源码级别问题，需修复 |
| formal_test_v2 | 119/119 通过 | 无失败，但存在 1 条安全警告 |
| P1/P2 接口抽查 | 部分通过 | 2 个示例端点返回 404 |
| 后端日志报错 | 无 | 无 500/Unhandled Exception |
| 新增 500 错误 | 无 | 未观察到 |

**结论：有条件通过 / 需工程师修复后复测**。动态测试全部通过，但静态检查未清零，且架构文档中声明的管理端 `/admin/api/reports` 接口实际缺失。

---

## 1. 测试套件详细结果

### 1.1 pytest 单元测试

| 命令 | 通过 | 失败 | 失败列表 | 结论 |
|------|------|------|----------|------|
| `pytest tests/unit/ -q` | 100 | 0 | — | 通过 |

- 运行日志: `deliverables/audit-2026-07-06/pytest.log`
- 耗时: 约 1.62 秒
- 仅有 6 个 DeprecationWarning（Starlette/httpx、SQLAlchemy `utcnow`），不影响功能。

### 1.2 behave BDD 测试

| 命令 | 通过 | 失败 | 失败列表 | 结论 |
|------|------|------|----------|------|
| `behave features/ -q` | 138 个场景 | 0 | — | 通过 |

- 运行日志: `deliverables/audit-2026-07-06/behave.log`
- 16 个 feature、970 个 step 全部通过，耗时约 1.9 秒。

### 1.3 Ruff 静态检查

| 命令 | 通过 | 失败 | 失败列表 | 结论 |
|------|------|------|----------|------|
| `ruff check backend/` | 0 | 1 | `backend/domain/admin/services/order_service.py:6:21` F401 `decimal.Decimal` 未使用 | **不通过** |

- 运行日志: `deliverables/audit-2026-07-06/ruff.log`
- 该错误为**源码级别**问题，可直接用 `--fix` 自动修复。

### 1.4 formal_test_v2 接口测试

| 命令 | 通过 | 失败 | 失败列表 | 结论 |
|------|------|------|----------|------|
| `python scripts/formal_test_v2.py` | 119 | 0 | — | 通过 |

- 运行日志: `deliverables/audit-2026-07-06/formal_test.log`
- 详细结果 JSON: `scripts/test_results_v2.json`
- 警告：
  - `/book/search` 无需认证即可访问。此行为需根据产品安全策略判断是否接受，本次仅记录，不计入失败。
- 注意：该脚本对管理端 API 列表（如 `/admin/api/reports`）的判定逻辑为“状态码 < 500 即通过”，因此 404 不会被标记为失败。详见下方回归抽查。

---

## 2. 回归抽查结果

本次抽查了任务中提到的 5 个 P1/P2 相关接口。后端运行正常，但有两个示例端点实际不存在或路径与架构文档不一致。

| 接口 | 请求方式 | 状态码 | 关键字段/说明 | 结论 |
|------|----------|--------|---------------|------|
| `/admin/api/dashboard` | GET | 200 | `total_users`、`total_children`、`total_orders`、`total_revenue`、`daily_active_users` | 正常 |
| `/admin/api/books?page=1&page_size=1` | GET | 200 | `items`（含 `id`、`isbn`、`title`、`author`、`ar_value` 等） | 正常 |
| `/admin/api/certificates?page=1&page_size=1` | GET | 404 | `{"detail": "Not Found"}` | **异常**（实际页面调用的是 `/admin/api/advancement/certificates`） |
| `/admin/api/reports?page=1&page_size=1` | GET | 404 | `{"detail": "Not Found"}` | **异常**（`ARCHITECTURE.md` 声明存在 `/admin/api/reports`，实际仅有 `/admin/api/reports/observation`） |
| `/book/search?page=1&page_size=1` | GET | 200 | `items`（含 `id`、`title`、`author`、`ar_value` 等） | 正常 |

为确认管理能力，进一步抽查了实际被前端页面调用的对应端点：

| 接口 | 状态码 | 关键字段 | 结论 |
|------|--------|----------|------|
| `/admin/api/advancement/certificates` | 200 | `success`、`items`（含 `child_name`、`level_name`、`certificate_no`） | 正常 |
| `/admin/api/reports/observation` | 200 | `items`（含 `child_name`、`total_reading_minutes`、`total_books_read`） | 正常 |

**说明**：
- `/admin/api/certificates` 与 `/admin/api/reports` 返回 404 是**后端路由未注册**导致，非测试脚本问题。
- `/admin/api/reports` 在 `ARCHITECTURE.md` 中被列为 `admin_reports_router` 的前缀之一，但 `backend/domain/admin/routers/admin_reports_router.py` 中只注册了 `/admin/api/reports/observation`、`/admin/api/reports/observation/generate`、`/admin/api/reports/observation/{report_id}/comment`，缺少 `/admin/api/reports` 本身。

---

## 3. 后端启动日志检查

- 日志文件: `deliverables/audit-2026-07-06/backend.log`
- 启动结果：无报错，启动成功
- 检查项：
  - `ERROR` / `Unhandled exception` / `Traceback`：无
  - `HTTP/1.1" 5xx` 响应：无
- 调度器成功启动，生命周期事件正常。

---

## 4. 路由判定

### 4.1 Ruff F401 错误

- **判定责任方**: Engineer（Alex）
- **原因**: `backend/domain/admin/services/order_service.py` 中导入了 `decimal.Decimal` 但未使用，属于源码问题，测试脚本和配置均正确。
- **修复建议**: 删除该未使用导入，或运行 `ruff check backend/ --fix`。

### 4.2 `/admin/api/reports` 返回 404

- **判定责任方**: Engineer（Alex）
- **原因**: 架构文档中声明该端点存在，但路由文件未注册根路径 `/admin/api/reports`（仅注册了子路径）。属于源码实现与架构设计不一致。
- **修复建议**: 在 `admin_reports_router.py` 中补充 `/admin/api/reports` 的汇总列表接口，或更新架构文档（若该端点已废弃）。

### 4.3 `/admin/api/certificates` 返回 404

- **判定责任方**: Engineer（Alex）
- **原因**: 前端证书管理页面调用的是 `/admin/api/advancement/certificates`，因此该 404 路径本身可能为示例路径。但如果任务期望该路径存在，则同样属于后端路由缺失。建议与产品经理确认是否需要在 `/admin/api/certificates` 增加别名或统一入口。

### 4.4 动态测试全部通过

- **判定责任方**: NoOne
- 单元测试、BDD、formal_test 的断言均与实际输出一致，无需修复。

---

## 5. 最终结论

| 维度 | 状态 |
|------|------|
| 功能正确性（动态测试） | 通过 |
| 代码静态质量（Ruff） | **不通过**（1 处未使用导入） |
| 架构/接口一致性 | **不通过**（`/admin/api/reports` 缺失） |
| 服务稳定性 | 通过 |

**最终结论：有条件通过 / 需修复后复测**

建议在工程师修复以下问题后重新执行 `ruff check backend/` 并对 `/admin/api/reports` 与 `/admin/api/certificates` 进行回归抽查：

1. 修复 `backend/domain/admin/services/order_service.py` 中未使用的 `decimal.Decimal` 导入。
2. 根据 `ARCHITECTURE.md` 补充 `/admin/api/reports` 路由，或确认并更新架构文档。
3. 确认 `/admin/api/certificates` 是否为需要保留的端点；如不需要，请在任务描述中明确说明该路径为示例路径。

所有动态测试输出文件已保存至 `deliverables/audit-2026-07-06/`。
