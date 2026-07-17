# 前端全量静态 Bug 扫描报告

> **生成时间**: 2026-07-17 GMT+8  
> **扫描范围**: 小程序 45 JS + 45 WXML + 45 WXSS | 管理台 33 CSS + 37 HTML | 12 组件  
> **扫描方式**: 正则静态分析 (Python)，逐文件 grep 模式匹配  
> **审计用途**: 人工专家审查 — 逐条确认真/误报

---

## 严重度分级

| 级别 | 定义 | 数量 |
|------|------|------|
| **P0** | 运行时崩溃 / 资金安全 | 6 |
| **P1** | 功能异常 / 数据丢失 | 21 |
| **P2** | 体验 / 样式 / 工程 | 305 |
| **P3** | 建议 / 低风险 | 65 |

---

## 类别分布

| 类别 | 数量 | 占比 |
|------|------|------|
| 管理台内联 onclick (P2) | 226 | 57% |
| 硬编码 hex 颜色 (P2) | 72 | 18% |
| WXML 绑定无 wx:if (P3) | 48 | 12% |
| 未保护 .find() (P0) | 6 | 2% |
| 未保护 .filter() (P1) | 14 | 4% |
| 未保护 .map() (P3) | 17 | 4% |
| 未保护 .toFixed() → NaN (P1) | 2 | 1% |
| wx:for 缺 wx:key (P2) | 4 | 1% |
| 禁用 CSS 特性 (P2) | 3 | 1% |
| 空 catch 块 (P1) | 2 | 1% |
| !important 滥用 (P3) | 2 | 1% |
| 定时器泄露 (P1) | 1 | <1% |
| app.js 缺全局异常 (P1) | 1 | <1% |

---

## P0 — 运行时崩溃（必修）

| # | 文件 | 行 | 问题 | 修复方案 |
|---|------|----|------|---------|
| 1 | `pages/order-pkg/child-manage/child-manage.js` | 44 | `.find()` 无 `\|\| []` 保护 | `(data.children \|\| []).find(id => id === e) ...` |
| 2 | `pages/order-pkg/benefit-transfer/benefit-transfer.js` | 46 | `.find()` 无 `\|\| []` 保护 | `(records \|\| []).find(r => r.id === ...)` |
| 3 | `pages/order-pkg/messages/messages.js` | 133 | `.find()` 无 `\|\| []` 保护 | `(conversations \|\| []).find(...)` |
| 4 | `pages/reading-pkg/reader/reader.js` | 78 | `.find()` 无 `\|\| []` 保护 | `(books \|\| []).find(b => b.id === ...)` |
| 5 | `pages/member-pkg/observation-report/observation-report.js` | 116 | `.find()` 无 `\|\| []` 保护 | `(data \|\| []).find(...)` |
| 6 | `pages/activity-pkg/activity-list/activity-list.js` | 83 | `.find()` 无 `\|\| []` 保护 | `(activities \|\| []).find(a => a.id === ...)` |

**风险**: API 返回 `null`/`undefined` 数组时直接崩溃白屏。已在零宕机审查中确认 F4 `null.find()` 已修此类模式，但扫描发现仍有 6 处遗漏。

---

## P1 — 功能异常（建议修）

### 未保护 .filter() — 14 处

| # | 文件 | 行 |
|---|------|----|
| 1 | `pages/order-pkg/messages/messages.js` | 110 |
| 2 | `pages/order-pkg/child-manage/child-manage.js` | 45 |
| 3 | `pages/order-pkg/benefit-transfer/benefit-transfer.js` | 47 |
| 4 | `pages/order-pkg/borrow-history/borrow-history.js` | 38, 39, 51 |
| 5 | `pages/order-pkg/order-history/order-history.js` | 46 |
| 6 | `pages/order-pkg/reservation/reservation.js` | 62, 63 |
| 7 | `pages/order-pkg/refund-apply/refund-apply.js` | 76 |
| 8 | `pages/reading-pkg/quiz/quiz.js` | 243 |
| 9 | `pages/reading-pkg/vocabulary/vocabulary.js` | 148, 230 |
| 10 | `pages/shelf/shelf.js` | 99 |
| 11 | `pages/activity-pkg/activity-list/activity-list.js` | 62, 64 |

### 未保护 .toFixed() → NaN — 2 处

| # | 文件 | 行 | 代码片段 |
|---|------|----|---------|
| 1 | `pages/reading-pkg/quiz-result/quiz-result.js` | 73 | `((total - wrong) / total * 100).toFixed(1)` — 分母可能为 0 |
| 2 | `pages/reading-pkg/quiz-result/quiz-result.js` | 74 | 同上 |

