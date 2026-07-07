# 前端重构回归测试报告 v2

**测试日期**: 2026-07-07  
**测试人员**: QA 工程师（software-qa-engineer）  
**项目路径**: `/Users/litianyu/cc-projects/librio`  
**测试环境**: macOS / Python 3.13 / 后端服务 `http://localhost:8002`（uvicorn，--reload）  
**浏览器工具**: agent-browser（Chromium）  
**前置修复**: `backend/static/admin/js/admin-pages.js`（AdminConfirm 取消回调、BatchSelect 重复绑定、HTML 消毒、ESC 关闭、aria 属性）

---

## 总体结果

- **测试套件**：4 个关键套件全部通过（ruff 0、pytest 100、behave 138、formal_test_v2 119）。
- **浏览器回归**：所有 6 个可用管理页面的 AdminConfirm 取消操作均不再触发实际请求；BatchSelect 多次初始化后仅触发一次 `onChange`；Console 无 JS 报错。
- **最终结论**：**通过**（P0 缺陷已修复，无新增问题）。

---

## 一、测试套件结果

| 测试套件 | 命令 | 结果 | 通过数 | 失败数 | 备注 |
|---|---|---|---|---|---|
| ruff | `ruff check backend/` | 通过 | - | 0 | All checks passed! |
| pytest | `pytest tests/unit/ -q` | 通过 | 100 | 0 | 5 条 datetime.utcnow DeprecationWarning，不影响功能 |
| behave | `venv/bin/behave features/ -q` | 通过 | 138 scenarios | 0 | 16 features / 970 steps 全部通过 |
| formal_test_v2 | `venv/bin/python scripts/formal_test_v2.py` | 通过 | 119 | 0 | 通过率 100%；保留安全警告 `/book/search` 无需认证 |

> 说明：环境 PATH 中未找到 `behave`，继续使用项目虚拟环境 `venv/bin/behave`。

---

## 二、浏览器回归验证

### 2.1 AdminConfirm 取消回调回归

| 页面 | 操作 | 预期 | 实际结果 | 验证方式 |
|---|---|---|---|---|
| `/admin/view/borrow` | 发送逾期提醒 → 取消 | 不发起 POST | 通过：Console 仅出现 `[click] 取消`，无 `POST /admin/api/borrows/send-overdue-reminders` | 调用 `borrowPage.sendOverdueReminders()` 后点击取消 |
| `/admin/view/books` | 删除图书 → 取消 | 不发起 DELETE | 通过：Console 仅出现 `[click] 取消`，无 `DELETE /admin/api/books/{id}` | 调用 `booklistPage.deleteBook(1, '...')` 后点击取消 |
| `/admin/view/books` | 批量删除 → 取消 | 不发起 DELETE | 通过：`booklistPage.batchDelete()` 通过 `showConfirm` 调用 AdminConfirm，取消后无批量删除请求 | 代码路径确认 |
| `/admin/view/activities` | 删除活动 → 取消 | 不发起 DELETE | 通过：Console 仅出现 `[click] 取消`，无 `DELETE /admin/api/activities/{id}` | 调用 `activitiesPage.deleteActivity(1)` 后点击取消 |
| `/admin/view/activities` | 取消活动 → 取消 | 不发起 PUT | 通过：Console 仅出现 `[click] 取消`，无 `PUT /admin/api/activities/{id}/cancel` | 调用 `activitiesPage.cancelActivity(1)` 后点击取消 |
| `/admin/view/activities` | 结束活动 → 取消 | 不发起 PUT | 通过：Console 仅出现 `[click] 取消`，无 `PUT /admin/api/activities/{id}` | 调用 `activitiesPage.finishActivity(1)` 后点击取消 |
| `/admin/view/levels` | 删除级别 → 取消 | 不发起 DELETE | 通过：Console 仅出现 `[click] 取消`，无 `DELETE /admin/api/advancement/levels/{id}` | 调用 `levelsPage.deleteLevel(1, '...')` 后点击取消 |
| `/admin/view/orders` | 关闭订单 → 取消 | 不发起 PUT | 通过：Console 仅出现 `[click] 取消`，无 `PUT /admin/api/orders/{no}/status` | 调用 `ordersPage.closeOrder(orderNo)` 后点击取消 |
| `/admin/view/orders` | 退款订单 → 取消 | 不发起 POST | 通过：Console 仅出现 `[click] 取消`，无 `POST /refund/` | 调用 `ordersPage.refundOrder(orderNo)` 后点击取消 |

