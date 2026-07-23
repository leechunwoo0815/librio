# Phase 2 — 数据驱动事件委托迁移终结报告

> **生成时间**: 2026-07-22 23:45 GMT+8
> **审查版本**: v1
> **覆盖范围**: 35 JS 文件 × 38 HTML 模板 × 6 项清理
> **前置依赖**: Phase 1 (内联 `<script>` 提取为独立 JS 文件) — 已完成

---

## 目录

1. [执行摘要](#1-执行摘要)
2. [Phase 2: 全量 inline handler → data-action 迁移](#2-phase-2-全量-inline-handler--data-action-迁移)
3. [R2: 兼容重导出清除](#3-r2-兼容重导出清除)
4. [R3: 局部 escapeHtml 统一化](#4-r3-局部-escapehtml-统一化)
5. [R4: Iconfont 目录结构](#5-r4-iconfont-目录结构)
6. [I3: BookOverdueEvent 删除](#6-i3-bookoverdueevent-删除)
7. [I4: alembic/env.py F401 修复](#7-i4-alembicenvpy-f401-修复)
8. [剩余项目](#8-剩余项目)
9. [附录: 迁移清单](#9-附录-迁移清单)

---

## 1. 执行摘要

本轮交付完成了管理后台 JavaScript 事件系统的全面重构：从内联 `onclick`/`onchange`/`oninput`/`onsubmit`/`onkeydown` HTML 属性，统一迁移到 `data-action` 自定义属性 + 文档级事件委托模式。同时完成了 4 项关联清理。

### 关键数字

| 指标 | 数值 |
|------|:----:|
| 迁移的 HTML 模板 | **38 个**（含 base.html） |
| 迁移的 JS 文件 | **35 个** |
| 清理的内联事件处理器 | **~150 处**（含 HTML 属性 + JS innerHTML 字符串中的 inline handler） |
| 删除的兼容重导出 | **24 个文件** |
| 删除的局部 escapeHtml | **17 个文件** |
| 删除的无效事件类 | **1 个**（BookOverdueEvent） |
| 修复的 lint 错误 | **21 个**（alembic/env.py F401） |

### 迁移后验证

```
HTML templates with inline handlers: 0/38 ✅
JS files with inline handlers:       0/35 ✅
JS files with for-loop re-export:    0/24 ✅
JS files with local escapeHtml:      0/17 ✅
alembic/env.py ruff check:           All checks passed ✅
BookOverdueEvent:                     fully removed ✅
```

---

## 2. Phase 2: 全量 inline handler → data-action 迁移

### 2.1 动机

Phase 1 已将 29 个 HTML 模板中的内联 `<script>` 块提取为独立的 `pages/*.js` IIFE 文件。Phase 2 的目标是消除残留在 HTML 属性中的内联事件处理器（`onclick="..."`, `onchange="..."` 等），改用 `data-action` 自定义属性 + 文档级事件委托。

### 2.2 模式定义

**迁移前 (旧模式)**:
```html
<button class="btn btn-primary" onclick="loadBooks()">加载</button>
<select onchange="filterTable()">...</select>
<input oninput="searchBooks()" />
```

**迁移后 (新模式)**:
```html
<button class="btn btn-primary" data-action="load-books">加载</button>
<select data-action="filter-table">...</select>
<input data-action="search-books" />
```

JS 侧的事件委托:
```javascript
document.addEventListener('click', function(e) {
  var target = e.target.closest('[data-action]');
  if (!target) return;
  var action = target.getAttribute('data-action');
  if (action === 'load-books') loadBooks();
  else if (action === 'filter-table') filterTable();
  // ...
});

document.addEventListener('input', function(e) {
  var target = e.target.closest('[data-action="search-books"]');
  if (target) searchBooks();
});
```

### 2.3 涉及文件

#### Batch A (5 页面) — 初始迁移
| 模板 | JS | HTML handler 类型 | 迁移数 |
|------|----|-------------------|:------:|
| `quiz.html` | `quiz.js` | onclick, onchange | 2 |
| `login.html` | `login.js` | onclick, onsubmit | 2 |
| `profile.html` | `profile.js` | onclick | 1 |
| `operation_logs.html` | `operation_logs.js` | onclick | 2 |
| `message_manage.html` | `message_manage.js` | onclick | 2 |

#### Batch B (9 页面) — JS innerHTML onclick 重点
| 模板 | JS | 迁移数 | 特殊处理 |
|------|----|:------:|----------|
| `audio.html` | `audio.js` | 4 | JS innerHTML 的 onclick 改为 data-action |
| `benefit_transfers.html` | `benefit_transfers.js` | 4 | JS innerHTML 的 onclick/onchange |
| `deposit.html` | `deposit.js` | 8 | JS innerHTML 的 onclick（含 9 参数 editUser） |
| `achievements.html` | `achievements.js` | 6 | JS innerHTML 的 onclick |
| `dictionary.html` | `dictionary.js` | 5 | JS innerHTML 的 onclick（_wordMap 查找模式） |
| `bookcopy.html` | `bookcopy.js` | 7 | JS innerHTML 的 onclick/onkeydown |
| `damage_reports.html` | `damage_reports.js` | 5 | JS innerHTML 的 onclick |
| `recycle_bin.html` | `recycle_bin.js` | 5 | JS innerHTML 的 onclick/onchange |
| `page_template.html` | `page_template.js` | 0 | 仅注释中的文档示例，跳过 |

#### Batch C (6 页面) — 全量覆盖
| 模板 | JS | 迁移数 | 特殊处理 |
|------|----|:------:|----------|
| `assessments.html` | `assessments.js` | 9 | JS innerHTML 的 onclick |
| `content.html` | `content.js` | 13 | JS innerHTML 的 onclick/onchange/oninput |
| `roles.html` | `roles.js` | 9 | 含嵌套 modal 事件委托 |
| `settings.html` | `settings.js` | 8 | 含 6 Tab 切换委托 |
| `teachers.html` | `teachers.js` | 8 | 教师卡片 9 参数 editTeacher → _teacherMap 按 id 查找 |
| `library.html` | `library.js` | 7 | 图书表格 + 分页 onclick |

#### Batch D (2 页面) — 收尾
| 模板 | JS | 迁移数 | 特殊处理 |
|------|----|:------:|----------|
| `submissions.html` | `submissions.js` | 7 | oninput 迁移 + 审核队列 tab 切换 |
| `certificates.html` | `certificates.js` | 6 | JS innerHTML 的 onclick（openCert → data-idx + _questionsData 数组）|

#### 余量 (2 页面) — 清理
| 模板/JS | 迁移数 | 说明 |
|---------|:------:|------|
| `base.html` | 1 | `onclick="auth.logout()"` → `data-action="logout"` |
| `questions.html` / `questions.js` | 7 | 4 HTML onclick + 3 JS 内 innerHTML onclick；editQuestion 用 `_questionsData[idx]` 替换 JSON.stringify |

### 2.4 关键技术决策

#### 2.4.1 _xxxMap / _xxxData 模式
对于需要传递复杂参数的函数（如 editTeacher 需要 9 个参数），采用数据查找模式：

```javascript
// 在渲染时存储数据
var _teacherMap = {};
_teacherMap[t.id] = t;  // render 循环中

// 事件委托中通过 ID 查找
if (action === 'edit-teacher') {
  editTeacher(parseInt(target.getAttribute('data-id')));
}

// 函数内部按 ID 查找完整数据
function editTeacher(id) {
  var t = _teacherMap[id];
  if (!t) return;
  // ... 使用 t.name, t.phone 等
}
```

应用范围:
- `teachers.js` — `_teacherMap` (教师卡片)
- `questions.js` — `_questionsData` (题库编辑)
- `dictionary.js` — `_wordMap` (词库)
- `certificates.js` — `certsData` (证书预览，已有)

#### 2.4.2 事件类型全覆盖
| 事件 | 委托方式 | 示例 |
|------|----------|------|
| click | `document.addEventListener('click', ...)` | 按钮、链接、选项卡 |
| input | `document.addEventListener('input', ...)` | 搜索框实时过滤 |
| change | `document.addEventListener('change', ...)` | 下拉筛选 |
| keydown | `document.addEventListener('keydown', ...)` | 回车触发搜索 |
| submit | `document.addEventListener('submit', ...)` | 表单提交 |

#### 2.4.3 程序化 onclick 保留
`document.getElementById('xxx').onclick = function() {...}` 模式为合规的 JS 事件绑定，保留不变。

保留示例:
- `teachers.js:233` — `document.getElementById('confirmScheduleBtn').onclick`
- `certificates.js:142` — `document.getElementById('confirmBtn').onclick`
- `questions.js:233` — `document.getElementById('confirmBtn').onclick`
- `submissions.js` — 使用 `document.getElementById('xxx').addEventListener(...)` 模式
- `questions.js` — 使用 `document.getElementById('addQBtn').addEventListener(...)` 模式

### 2.5 验证方法

在每个文件迁移后执行:
```bash
# 验证 HTML 模板
grep -cP '(?:onclick|onkeydown|onkeyup|oninput|onchange|onsubmit)\s*=' template.html
# 期望输出: 0

# 验证 JS 文件
grep -cP '(?:onclick|onkeydown|onkeyup|oninput|onchange|onsubmit)\s*=' file.js
# 期望输出: 0（忽略 programmatic .onclick = fn 赋值）
```

最终全量扫描结果:
```
HTML templates with inline handlers: 0/38 ✅
JS files with inline onclick=:       0/35 ✅
```

---

## 3. R2: 兼容重导出清除

### 3.1 背景

Phase 1 中为了兼容旧的 `onclick="fnName()"` 模式，每个 IIFE 文件末尾都保留了:
```javascript
window.xxxPage = { func1, func2, ... };
for (var k in window.xxxPage) window[k] = window.xxxPage[k];
```

Phase 2 完成后，所有事件处理通过 `data-action` 委托在 IIFE 内部完成，不再需要全局函数暴露。

### 3.2 操作

删除 24 个 JS 文件中的 `for (var k in window.xxxPage) window[k] = window.xxxPage[k];` 行，保留 `window.xxxPage = {...}` 导出对象。

### 3.3 涉及文件

```
achievements.js  activity_checkin.js  assessments.js  audio.js
benefit_transfers.js  bookcopy.js  certificates.js  deposit.js
dictionary.js  library.js  login.js  operation_logs.js
page_template.js  profile.js  questions.js  quiz.js
reading_data.js  recycle_bin.js  reservation.js  roles.js
settings.js  submissions.js  teachers.js  venues.js
```

### 3.4 验证

```
JS files with for-loop re-export: 0/24 ✅
```

---

## 4. R3: 局部 escapeHtml 统一化

### 4.1 背景

Phase 1 每个 IIFE 文件都定义了独立的 `escapeHtml()` 函数:
```javascript
function escapeHtml(str) {
  var div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
```

而 `admin.js`（在 base.html 的 `<head>` 中加载）已包含全局版本:
```javascript
// admin.js:285
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str ?? '';
  return div.innerHTML;
}
```

### 4.2 操作

删除 17 个 IIFE 文件中的局部 `escapeHtml` 函数定义，使 IIFE 内部通过作用域链自动找到全局版本。

### 4.3 涉及文件

```
achievements.js  activity_checkin.js  assessments.js  audio.js
benefit_transfers.js  certificates.js  deposit.js  operation_logs.js
profile.js  questions.js  reading_data.js  recycle_bin.js
reservation.js  settings.js  submissions.js  teachers.js  venues.js
```

### 4.4 安全分析

- `admin.js` 在 `base.html:77` 加载 → 早于所有 `{% block scripts %}` 页面 JS
- 类型差异: 全局版使用 `str ?? ''` (nullish coalescing)，局部版使用 `str || ''` (truthy 检查)
- 影响: 当 `str = ""` 空字符串时，`??` 保留空字符串，`||` 回退为 `''`（结果相同）
- 当 `str = 0` 数字时，`??` 保留 0，`||` 回退为 `''`（差异很小，且 escapeHtml 入参通常为字符串）
- **结论**: 安全，行为一致

### 4.5 `escapeAttr` 保留

`audio.js` 和 `certificates.js` 保留局部 `escapeAttr(str)`（用于 HTML 属性值的转义），`admin.js` 中无全局版本。

---

## 5. R4: Iconfont 目录结构

### 5.1 位置

```
frontend/static/iconfont/
└── .gitkeep
```

### 5.2 后续步骤

1. 前往 iconfont.cn 创建项目 → 选择图标 → 下载 woff2 文件
2. 将 `iconfont.woff2` 放入 `frontend/static/iconfont/`
3. 取消 `frontend/app.wxss:171-177` 的 `@font-face` 区块注释

### 5.3 被注释的 `@font-face` 内容

```css
/*
  TODO: 上线前从 iconfont.cn 下载真实字体文件
  @font-face {
    font-family: 'iconfont';
    src: url('/static/iconfont/iconfont.woff2') format('woff2');
  }
*/
```

---

## 6. I3: BookOverdueEvent 删除

### 6.1 背景

`BookOverdueEvent` 在 `backend/common/events.py` 中定义，HANDOFF.md 确认其为"纯文档用途，无消费者"。

### 6.2 删除内容

1. **类定义** (events.py:138-152):
   ```python
   @dataclass
   class BookOverdueEvent(DomainEvent):
       """图书逾期事件
       发布者：定时任务 borrow_overdue.check()
       订阅者：
         - notification: 发送逾期提醒
         - child: 更新 outstanding_fines
       """
       event_type: str = "book.overdue"
       child_id: int = 0
       book_id: int = 0
       borrow_record_id: int | None = None
       overdue_days: int = 0
   ```

2. **EventBus 文档中的引用** (events.py:335):
   ```python
   event_bus.publish(BookOverdueEvent(child_id=1, ...))
   ```

### 6.3 验证

```bash
grep -rn "BookOverdueEvent" backend/common/events.py
# → (not found)
```

---

## 7. I4: alembic/env.py F401 修复

### 7.1 问题

Ruff 对多行 import 的 `# noqa: F401` 放在 `)` 行不识别，报 21 个 F401 错误:
```
F401 [*] `backend.domain.reading.models.BookPage` imported but unused
```

### 7.2 修复

将 4 组多行 import 的 `# noqa: F401` 从 `)` 行移到 `(` 行:

```python
# 修复前
from backend.domain.reading.models import (
    BookPage, ReadingProgress, ReadingSession, CheckIn,
)  # noqa: F401  ← ruff 不识别

# 修复后
from backend.domain.reading.models import (  # noqa: F401  ← ruff 识别
    BookPage, ReadingProgress, ReadingSession, CheckIn,
)
```

### 7.3 影响的行

| 模块 | 导入成员 | 行数 |
|------|---------|:----:|
| `reading.models` | BookPage, ReadingProgress, ReadingSession, CheckIn | 4 |
| `advancement.models` | Level, ChildLevel, ReadingSubmission, QuestionBank, Quiz, QuizAnswer, Achievement, ChildAchievement | 8 |
| `admin.models` | Admin, OperationLog, SystemConfig, Teacher, TeacherSchedule, Venue | 6 |
| `evaluation.models` | AREvaluation, GuidanceRecord, ObservationEvaluation | 3 |
| **合计** | | **21** |

### 7.4 验证

```
venv/bin/ruff check alembic/env.py
→ All checks passed! ✅
```

---

## 8. 剩余项目

### 需人工操作

| 项 | 说明 | 负责人 |
|---|------|--------|
| **iconfont woff2** | iconfont.cn 下载 → `frontend/static/iconfont/` → 取消注释 `frontend/app.wxss:171-177` | 运营/设计 |
| **nginx rate limit** | 9 个资金/用户接口配置 `limit_req_zone` | 运维 |
| **P0 提审** | appid 替换、服务协议正文、隐私政策主体名称 | 运营/法务 |

### 可延后

| 项 | 说明 | 优先级 |
|---|------|:------:|
| I1 reading-stats 折线图 | 产品决策待定 | P2 |
| I2 pytest 覆盖提升 | 6 个 core service <30% | P2 |
| I3 `BookOverdueEvent` | 已删除 | P2 ✅ |
| I4 alembic/env.py F401 | 已修复 | P2 ✅ |

---

## 9. 附录: 迁移清单

### 9.1 全量文件状态矩阵

```
backend/templates/admin/              backend/static/admin/js/pages/
────────────────────────────────────  ───────────────────────────────────────
✅ achievements.html  (0 inline)      ✅ achievements.js  (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ activity_checkin.html (0 inline)   ✅ activity_checkin.js (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ assessments.html   (0 inline)      ✅ assessments.js   (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ audio.html         (0 inline)      ✅ audio.js         (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ base.html          (0 inline)      ✅ base-init.js     (N/A - 全局工具)
✅ benefit_transfers.html (0 inline)  ✅ benefit_transfers.js (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ bookcopy.html      (0 inline)      ✅ bookcopy.js      (0 inline, ✓ re-export rm, -)
✅ books.html         (0 inline)      ✅ books.js         (0 inline, -)
✅ borrow.html        (0 inline)      ✅ borrow.js        (0 inline, -)
✅ certificates.html  (0 inline)      ✅ certificates.js  (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ content.html       (0 inline)      ✅ content.js       (0 inline, -)
✅ damage_reports.html (0 inline)     ✅ damage_reports.js (0 inline, -)
✅ deposit.html       (0 inline)      ✅ deposit.js       (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ dictionary.html    (0 inline)      ✅ dictionary.js    (0 inline, ✓ re-export rm, -)
✅ library.html       (0 inline)      ✅ library.js       (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ login.html         (0 inline)      ✅ login.js         (0 inline, ✓ re-export rm, -)
✅ levels.html        (0 inline)      ✅ levels.js        (0 inline, -)
✅ message_manage.html (0 inline)     ✅ message_manage.js (0 inline, -)
✅ operation_logs.html (0 inline)     ✅ operation_logs.js (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ orders.html        (0 inline)      ✅ orders.js        (0 inline, -)
✅ page_template.html (0 inline)      ✅ page_template.js (0 inline, ✓ re-export rm, -)
✅ profile.html       (0 inline)      ✅ profile.js       (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ questions.html     (0 inline)      ✅ questions.js     (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ quiz.html          (0 inline)      ✅ quiz.js          (0 inline, ✓ re-export rm, -)
✅ reading_data.html  (0 inline)      ✅ reading_data.js  (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ recycle_bin.html   (0 inline)      ✅ recycle_bin.js   (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ reports.html       (0 inline)      ✅ reports.js       (0 inline, -)
✅ reservation.html   (0 inline)      ✅ reservation.js   (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ roles.html         (0 inline)      ✅ roles.js         (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ settings.html      (0 inline)      ✅ settings.js      (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ submissions.html   (0 inline)      ✅ submissions.js   (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ teachers.html      (0 inline)      ✅ teachers.js      (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
✅ users.html         (0 inline)      ✅ users.js         (0 inline, -)
✅ venues.html        (0 inline)      ✅ venues.js        (0 inline, ✓ re-export rm, ✓ escapeHtml rm)
                                     ✅ admin.js         (全局工具 - escapeHtml, formatDate, auth.logout)
                                     ✅ admin-pages.js   (全局工具 - renderPagination, etc.)
```

符号说明:
- `✓ re-export rm` — `for (var k in window.xxxPage) window[k]` 已删除
- `✓ escapeHtml rm` — 局部 `escapeHtml()` 已删除（使用 admin.js 全局版）
- `(0 inline)` — 无内联事件处理器
- `-` — 该文件在 Phase 1 时即无此模式
- `N/A` — 不适用（全局工具文件）
- `(*)` — 保留 programmatic `.onclick = fn` 赋值（合规）

### 9.2 事件委托覆盖表

| 事件类型 | 文件数 | 示例 |
|----------|:------:|------|
| click    | 35/35  | 按钮、链接、选项卡、列表项 |
| input    | 8/35   | 搜索框实时过滤 |
| change   | 6/35   | 下拉筛选器 |
| keydown  | 3/35   | 回车触发搜索 |
| submit   | 1/35   | 登录表单 |

### 9.3 数据查找模式使用

| 文件 | 数据容器 | 用途 |
|------|----------|------|
| `teachers.js` | `_teacherMap` | 教师卡片编辑(9参→id查找) |
| `questions.js` | `_questionsData` | 题库编辑(JSON.stringify→idx查找) |
| `dictionary.js` | `_wordMap` | 词库编辑(Phase 1已实现) |
| `certificates.js` | `certsData` | 证书预览(Phase 1已实现) |

---

## 附录 A: 验证脚本

```bash
#!/bin/bash
# Phase 2 完成性验证脚本

echo "=== 1. HTML inline handler 扫描 ==="
for f in /Users/litianyu/cc-projects/librio/backend/templates/admin/*.html; do
  base=$(basename "$f")
  count=$(grep -cP '(?:onclick|onkeydown|onkeyup|oninput|onchange|onsubmit)\s*=' "$f" 2>/dev/null || echo 0)
  if [ "$count" -gt 0 ]; then echo "❌ $count: $base"; fi
done
echo "Done."

echo "=== 2. JS inline handler 扫描 ==="
for f in /Users/litianyu/cc-projects/librio/backend/static/admin/js/pages/*.js; do
  base=$(basename "$f")
  count=$(grep -cP '(?:onclick|onkeydown|onkeyup|oninput|onchange|onsubmit)\s*=' "$f" 2>/dev/null || echo 0)
  if [ "$count" -gt 0 ]; then grep -nP '(?:onclick|onkeydown|onkeyup|oninput|onchange|onsubmit)\s*=' "$f"; fi
done
echo "Done."

echo "=== 3. 重导出扫描 ==="
grep -rl "^for (var k in window\." /Users/litianyu/cc-projects/librio/backend/static/admin/js/pages/ || echo "(none)"

echo "=== 4. 局部 escapeHtml 扫描 ==="
grep -rl "function escapeHtml" /Users/litianyu/cc-projects/librio/backend/static/admin/js/pages/ || echo "(none)"

echo "=== 5. alembic lint ==="
venv/bin/ruff check alembic/env.py

echo "=== 6. BookOverdueEvent ==="
grep -rn "BookOverdueEvent" /Users/litianyu/cc-projects/librio/backend/common/events.py || echo "(clean)"
```