### 空 catch 块 — 2 处

| # | 文件 | 行 | 风险 |
|---|------|----|------|
| 1 | `pages/reading-pkg/reader/reader.js` | 433 | `catch(e) {}` — 音频错误被静默，用户无反馈 |
| 2 | `components/pay-button/pay-button.js` | 15 | `catch(e) {}` — 支付异常被静默 |

### 定时器泄露 — 1 处

| # | 文件 | 风险 |
|---|------|------|
| 1 | `pages/reading-pkg/reader/reader.js` | 有 setInterval/setTimeout + onUnload 但无 clear |

### app.js 缺全局异常 — 1 处

| # | 文件 | 建议 |
|---|------|------|
| 1 | `app.js` | 增加 `onError` 捕获全局 JS 异常，上报日志 |

---

## P2 — 体验/样式/工程

### 管理台内联 onclick （226 处，涉及 30+ 模板）

**代表性文件**（完整列表见扫描输出）：

| 模板 | 内联 onclick 数量 | 建议 |
|------|-------------------|------|
| `templates/admin/content.html` | 16 | 外迁到 `content.js` |
| `templates/admin/page_template.html` | 10 | 外迁 |
| `templates/admin/teachers.html` | 12 | 外迁 |
| `templates/admin/library.html` | 7 | 外迁 |
| `templates/admin/dictionary.html` | 10 | 外迁 |

**说明**: 内联 `onclick="handler()"` 无法单元测试、代码膨胀。建议分批外迁。已在 `users.html` 完成示范（`24 个 onclick → users.js`）。

### 硬编码 hex 颜色（72 处）

| 文件 | 示例 |
|------|------|
| `backend/static/admin/css/base.css` | `#f7f9fa`, `#5560cf`, `#94ed5a`, `#39c34b` 等 21 个 |
| `pages/shelf/shelf.wxss` | `#e8dff5`, `#fce4ec`, `#e0f2f1` 等 16 个 |
| `pages/certificates.css` | `#d4a843`, `#b8860b`, `#c8a060` 等 12 个 |
| `pages/login/login.wxss` | `#07C160` (微信绿) |

**说明**: base.css 的硬编码 hex 是 CSS 变量定义本身，属合理保留。其余应迁移为 CSS 变量。

### 禁用 CSS 特性（3 处）

| 文件 | 行 | 特性 | 影响 |
|------|----|------|------|
| `backend/static/admin/css/base.css` | 185 | `backdrop-filter` | 微信小程序不支持，PC web 部分浏览器不支持 |
| `backend/static/admin/css/base.css` | 519 | `backdrop-filter` | 同上 |
| `backend/static/admin/css/pages/content.css` | 26 | `aspect-ratio` | 小程序兼容性问题 |

### wx:for 缺 wx:key（4 处）

| 文件 | 行 |
|------|----|
| `pages/books/books.wxml` | 100 |
| `pages/shelf/shelf.wxml` | 67, 128, 155 |

---

## P3 — 建议/低风险

### WXML 绑定无 wx:if 保护（48 处）

代表性模式：
```wxml
<text>{{item.name}}</text>         <!-- 缺 wx:if="{{item}}" -->
<image src="{{book.cover}}"></image> <!-- 缺 wx:if="{{book}}" -->
```

### 未保护 .map()（17 处）

均用于列表渲染，API 返回空数组时不会崩溃，但建议加 `|| []` 保护。

### !important（2 处）

`base.css:358`, `base.css:922` — 降低样式可维护性。

---

## 专家审查建议

1. **优先审查 P0 × 6**: 确认是否在零宕机审查中已修复（扫描可能命中旧代码）。逐行验证 `|| []` 是否已存在。
2. **P1 .toFixed() × 2**: 确认 `quiz-result.js` 的 `total===0` fallback 是否已覆盖。
3. **P1 空 catch × 2**: `reader.js:433` 和 `pay-button.js:15` 应至少加 `console.error`。
4. **内联 onclick**: 建议分批计划（P3 级别，非阻塞）。
5. **CSS 禁用特性**: `backdrop-filter` 两个位置如果仅影响 PC 管理台可保留；`aspect-ratio` 在 `content.css:26` 需确认兼容性。

---

## 扫描局限性

- **假阳性**: `.find()` 的 guard 可能在上一行，静态扫描可能遗漏上下文
- **假阴性**: 动态属性访问 (`data[key]`) 无法静态检测
- **未覆盖**: 微信 API 调用结果（如 `wx.getStorageSync` 返回 null）不在本扫描范围
- **未覆盖**: 后端 API 响应 schema 变更导致的字段缺失无法检测
