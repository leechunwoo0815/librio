# 前端重构回归测试报告

**测试日期**: 2026-07-07  
**测试人员**: QA 工程师（software-qa-engineer）  
**项目路径**: `/Users/litianyu/cc-projects/librio`  
**测试环境**: macOS / Python 3.13 / 后端服务 `http://localhost:8002`（uvicorn）  
**浏览器工具**: agent-browser（Chromium）

---

## 总体结果

- **测试套件**: 4 个关键套件全部通过（ruff 0、pytest 100、behave 138、formal_test_v2 119）。
- **浏览器验证**: 6 个可用管理页面均可正常加载、交互、渲染数据；Console 无报错。
- **最终结论**: **有条件通过**（存在 2 个需修复的问题，详见下方）。

---

## 一、测试套件结果

| 测试套件 | 命令 | 结果 | 通过数 | 失败数 | 备注 |
|---|---|---|---|---|---|
| ruff | `ruff check backend/` | 通过 | - | 0 | All checks passed! |
| pytest | `pytest tests/unit/ -q` | 通过 | 100 | 0 | 5 条 DeprecationWarning（datetime.utcnow），不影响功能 |
| behave | `venv/bin/behave features/ -q` | 通过 | 138 scenarios | 0 | 16 features / 970 steps 全部通过 |
| formal_test_v2 | `venv/bin/python scripts/formal_test_v2.py` | 通过 | 119 | 0 | 通过率 100%；警告 `/book/search` 无需认证即可访问 |

> 说明：环境 PATH 中未找到 `behave`，使用项目虚拟环境 `venv/bin/behave` 执行后通过。

---

## 二、浏览器验证结果（7 个管理页面）

实际管理页面路由前缀为 `/admin/view/`（HTML 模板由 `backend/domain/admin/admin_page_router.py` 提供）。下表按任务要求覆盖 7 个目标路径，并记录关键操作与结果。

| 目标路径 | 实际路由 | 页面标题 | 关键操作 | 实际结果 | 问题 |
|---|---|---|---|---|---|
| `/admin/books` | `/admin/view/books` | 图书管理 | 列表加载、搜索框、分页、新增弹窗、详情弹窗 | 列表加载 18 条图书记录；搜索框、新增弹窗、详情弹窗均存在；`booklistPage` 全局对象可用；详情弹窗可渲染 HTML | **路由/模板不匹配**：`/admin/view/books` 实际渲染 `booklist.html` 并加载 `pages/booklist.js`；`books.html` 与 `books.js` 未被使用 |
| `/admin/booklist` | `/admin/view/booklist` | - | 访问页面 | 返回 `{"detail":"Not Found"}`（HTTP 404） | **页面缺失**：该路由不存在，无法访问 |
| `/admin/orders` | `/admin/view/orders` | 订单管理 | 列表加载、状态筛选、详情弹窗、新建弹窗 | 列表加载 6 条订单；状态筛选（已支付）生效，返回 2 条；详情弹窗、新建弹窗均存在；`ordersPage` 可用 | 无 |
| `/admin/reports` | `/admin/view/reports` | 观察期报告管理 | 列表加载、状态过滤、详情侧滑面板、评语弹窗 | 列表加载 1 条报告；状态筛选下拉存在；详情面板可渲染 HTML；评语弹窗可打开并回显内容；`reportsPage` 可用 | 无 |
| `/admin/borrow` | `/admin/view/borrow` | 扫码借还 | 条码输入、孩子搜索、借阅记录、发送逾期提醒按钮 | 条码输入、孩子搜索、借阅记录区域、逾期提醒按钮均存在；`borrowPage` 可用；`AdminConfirm` 弹窗可弹出 | **AdminConfirm 取消仍执行回调**：点击“发送逾期提醒”后点取消，Console 显示仍发起了 `POST /admin/api/borrows/send-overdue-reminders` 请求 |
| `/admin/activities` | `/admin/view/activities` | 活动管理 | 列表加载、编辑/新建弹窗 | 列表加载 8 条活动；新建弹窗可正常打开；签到管理弹窗存在；`activitiesPage` 可用 | 无 |
| `/admin/levels` | `/admin/view/levels` | 级别配置 | 等级列表、编辑弹窗 | 列表加载 38 个级别；编辑弹窗可打开并正确回填数据；`levelsPage` 可用 | 无 |

---

## 三、Console 报错清单

在整个浏览器验证过程中，Console 未出现任何 `error` 或 `exception` 级别的日志。仅有以下正常日志：

- 登录流程调试日志（`doLogin`、`请求状态变化` 等）
- `admin.js` 的操作日志：`[nav] page_load`、`[api] GET/POST ...`、`[click] ...`
- 各页面 API 请求成功记录（`✅ GET ...` / `✅ POST ...`）

