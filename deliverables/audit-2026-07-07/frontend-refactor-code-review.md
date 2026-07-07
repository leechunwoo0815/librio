# MegaWords (librio) 管理后台前端重构代码审查报告

- **审查日期**：2026-07-07
- **审查范围**：
  - 公共组件：`backend/static/admin/js/admin-pages.js`
  - 已迁移的 7 个核心页面：`books / booklist / orders / reports / borrow / activities / levels`
  - 共享脚本：`backend/static/admin/js/admin.js`
  - 全部 `backend/templates/admin/*.html`（共 32 个模板）
- **审查人**：software-engineer

## 总体结论

本次重构在“把页面 JS 外迁到独立文件”这一表象目标上基本完成：7 个核心页面模板中均已删除内联 `<script>` 块，页面脚本改为通过 `{% block scripts %}` 加载。但公共组件 `AdminConfirm` 存在一个 **P0 级回归缺陷**：点击“取消”时仍会执行业务回调，导致所有基于 `showConfirm` / `AdminConfirm.show` 的确认对话框形同虚设。该问题影响全部 7 个已迁移页面中的 6 个，以及若干尚未迁移的页面。

此外，重构未充分利用已抽取的公共组件（`AdminTable`、`AdminPagination`、`BatchSelect` 均未被核心页面使用），页面中仍残留大量内联 `onclick` 处理器，且 `backend/static/admin/js/admin.js` 与多个非核心模板中仍有原生 `confirm` / `alert` 调用。建议在修复 P0 缺陷后，统一弹窗 API、推广公共组件，并制定剩余模板的迁移优先级。

## 问题分级统计

| 级别 | 含义 | 数量 | 代表问题 |
|------|------|------|----------|
| P0 | 功能回归 / 安全漏洞，必须立即修复 | 2 | 确认弹窗取消仍执行回调；草稿恢复在取消时触发 |
| P1 | 明显缺陷 / 兼容性问题 / 可维护性风险 | 10 | XSS 注入面、BatchSelect 重复监听、大量内联事件、原生弹窗残留 |
| P2 | 局部设计/实现问题，建议返工 | 14 | 公共组件未使用、死代码、业务逻辑错误、事件处理不一致 |
| P3 | 风格/规范类建议 | 6 | 缺少焦点管理、ES5/ES6 混用、硬编码样式等 |

---

## 一、公共组件审查

### 1.1 设计评价

`admin-pages.js` 采用 IIFE 将组件挂载到全局对象，符合当前项目“无构建工具”的技术栈：

- **AdminConfirm**：单例弹窗，支持纯确认与带输入框两种模式，DOM 在首次使用时惰性创建。
- **AdminTable / AdminPagination**：提供通用表格加载、分页渲染能力，但本次迁移的 7 个页面均未使用。
- **AdminModal**：仅做 `display` 切换，功能极简。
- **BatchSelect**：提供表头全选、行复选框联动及 `onChange` 回调。
- 兼容层：重写全局 `showConfirm`，保持多参数调用签名，意图让旧页面平滑过渡。

整体方向正确，但 API 一致性、事件清理、向后兼容性存在明显问题。

### 1.2 问题清单