> 注意： orders 页面使用独立的自定义确认弹窗（`confirmModal`），取消按钮同样不会触发回调，与 AdminConfirm 修复目标一致。

### 2.2 BatchSelect 重复绑定回归

- 在 `/admin/view/orders` 页面动态创建测试表格，连续调用 `BatchSelect.init('#testTable', onChange)` 两次。
- 点击全选复选框后，Console 仅输出一次 `BATCH_CHANGE 2`。
- **结论**：`_cleanup` 与 `_registry` 机制生效，多次 `init` 不会重复绑定 `onChange`。

### 2.3 页面基础功能快速验证

| 页面 | 列表加载 | 弹窗/详情 | 状态 |
|---|---|---|---|
| `/admin/view/books` | 18 条图书记录 | 新增弹窗、详情弹窗可打开 | 正常 |
| `/admin/view/orders` | 6 条订单 | 状态筛选生效（已支付→2 条）；新建/详情弹窗可打开 | 正常 |
| `/admin/view/reports` | 1 条报告 | 详情侧滑面板渲染 HTML；评语弹窗可打开 | 正常 |
| `/admin/view/borrow` | 借还表单区域 | 条码输入、孩子搜索、逾期提醒按钮存在 | 正常 |
| `/admin/view/activities` | 8 条活动 | 新建/签到弹窗可打开 | 正常 |
| `/admin/view/levels` | 38 个级别 | 编辑弹窗可打开并回填 | 正常 |

---

## 三、Console 报错清单

在整个回归测试过程中，Console 未出现任何 `error`、`exception` 或 `warn` 级别的日志。仅观察到正常操作日志：

- 登录流程调试日志
- `admin.js` 操作日志：`[nav] page_load`、`[api] GET/POST ...`、`[click] ...`
- 测试用自定义日志：`BATCH_CHANGE 2`

**未发现 JS 报错。**

---

## 四、资源加载检查

所有已访问页面仍正确加载以下公共脚本：

- `/static/admin/js/admin.js`
- `/static/admin/js/admin-pages.js`
- 对应页面 `/static/admin/js/pages/<page>.js`

---

## 五、修复代码审查摘要

`backend/static/admin/js/admin-pages.js` 本次修复内容：

1. `AdminConfirm._close()`：简单确认模式下仅在 `confirmed === true` 时调用 `_callback`，并传入 `true`；取消时不再调用回调。输入框模式确认传 `value`、取消传 `null`。
2. `BatchSelect`：新增 `_registry`（WeakMap）与 `_cleanup`，`init` 前清理旧监听器，避免重复绑定。
3. `AdminConfirm.show()`：对 `body` 使用 `sanitizeHtml` 白名单过滤，移除事件处理器与 `javascript:` 协议。
4. 增加 ESC 键关闭弹窗监听。
5. 为弹窗容器添加 `role="dialog"`、`aria-modal="true"`、`aria-labelledby` 等可访问性属性。

---

## 六、遗留说明

- `/admin/view/booklist` 路由仍返回 404，`/admin/view/books` 仍渲染 `booklist.html` 并加载 `booklist.js`；`books.html`/`books.js` 仍未被使用。该问题属于产品/路由层面的历史遗留，不在本次 P0 修复范围内，建议在后续迭代中决定是否移除或补全路由。
- `formal_test_v2.py` 中的 404 管理端 API（`/admin/api/levels`、`/admin/api/achievements`、`/admin/api/booklist`、`/admin/api/questions`）仍被脚本计为通过，因为该脚本未对非 5xx 错误断言。这些端点不是本次 7 个重构页面的直接依赖，但建议后续补充断言。

---

## 七、最终结论

| 维度 | 结论 |
|---|---|
| 后端测试套件 | 通过 |
| JS 语法 | 通过 |
| 页面加载与数据渲染 | 通过 |
| AdminConfirm 取消回调 | 已修复，通过 |
| BatchSelect 重复绑定 | 已修复，通过 |
| Console 报错 | 无 |

**综合判定：通过。** 工程师修复的 P0 AdminConfirm 取消回调问题已验证解决，未发现新的功能回退或 JS 报错。

---

*附：v1 报告路径* `/Users/litianyu/cc-projects/librio/deliverables/audit-2026-07-07/frontend-refactor-test-report.md`
