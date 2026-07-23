# XSS 深度审查与修复交接文档

> **创建时间**: 2026-07-21 (更新: 2026-07-23)
> **覆盖**: X1-X6 全部完成 ✅ | CI 同构九关全绿 | 回归 13/13
> **关联**: `HANDOFF.md` §3.7, `专家意见/XSS深度审查报告-20260721.md`, `tests/unit/test_xss_sanitization.py`

---

## 审查覆盖 (X1-X6)

| 维度 | 问题 | 修复 |
|------|------|------|
| **X1** | `Template()` 默认 `autoescape=False` | → `Environment(autoescape=select_autoescape(['html','xml']))` |
| **X2** | onclick 字符串拼接（注入点） | → `data-action` 委托 + `escapeHtml()` |
| **X3** | 模板插值未转义 | → 补 `escapeHtml()` 调用 |
| **X4** | `err.message` 直接 DOM 插入 | → `escapeHtml()` 包裹 |
| **X5** | Schema 字段无 max_length/白名单 | → `max_length=20` + 枚举 validator |
| **X6** | 回归测试缺失 | → 13 断言 (3 autoescape + 10 schema) |

---

## 修复文件清单

### X1 — Jinja2 Autoescape
- `backend/domain/report/service.py:319-325` — `Template`→`Environment(autoescape=...)`
- `backend/domain/certificate/service.py:129-134` — 同上
- `backend/templates/observation_report.html` — `teacher_comment_section` 保留 `| safe`（其他变量 autoescaped）

### X2 — onclick→data-* 委托
- `backend/static/admin/js/pages/users.js` — `editUser`, `showEditChild`
- `backend/static/admin/js/pages/submissions.js` — `openReview`
- `backend/static/admin/js/pages/certificates.js` — `regenerate`
- `backend/static/admin/js/base-init.js` — 新增 `escapeAttr()` 全局函数

### X3 — 模板插值补 escapeHtml
- `library.js` — `isbn`
- `levels.js` — `badge_emoji`
- `achievements.js` — `badge_emoji`
- `message_manage.js` — `groups`
- `certificates.js` — `level_name` ×4

### X4 — err.message 安全处理
- `damage_reports.js`, `assessments.js`, `books.js`(qCount)
- `benefit_transfers.js`, `operation_logs.js`, `recycle_bin.js`
- 清理以上文件的 `escapeAttr` 定时炸弹代码

### X5 — Schema 字段校验
- `backend/domain/admin/admin_schemas.py`
  - `BulkImportBookItem.isbn: max_length=20`
  - `LevelCreate.badge_emoji / AchievementCreate.badge_emoji: max_length=20`
  - `SendMessageRequest.target_role_groups: @field_validator` 枚举白名单

### X6 — 回归测试
- `tests/unit/test_xss_sanitization.py` — 13 断言:
  - 3 个 autoescape 测试
  - 10 个 schema validation 测试

---

## 关键设计决策

1. **escapeAttr() 放 base-init.js**（全局共享），不在各 page JS 重复定义
2. **jsEscape 升级**：处理 `& " < >`（在原有 `\\ '` 基础上），且 `&` 先替换防止 `&quot;`→`&amp;quot;`
3. **jsEscape 保留 `\\'` 模式**（不用 `&#39;`），因为 `&#39;` 在浏览器 onclick 上下文会被解码回 `'`，破坏 JS 语法
4. **data-action 委托读取 dataset**（浏览器自动处理转义，无需 escapeHtml）
5. **仅 `teacher_comment_section` 保留 `| safe`** — 其他变量保持 autoescaped

---

## 给新 LLM

1. **X1-X6 已全部修复验证通过**，不要重复修复
2. **新写 JS 时**：禁止内联 onclick/onchange/oninput/onsubmit，必须使用 `data-action` 委托
3. **所有 DOM 插入字符串**（含 err.message、API 返回字段）必须经 `escapeHtml()` 转义
4. **后端 Schema**：字符串字段加 `max_length`，枚举字段用 `@field_validator` 白名单
5. **Jinja2 Template()**：必须配合 `Environment(autoescape=True)`，禁止默认构造
6. 所有 escapeHtml 使用全局版（`??` 安全运算符），不要在 page JS 中重复定义
7. 验证用 `pytest tests/unit/test_xss_sanitization.py -v`（期望 13 passed）