| 级别 | 位置 | 问题描述 | 影响 |
|------|------|----------|------|
| P0 | `admin-pages.js:54-62` `_close()` | 无论用户点击“确认”还是“取消”，都会调用 `_callback`。简单确认模式下，取消会回调 `null`，导致所有把回调直接当“确认执行”的调用方都会**在取消时执行业务逻辑**。 | 全部使用 `showConfirm` / `AdminConfirm.show` 的页面 |
| P0 | `admin-pages.js:82-83` `show()` | `bodyEl.innerHTML = body` 直接写入 HTML；若调用方未转义，会导致 XSS。组件本身未做消毒。 | 所有调用 AdminConfirm 显示动态内容的地方 |
| P1 | `admin-pages.js:244-246` `global.showConfirm` | 与原 `admin.js` 的 `showConfirm` 行为不一致：原实现仅在确认时调用 callback，新包装始终调用；且回调参数为 `''`/`null` 而非无参/布尔值。 | 旧页面（teachers/settings/venues/bookcopy/assessments 等）的确认语义 |
| P1 | `admin-pages.js:196-234` `BatchSelect` | `init()` 每次调用都会给 `.select-all` 重新绑定 `change` 事件；在 `books.js` 中每次渲染后都会再次调用，导致监听器堆积、`onChange` 重复触发。 | `books.html` 批量选择 |
| P2 | `admin-pages.js:94-183` | `AdminTable` / `AdminPagination` 已抽取，但 7 个核心页面全部自己实现了表格加载与分页，公共组件未被使用。 | 代码重复、迁移收益降低 |
| P2 | `admin-pages.js:185-194` `AdminModal` | 仅切换 `display`，缺少 ESC 关闭、焦点管理、`aria-*` 属性，可访问性差。 | 所有使用 AdminModal 的场景 |
| P3 | `admin-pages.js:18` 等 | 弹窗样式大量硬编码在 `style.cssText` 中，未完全复用项目 CSS 变量，后续主题切换困难。 | 可维护性 |
| P3 | `admin-pages.js:35-42` | 没有 `destroy()` / `remove()` 方法，页面卸载时 DOM 与监听不会释放。 | 内存管理（当前非 SPA，影响较小） |

---

## 二、7 个核心页面外迁审查

### 2.1 books.html / books.js

| 检查项 | 结论 | 说明 |
|--------|------|------|
| 内联 `<script>` 块 | 已移除 | 仅保留 `<script src="/static/admin/js/pages/books.js">` |
| 内联事件处理器 | 仍存在 9 处 | 全部改为 `window.booksPage.*`，如 `onclick="window.booksPage.openAddModal()"` |
| 公共组件引用 | 使用 `AdminConfirm.show`、`BatchSelect` | 未使用 `AdminTable` / `AdminPagination` |
| 加载顺序 | 正确 | `admin.js` → `admin-pages.js` → `books.js` |

**问题清单：**

- **P0** `books.js:167-178` `restoreDraft()`：调用 `AdminConfirm.show('恢复草稿', ..., restoreFn)`。由于 `_close()` 在取消时仍回调 `null`，即使用户点“取消”也会触发草稿恢复。
- **P0** `books.js:219-229` `deleteBook()`、`books.js:236-250` `batchDelete()`、`books.js:205-217` `togglePublish()`：均使用 `AdminConfirm.show`，点击取消仍会执行删除/下架。
- **P1** `books.js:93-97`：每次 `renderBooks()` 后重复调用 `BatchSelect.init('#booksTable', ...)`，造成 `select-all` 监听器堆积。
- **P2** `books.js:33-43` `loadBooks()`：AR/年龄下拉框无 `id` 与事件绑定，筛选功能未生效。
- **P2** `books.js:50-98` `renderBooks()`：未使用 `AdminTable`，自行拼接 HTML、维护分页信息。
- **P3** `books.js:63-91`：行内操作链接仍通过字符串拼接生成 `onclick="window.booksPage.viewBook('${b.id}')"`，可维护性一般。

### 2.2 booklist.html / booklist.js

| 检查项 | 结论 | 说明 |
|--------|------|------|
| 内联 `<script>` 块 | 已移除 | 仅保留页面 JS 引用 |
| 内联事件处理器 | 仍存在 11 处 |  toolbar、批量操作栏、弹窗关闭按钮等 |
| 公共组件引用 | 使用全局 `showConfirm` | 未使用 `BatchSelect`、`AdminTable` |
| 加载顺序 | 正确 | 在 base 脚本之后加载 |

**问题清单：**

- **P0** `booklist.js:184-194` `deleteBook()`、`booklist.js:211-221` `batchDelete()`：使用 `showConfirm(..., async function(){...})`，取消时仍会回调并删除数据。
- **P2** `booklist.js:251-277`：页面保留了 `#confirmModal` 弹窗 HTML，但仅暴露 `closeConfirmModal()`，`#confirmBtn` 未绑定事件，实际使用 `showConfirm` 弹窗，属于死代码。
- **P2** `booklist.js:54`：行内复选框使用 `onchange="window.booklistPage.updateBatchBar()"`，未复用 `BatchSelect`。
- **P2** `booklist.js:36` `updateStats()`：测验题数量统计错误地使用了 `b.has_audio`（应为 `question_count` 或类似字段）。
- **P2** `booklist.js:50`：分页区 `paginationPages` 始终为空，未实现分页。