**未发现 JS 报错。**

---

## 四、资源加载检查

通过 HTML 源码与浏览器 DOM 双重确认，以下页面正确加载了公共组件 `admin-pages.js` 与对应页面 JS：

| 页面 | admin.js | admin-pages.js | pages/*.js | 状态 |
|---|---|---|---|---|
| `/admin/view/books`（实际 booklist） | 已加载 | 已加载 | `pages/booklist.js` | 正常 |
| `/admin/view/orders` | 已加载 | 已加载 | `pages/orders.js` | 正常 |
| `/admin/view/reports` | 已加载 | 已加载 | `pages/reports.js` | 正常 |
| `/admin/view/borrow` | 已加载 | 已加载 | `pages/borrow.js` | 正常 |
| `/admin/view/activities` | 已加载 | 已加载 | `pages/activities.js` | 正常 |
| `/admin/view/levels` | 已加载 | 已加载 | `pages/levels.js` | 正常 |
| `/admin/view/booklist`（404） | - | - | - | 页面不存在，无资源加载 |

另外，使用 `node --check` 对所有 admin JS 文件做语法检查，全部通过：

- `backend/static/admin/js/admin-pages.js`
- `backend/static/admin/js/pages/books.js`
- `backend/static/admin/js/pages/booklist.js`
- `backend/static/admin/js/pages/orders.js`
- `backend/static/admin/js/pages/reports.js`
- `backend/static/admin/js/pages/borrow.js`
- `backend/static/admin/js/pages/activities.js`
- `backend/static/admin/js/pages/levels.js`

---

## 五、AdminConfirm 组件检查

- 所有已验证页面中均可在 `window` 上访问到 `AdminConfirm`（由 `admin-pages.js` 暴露）。
- `admin.js` 中定义的原生 `showConfirm` 已被 `admin-pages.js` 覆盖为使用 `AdminConfirm`。
- `reports` 详情侧滑面板和 `books` 详情弹窗均使用 `innerHTML` 渲染 HTML，正常显示。

---

## 六、发现的问题

### 问题 1：AdminConfirm 取消按钮仍会执行回调（高优先级）

**现象**：在 `/admin/view/borrow` 点击“发送逾期提醒”→ 在 AdminConfirm 弹窗中点击“取消”→ 浏览器仍发起 `POST /admin/api/borrows/send-overdue-reminders` 请求。

**根因**：`admin-pages.js` 中 `AdminConfirm._close(confirmed)` 方法在取消时仍然调用 `this._callback(null)`，而调用方（如 `borrow.js`）的回调函数没有判断入参，直接执行业务操作。对使用 `showConfirm(..., callback)` 的所有删除/取消/发送类操作都存在同样风险。

**影响范围**：借阅逾期提醒、图书删除、活动删除/取消、级别删除、订单关闭/退款等所有依赖确认弹窗的操作。

**建议**：修复 `AdminConfirm._close` 方法，仅在 `confirmed === true` 时调用 `_callback`；若需兼容取消分支，可改为 `this._callback(confirmed, value)` 并让调用方判断第一个参数。

### 问题 2：图书管理页面路由与模板不匹配（中优先级）

**现象**：
- `/admin/view/booklist` 返回 404。
- `/admin/view/books` 实际渲染的是 `booklist.html`，加载的是 `pages/booklist.js`。
- `backend/templates/admin/books.html` 与 `backend/static/admin/js/pages/books.js` 存在但未被任何路由引用。

**影响**：任务要求验证的 `/admin/booklist` 页面无法访问；`books.js` 外迁后并未被实际使用，存在资源浪费与维护歧义。

**建议**：确认产品意图后二选一：
1. 保留 `/admin/view/books` 为图书列表，新增 `/admin/view/booklist` 或其他独立路由；或
2. 明确废弃 `books.html`/`books.js`，将其从代码库中移除，避免误导。

---

## 七、最终结论

| 维度 | 结论 |
|---|---|
| 后端测试套件 | 通过 |
| JS 语法 | 通过 |
| 页面加载与数据渲染 | 通过 |
| 关键交互（弹窗、筛选、详情） | 通过 |
| Console 报错 | 无 |
| AdminConfirm 可用性 | 可用，但存在取消仍执行的 bug |
| 路由/模板一致性 | 存在 `/admin/view/booklist` 404 与 `books.js` 未使用问题 |

**综合判定：有条件通过**

建议在修复以下两个问题后重新验证：
1. `AdminConfirm` 取消按钮不应执行回调；
2. 明确 `/admin/view/books` 与 `/admin/view/booklist` 的路由与模板对应关系，移除未使用的 `books.html`/`books.js` 或补齐路由。
