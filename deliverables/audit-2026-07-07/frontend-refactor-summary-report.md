# MegaWords 前端重构审查汇总报告

- **日期**：2026-07-07
- **范围**：管理后台前端公共组件 + 7 个核心页面 JS 外迁
- **审查团队**：software-frontend-refactor-review

---

## 一、总体结论

本次前端重构在“页面 JS 外迁”目标上取得实质进展，但**不可直接合并**。存在 2 个阻塞问题，需修复/确认后再合并。

| 维度 | 结论 |
|------|------|
| 后端测试套件 | 通过（pytest 100/100, behave 138/138, ruff 0, formal_test 119/119） |
| JS 语法检查 | 8 个文件全部通过 |
| 页面加载与渲染 | 通过 |
| 公共组件设计 | 基本可用，但取消回调有 P0 回归 |
| 路由/模板一致性 | 存在 `/admin/view/books` 与 `booklist.html` 不匹配问题 |
| 综合判定 | **需修复后合并** |

---

## 二、已确认修复的问题

### P0 — AdminConfirm 取消回调缺陷（已修复并验证）

**位置**：`backend/static/admin/js/admin-pages.js`

**修复内容**：
1. `_close(confirmed)` 简单确认模式下，仅在 `confirmed === true` 时调用 callback
2. 输入框模式取消传 `null`、确认传 `value.trim()`
3. `BatchSelect.init()` 增加 WeakMap 清理旧监听器，避免重复绑定
4. `AdminConfirm.show()` body 增加 sanitizeHtml 白名单过滤（移除 script/iframe/on* 等）
5. 增加 ESC 关闭、role/aria-modal 可访问性属性

**验证结果**：
- `node --check`：通过
- `ruff check backend/`：通过
- `pytest tests/unit/`：100/100
- `behave features/`：138/138
- `formal_test_v2.py`：119/119
- 浏览器回归：borrow/books/activities/levels/orders 等页面的删除/取消/发送提醒操作，取消后不再发起实际请求；BatchSelect 多次 init 后仅触发一次 onChange；Console 无 JS 报错

**详细验证报告**：`deliverables/audit-2026-07-07/frontend-refactor-test-report-v2.md`

---

## 三、待确认的阻塞问题

### 问题 1：图书管理路由与模板不匹配

**现象**：
- `/admin/view/books` 实际渲染 `booklist.html`，加载 `pages/booklist.js`
- `/admin/view/booklist` 路由不存在，返回 404
- `books.html` 与 `pages/books.js` 外迁后未被任何路由使用

**位置**：`backend/domain/admin/admin_page_router.py:181-198`

```python
@router.get("/books", response_class=HTMLResponse)
async def books(request: Request):
    ...
    return templates.TemplateResponse(
        request, "admin/booklist.html", {"active_page": "books"}   # ← 渲染了 booklist.html
    )

@router.get("/library", response_class=HTMLResponse)
async def library(request: Request):
    ...
    return templates.TemplateResponse(
        request, "admin/booklist.html", {"active_page": "library"} # ← 同样渲染 booklist.html
    )
```

**需要你确认**：

1. `/admin/view/books` 应该显示 **新版 `books.html`**（有统计、批量操作、上传进度）还是 **旧版 `booklist.html`**？
2. 如果保留 `booklist.html`，是否需要新增 `/admin/view/booklist` 路由？
3. `/admin/view/library` 是否应保留？如果 `books.html` 与 `booklist.html` 功能重叠，建议废弃其一。

**建议方案**：
- 将 `/admin/view/books` 改为渲染 `books.html`
- `/admin/view/library` 重定向到 `/admin/view/books` 或保留 `booklist.html` 作为独立路由
- 如果 `booklist.html` 不再使用，删除 `booklist.html` 和 `pages/booklist.js`，避免维护两套代码

---

## 四、非阻塞问题（后续迭代）

### P1 级别

1. **已迁移页面仍残留大量内联 `onclick` 事件处理器**
   - 7 个核心页面虽然移除了 `<script>` 块，但仍有 45+ 处 `onclick="window.xxxPage.*"`
   - 建议后续迁移到 `addEventListener`，实现 HTML 与 JS 真正分离

2. **原生 `confirm`/`alert` 仍有 23 处残留**
   - 主要在未迁移的 26 个模板中
   - 建议按优先级分批迁移：`settings.html`、`teachers.html`、`assessments.html`、`questions.html` 等高频操作页面优先

3. **公共组件利用率低**
   - `AdminTable` / `AdminPagination` 已抽取，但 7 个核心页面均未使用，仍自行实现表格/分页
   - 建议逐步推广公共组件，减少重复代码

### P2/P3 级别

- `AdminModal` 缺少焦点管理、ESC 关闭已在 AdminConfirm 实现但 AdminModal 未跟进
- 弹窗样式硬编码在 `style.cssText` 中
- 部分页面 ES5/ES6 混用（如 `books.js` 使用 `const/let`，`booklist.js` 使用 `var`）

---

## 五、剩余 26 个模板迁移优先级

| 优先级 | 模板 | 原因 |
|--------|------|------|
| 高 | settings.html, teachers.html, assessments.html, questions.html | 原生弹窗多、操作频繁、内联事件多 |
| 中 | certificates.html, recycle_bin.html, reservations.html, deposit.html | 确认操作多、安全影响大 |
| 低 | login.html, content.html, reading_data.html 等 | 操作少或主要用于展示 |

---

## 六、测试验证结果

| 测试项 | 命令 | 结果 |
|--------|------|------|
| ruff | `ruff check backend/` | All checks passed |
| pytest | `venv/bin/pytest tests/unit/ -q` | 100 passed |
| behave | `venv/bin/behave features/ -q` | 138 scenarios passed |
| formal_test | `venv/bin/python scripts/formal_test_v2.py` | 119/119 (100%) |
| JS 语法 | `node --check` | 8/8 通过 |

---

## 七、下一步行动

**阻塞项（需先解决）**：
1. 确认 `/admin/view/books` 与 `/admin/view/booklist` 的路由模板对应关系
2. 按确认结果修改 `admin_page_router.py`，并删除废弃的模板/JS

**完成后建议**：
1. 浏览器实际验证 7 个迁移页面（已安排 QA 进行，等待 v2 报告）
2. 按优先级分批次迁移剩余 26 个模板
3. 统一替换所有原生 `confirm`/`alert` 为 `AdminConfirm`/`showToast`

---

## 八、落盘文件

- 工程师审查报告：`deliverables/audit-2026-07-07/frontend-refactor-code-review.md`
- QA 测试报告（第一版）：`deliverables/audit-2026-07-07/frontend-refactor-test-report.md`
- 本汇总报告：`deliverables/audit-2026-07-07/frontend-refactor-summary-report.md`