### 2.3 orders.html / orders.js

| 检查项 | 结论 | 说明 |
|--------|------|------|
| 内联 `<script>` 块 | 已移除 | 仅保留页面 JS 引用 |
| 内联事件处理器 | 仍存在 8 处 | 查询、导出、新建、弹窗关闭等 |
| 公共组件引用 | 未使用 | 完全自定义 `#confirmModal` / `#detailModal` |
| 加载顺序 | 正确 | 在 base 脚本之后加载 |

**问题清单：**

- **P1** `orders.js:15-39`：自定义确认弹窗 `#confirmBtn` 的监听在 `DOMContentLoaded` 中只绑定一次；`hideConfirm()` 会清空回调，逻辑正确，但与 `AdminConfirm` 不统一。
- **P2** `orders.js:234-252` `editOrder()`：先调用 `showOrderConfirm(...)` 再直接修改弹窗 DOM，导致同一弹窗状态被复用，容易在并发/快速操作时残留旧状态。
- **P2** `orders.js:64-69` `searchChildrenForOrder()`：下拉项 HTML 拼接中孩子姓名等已 `escapeHtml`，但手机号、家长姓名为纯文本拼接，若后端返回恶意内容仍有注入风险（应统一转义）。
- **P2** `orders.js:131-152` `renderOrders()`：未对 `o.order_no` 做 `escapeHtml`（虽然通常是数字，但建议统一）。
- **P2** `orders.js:154-165` `renderPagination()`：仅渲染页码，无上一页/下一页。

### 2.4 reports.html / reports.js

| 检查项 | 结论 | 说明 |
|--------|------|------|
| 内联 `<script>` 块 | 已移除 | 仅保留页面 JS 引用 |
| 内联事件处理器 | 仍存在 7 处 | 查询、刷新、面板关闭、评语保存等 |
| 公共组件引用 | 未使用 | 无确认弹窗需求 |
| 加载顺序 | 正确 | 在 base 脚本之后加载 |

**问题清单：**

- **P1** `reports.html:20-29`：工具栏按钮仍使用内联 `onclick`。
- **P2** `reports.js:27-28` `updateStats()`：`statPassRate` 被设置为“平均阅读时长（分钟）”，命名与含义不符。
- **P2** `reports.js:31-59` `renderReports()`：前端按状态过滤会覆盖服务端分页，若数据量大需后端分页。
- **P2** `reports.js:61-91` `openPanel()`：侧边栏展开依赖 `.show` / `.open` 类，需确认对应 CSS 已定义。

### 2.5 borrow.html / borrow.js

| 检查项 | 结论 | 说明 |
|--------|------|------|
| 内联 `<script>` 块 | 已移除 | 仅保留页面 JS 引用 |
| 内联事件处理器 | 仍存在 5 处 | 查找、借出、归还、发送逾期提醒等 |
| 公共组件引用 | 使用全局 `showConfirm` | 仅用于发送逾期提醒 |
| 加载顺序 | 正确 | 在 base 脚本之后加载 |

**问题清单：**

- **P0** `borrow.js:151-165` `sendOverdueReminders()`：使用 `showConfirm(...)`，取消时仍会发送提醒。
- **P2** `borrow.html:58`："标记丢失"按钮无 `onclick` 绑定，功能缺失。
- **P2** `borrow.js:74-95` `lookupBarcode()`：通过 `/admin/api/books?keyword=barcode` 查询并取第一条，未使用馆藏副本接口，逻辑可能不准确。
- **P2** `borrow.js:42-53` `searchChildren()`：孩子下拉项拼接使用字符串内联 `onclick`，且 `c.name` 仅做了 `replace(/'/g, "\\'")`，未处理 `"` 与 `\`。
- **P2** `borrow.js:133-148` `loadRecords()`：初始页面未加载记录，仅在孩子借/还后加载。

### 2.6 activities.html / activities.js

| 检查项 | 结论 | 说明 |
|--------|------|------|
| 内联 `<script>` 块 | 已移除 | 仅保留页面 JS 引用 |
| 内联事件处理器 | 仍存在 7 处 | 创建、编辑、签到、弹窗关闭等 |
| 公共组件引用 | 使用全局 `showConfirm` | 无 `AdminConfirm` 直接调用 |
| 加载顺序 | 正确 | 在 base 脚本之后加载 |

**问题清单：**

- **P0** `activities.js:141-179` `publishActivity` / `cancelActivity` / `finishActivity` / `deleteActivity`：均使用 `showConfirm`，取消仍会执行。
- **P2** `activities.html:67-76`：页面存在 `#confirmModal` 弹窗，但取消按钮 `onclick="hideConfirm()"` 未定义；该弹窗实际未被使用，为死代码。
- **P2** `activities.js:194-202` `showSigninModal()`：签到列表项通过字符串拼接生成，姓名已转义，但结构较脆弱。
- **P3** `activities.js:18-20` `onTypeChange()` 为空函数，仅作预留。

### 2.7 levels.html / levels.js

| 检查项 | 结论 | 说明 |
|--------|------|------|
| 内联 `<script>` 块 | 已移除 | 仅保留页面 JS 引用 |
| 内联事件处理器 | 仍存在 7 处 | 刷新、导入/导出、编辑/删除、保存调整等 |
| 公共组件引用 | 使用全局 `showConfirm`、`exportCSV` | 未使用表格组件 |
| 加载顺序 | 正确 | 在 base 脚本之后加载 |

**问题清单：**

- **P0** `levels.js:70-80` `deleteLevel()`：使用 `showConfirm`，取消仍会删除。
- **P2** `levels.js:124-133` `saveAdjustment()`：仅弹出 `showToast('调整已保存（本地配置）')`，未调用后端接口，属于功能 stub。
- **P2** `levels.js:54-68` `editLevel()`：编辑按钮的 `onclick` 把级别名称直接嵌入属性，仅 `escapeHtml` 未处理 `"` / `\` / backtick，特殊字符会破坏属性解析。
- **P2** `levels.js:158-193` `handleImport()`：CSV 解析按简单逗号切分，不支持含逗号或引号的字段；`try { ... } catch { failed++ }` 会吞掉所有异常。
- **P2** `levels.js:105-107`：`pass_rate` 从百分比除以 100，但需确认后端字段 `required_quiz_pass_rate` 的存储单位，避免二次除法。

---

## 三、原生弹窗残留扫描

### 3.1 已迁移页面（7 个核心页面）

经扫描，7 个核心页面的 JS 文件中已无原生 `confirm` / `alert` / `prompt` 调用。

### 3.2 共享脚本

| 文件 | 行号 | 类型 | 代码片段 |
|------|------|------|----------|
| `admin.js` | 153 | `confirm` | `if (window.confirm(fullMsg) && cb) cb();` |
| `admin.js` | 157 | `prompt` | `const input = window.prompt(...)` |
| `admin.js` | 160 | `confirm` | `if (window.confirm(title ? ... : msg)) { ... }` |
| `admin.js` | 313 | `confirm` | `if (!confirm(\`确定删除选中的 ${ids.length} 项？\`)) return;` |

### 3.3 未迁移模板

| 文件 | 行号 | 类型 | 说明 |
|------|------|------|------|
| `certificates.html` | 218 | `confirm` | 重新生成证书确认 |
| `recycle_bin.html` | 113 | `confirm` | 恢复记录确认 |
| `questions.html` | 248 | `confirm` | 删除题目确认 |
| `dictionary.html` | 150 | `confirm` | 删除单词确认 |
| `audio.html` | 139 | `confirm` | 删除音频确认 |
| `reservation.html` | 108 | `confirm` | 取书确认 |
| `reservation.html` | 119 | `confirm` | 取消预约确认 |
| `assessments.html` | 321 | `confirm` | 删除评估记录确认 |
| `achievements.html` | 301 | `confirm` | 删除徽章确认 |
| `deposit.html` | 109 | `confirm` | 审核退款确认 |
| `content.html` | 98 | `alert` | 上传页面图片占位 |
| `library.html` | 58 | `alert` | 批量导入占位 |
| `library.html` | 230 | `alert` | 编辑图书占位 |
| `library.html` | 231 | `alert` | 图书详情占位 |
| `login.html` | 46 | `alert` | 登录按钮调试代码 |

### 3.4 使用 `showConfirm` 但未迁移的模板

以下模板已改用新的 `showConfirm` 包装，但因为公共组件存在 P0 取消仍执行的缺陷，同样会受影响：

| 文件 | 行号 | 说明 |
|------|------|------|
| `teachers.html` | 260、292 | 删除老师、查看课表详情 |
| `settings.html` | 296 | 删除管理员 |
| `venues.html` | 243 | 删除场馆 |
| `bookcopy.html` | 153、170 | 副本详情、归还确认 |
| `assessments.html` | 245、252 | 评估详情、安排评估 |

---

## 四、剩余非核心模板迁移建议

`backend/templates/admin` 下共 32 个模板，剔除 7 个已迁移核心页面后，剩余 **25 个**（含 `base.html`、`login.html`）。下表按内联脚本规模、内联事件数量、是否残留原生弹窗给出迁移优先级。

| 优先级 | 模板 | 内联脚本行数 | onclick 数 | 原生弹窗 | 建议 |
|--------|------|--------------|------------|----------|------|
| **高** | `settings.html` | 163 | 9 | 无 | 系统设置/管理员管理，脚本最多，优先拆分 |
| **高** | `teachers.html` | 212 | 6 | 无 | 老师管理，依赖 `showConfirm`，需修复后迁移 |
| **高** | `assessments.html` | 227 | 7 | 1 处 confirm | 评估管理，脚本最多且含原生 confirm |
| **高** | `questions.html` | 174 | 6 | 1 处 confirm | 题库管理，含题目编辑弹窗，逻辑复杂 |
| **高** | `certificates.html` | 170 | 4 | 1 处 confirm | 证书管理，业务关键 |
| **高** | `users.html` | 154 | 5 | 无 | 用户管理，脚本规模大 |
| **高** | `library.html` | 118 | 9 | 3 处 alert | 图书入库，含大量占位 alert，需补全功能 |
| **高** | `deposit.html` | 85 | 7 | 1 处 confirm | 押金/退款审核，财务敏感 |
| **高** | `reservation.html` | 97 | 6 | 2 处 confirm | 预约管理 |
| **高** | `achievements.html` | 203 | 7 | 1 处 confirm | 成就/徽章管理 |
| **中** | `audio.html` | 112 | 3 | 1 处 confirm | 音频管理，规模中等 |
| **中** | `dictionary.html` | 130 | 5 | 1 处 confirm | 词库管理 |
| **中** | `recycle_bin.html` | 110 | 8 | 1 处 confirm | 回收站，恢复/删除逻辑 |
| **中** | `bookcopy.html` | 139 | 6 | 无（已用 showConfirm） | 馆藏管理，条码扫描/归还 |
| **中** | `venues.html` | 159 | 5 | 无（已用 showConfirm） | 场馆管理 |
| **中** | `content.html` | 41 | 17 | 1 处 alert | 内容/页面/音频上传，onclick 最多但脚本少，可顺手迁移 |
| **中** | `quiz.html` | 95 | 2 | 无 | 出卷管理 |
| **中** | `message_manage.html` | 118 | 0 | 无 | 消息管理，无内联事件但脚本较多 |
| **中** | `reading_data.html` | 80 | 4 | 无 | 阅读数据统计 |
| **中** | `operation_logs.html` | 95 | 5 | 无 | 操作日志查询/导出 |
| **中** | `profile.html` | 91 | 0 | 无 | 个人名片 |
| **中** | `submissions.html` | 82 | 6 | 无 | 审核队列 |
| **中** | `activity_checkin.html` | 100 | 2 | 无 | 活动签到 |
| **低** | `login.html` | 110 | 2 | 1 处 alert | 登录页独立布局，alert 为调试代码，建议顺手清理 |
| **低** | `base.html` | 124 | 4 | 无 | 布局模板，保留少量内联脚本（侧边栏权限、骨架屏、CSV 导出），可待后续统一 |
| **低** | `dashboard.html` | 20 | 0 | 无 | 数据概览，脚本极少，最后迁移 |

### 4.1 迁移顺序建议

1. **第一批（1-2 周）**：`settings`、`teachers`、`assessments`、`questions`、`certificates`、`users`、`deposit`。
   - 这些模板脚本量大或业务关键，迁移收益最高。
   - 迁移前必须先修复 `AdminConfirm` 的 P0 取消回调问题。
2. **第二批（2-3 周）**：`library`、`reservation`、`achievements`、`audio`、`dictionary`、`recycle_bin`、`bookcopy`、`venues`、`content`。
   - 中等复杂度，迁移过程中顺带替换原生 `confirm`/`alert`。
3. **第三批（按需）**：`quiz`、`message_manage`、`reading_data`、`operation_logs`、`profile`、`submissions`、`activity_checkin`、`login`、`dashboard`、`base`。
   - 脚本少或为独立页面，可放在最后或随业务迭代逐步迁移。

---

## 五、汇总

### 5.1 确认修复项（本次重构已达成）

- 7 个核心页面模板的内联 `<script>` 块已全部移除，符合外迁目标。
- 页面 JS 文件均通过 `{% block scripts %}` 在 `base.html` 的公共脚本之后加载，执行顺序正确。
- `books.js` / `booklist.js` 等页面的确认弹窗已从原生 `confirm` 改为 `showConfirm` / `AdminConfirm.show`。
- 公共组件 `AdminConfirm`、`BatchSelect` 已注入全局，旧页面调用 `showConfirm` 时会被拦截到自定义弹窗。

### 5.2 需返工项（按优先级）

1. **P0 - 立即修复**
   - `admin-pages.js`：`AdminConfirm._close()` 应仅在用户确认时调用 callback；简单确认回调建议传递 `true`/`false`。
   - `books.js` `restoreDraft()`：修复取消时仍恢复草稿的问题（修复公共组件后自动解决）。
2. **P1 - 本迭代内修复**
   - 将 `AdminConfirm.show` 的 `body` 参数改为先转义/纯文本，或要求调用方显式传入已转义 HTML 并文档化。
   - 统一 `showConfirm` 与 `AdminConfirm.show` 的回调语义，兼容旧页面“仅在确认时执行”。
   - `books.js` 避免重复调用 `BatchSelect.init`；或改用事件委托。
   - 清理 `admin.js` 中的原生 `confirm` / `prompt` 调用（`batchDelete`、`showConfirm` 旧实现）。
   - 制定内联 `onclick` 清理计划（建议改用 `data-action` + 事件委托）。
3. **P2 - 下阶段优化**
   - 在核心页面中推广 `AdminTable` / `AdminPagination`，减少重复代码。
   - 移除 `booklist.html` / `activities.html` 中未使用的 `#confirmModal` 死代码。
   - 修复 `levels.js` `saveAdjustment()` 的 stub 实现。
   - 修复 `booklist.js` 测验题统计错误。
   - 修复 `borrow.html` “标记丢失”按钮缺失事件。
4. **P3 - 长期改进**
   - 弹窗组件增加 ESC 关闭、焦点陷阱、ARIA 属性。
   - 统一 ES6 语法风格；减少行内样式；补充 JSDoc。

### 5.3 建议下一步

1. **阻断发布风险**：在合并到主分支前，必须先修复 `AdminConfirm` 的 P0 取消回调缺陷，否则所有确认操作都会变成“无法取消”。
2. **回归测试**：QA 需重点覆盖 7 个核心页面的所有“取消”路径，确认不会误触发删除、下架、发布、发送提醒等业务动作。
3. **统一弹窗 API**：建议所有页面统一使用 `AdminConfirm.show`，删除 `orders.js`、死掉的 `#confirmModal` 等重复实现。
4. **推进剩余模板迁移**：按本报告第四节的优先级分批进行，迁移时同步替换原生 `confirm`/`alert`，避免重复劳动。
5. **引入 CSP**：待所有内联 `onclick` 清理完成后，可启用 `Content-Security-Policy` 进一步降低 XSS 风险。

---

*报告落盘路径：`/Users/litianyu/cc-projects/librio/deliverables/audit-2026-07-07/frontend-refactor-code-review.md`*
