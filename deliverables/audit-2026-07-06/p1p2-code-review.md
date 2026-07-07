# P1/P2 代码修复审查报告

- 审查日期：2026-07-06
- 审查范围：`/Users/litianyu/cc-projects/librio/backend`（admin templates、schemas、services、routers）
- 审查依据：开发模型声称已完成的 17 项 P1/P2 修复
- 审查人：Alex（Engineer）

## 总体结论

17 项声称修复中，**13 项已正确落地**，**1 项存在严重错误**（reports 状态过滤值与后端状态码不一致），**2 项实现不完整/存在风险**，**3 个 P3 级遗留问题**需要后续清理。

## 问题分级统计

| 级别 | 数量 | 说明 |
|------|------|------|
| P0   | 0    | 无导致系统崩溃、数据丢失或安全漏洞的问题 |
| P1   | 1    | 状态过滤值错误导致功能不可用 |
| P2   | 2    | 证书弹窗数据缺失/误导、逾期提醒按钮有“假实现”提示 |
| P3   | 3    | 统计卡片未填充、表格过滤失效、仪表盘 Service 重复实现 |

---

## 逐项审查

### 1. 证书弹窗改用后端真实字段

**声称内容**：`backend/templates/admin/certificates.html` — 证书弹窗改用后端真实字段 `level_name` / `certificate_no` / `issued_at` / `create_time`；保留 `book_count` / `word_count` / `prev_level` 兼容显示，不存在时显示为 0 或 `-`。

**实际代码位置**：
- `backend/templates/admin/certificates.html:166-197`（`openCert` 函数）
- `backend/domain/advancement/service.py:570-620`（`list_certificates` / `get_certificate`）

**审查结论**：⚠️ 有风险

**问题清单**：
1. 弹窗确实使用了 `level_name`、`certificate_no`、`issued_at`、`create_time`（第 170-172 行），并做了 fallback 处理，符合声称。
2. 但 `book_count` 与 `word_count` 在 Service 返回的证书对象中**并不存在**，前端用 `c.book_count || 0` 和 `c.word_count || 0` 显示，因此这两个统计永远展示为 `0`，属于“看起来有数据，实际为占位”的误导。
3. `prev_level` 在弹窗中**完全没有被使用**，与“保留 `prev_level` 兼容显示”不符。
4. 表头有“发证时间”和“生成时间”两列，但第 144-146 行均使用 `cert.create_time` 渲染，内容重复。
5. 页面顶部统计卡片依赖 `resp.stats`，但 `list_certificates` 只返回 `items`/`total`/`page`/`page_size`/`has_next`，没有 `stats`，四个卡片会一直保持 `--`。

**建议**：在 `list_certificates` 中补充 `book_count`/`word_count` 聚合或冗余字段，并返回 `stats`；如不需要应删除弹窗中的 0 占位统计。

---

### 2. `BookResponse` 新增 `question_count`

**实际代码位置**：`backend/domain/book/schemas.py:59`

**审查结论**：✅ 正确。`question_count: int | None = None` 已添加。

---

### 3. `search_books()` 批量聚合每本书的题库数量

**实际代码位置**：`backend/domain/book/service.py:35-78`

**审查结论**：✅ 正确。第 47-65 行一次性聚合 `QuestionBank`，第 70 行填充 `question_count`，无 N+1。

**建议**：检查 `QuestionBank.book_id` 是否有索引，避免大数据量下全表扫描。

---

### 4. “有测验题”统计从 `has_audio` 改为 `question_count`

**实际代码位置**：`backend/templates/admin/books.html:205`

**审查结论**：✅ 正确。`statQuiz` 使用 `books.filter(b => b.question_count && b.question_count > 0).length`。

---

### 5. 图书馆页面删除重复“词数”列并补充 `age_min` / `age_max`

**实际代码位置**：
- `backend/templates/admin/library.html:68-87`（表头 12 列）
- `backend/templates/admin/library.html:196-213`（行 12 列）
- `backend/templates/admin/library.html:94-137`（新增表单）
- `backend/templates/admin/library.html:233-257`（`addBook` 校验）

**审查结论**：✅ 正确。表头/行对齐为 12 列，无重复词数列；表单有年龄输入，`addBook` 校验了 3-15 与 `age_min <= age_max`。

**P3 备注**：输入框没有红色 `*` 必填标记，但功能上已强制校验。

---

### 6. 报告状态过滤 value 改为 int 2/3 并做 parseInt

**实际代码位置**：
- `backend/templates/admin/reports.html:19`（`<select>` value）
- `backend/templates/admin/reports.html:91-106`（统计与过滤逻辑）
- `backend/domain/report/models.py:25-26`（后端状态常量）
- `backend/domain/report/service.py:236,250`（状态写入）

**审查结论**：❌ 错误

- 前端确实把 value 改成了 `2` / `3`，并使用了 `parseInt`（第 104 行）。
- 但后端 `ObservationReport` 状态定义为 `STATUS_GENERATED = 1`、`STATUS_VIEWED = 2`。
- 生成报告时写 `status=1`，标记已查看时写 `status=2`。
- 前端“已生成”=2、“已查看”=3，与后端完全错位，过滤永远无结果；统计也基于 `2`/`3`，同样错误。
- 状态文本渲染写死为 `r.status === 3 ? '已查看' : '已生成'`（第 112-113 行），即使值改对，这里的判断也应改为 `=== 2`。

**修复建议**：前端 value 改为 `1`/`2`；统计与状态文本判断同步改为 `1`/`2`。

---

### 7. `AdminDashboardResponse` 新增今日统计字段

**实际代码位置**：`backend/domain/admin/admin_schemas.py:68-70`

**审查结论**：✅ 正确。`today_reading_minutes`、`today_new_words`、`today_voice_count` 已添加。

---

### 8. `get_dashboard()` 通过 SQL 聚合计算今日统计

**实际代码位置**：`backend/domain/admin/service.py:134-170`

**审查结论**：✅ 正确

- 今日阅读分钟：`func.sum(ReadingSession.duration_seconds)` 按今日过滤后除以 60（第 134-144 行）。
- 今日新增生词：`func.count(UserVocabulary.id)` 按 `create_time` 今日过滤（第 147-157 行）。
- 今日朗读次数：`func.count(VoiceRecording.id)` 按 `create_time` 今日过滤（第 160-170 行）。

**P2 备注**：查询对 `create_time` / `start_time` 使用 `func.date()`，如果相关表数据量大且未建索引，可能存在性能风险；建议评估索引。

---

### 9. 仪表盘填充“今日阅读总时长 / 今日新增生词 / 今日朗读次数”卡片

**实际代码位置**：`backend/templates/admin/dashboard.html:37-49, 107-109`

**审查结论**：✅ 正确。三个卡片分别绑定 `today_reading_minutes`、`today_new_words`、`today_voice_count` 并渲染。

---

### 10. 解除“发送逾期提醒”按钮禁用并绑定 `sendOverdueReminders()`

**实际代码位置**：`backend/templates/admin/borrow.html:31, 211-225`

**审查结论**：⚠️ 有风险

- 按钮已移除 `disabled` 并绑定 `sendOverdueReminders()`（第 31 行）。
- 函数确实调用后端 `/admin/api/borrows/send-overdue-reminders`（第 214 行）。
- 但函数内当 `count == 0` 时显示“该功能暂未实现，敬请期待”（第 219 行）。后端已实现真实逻辑，当没有逾期记录时返回 `sent_count=0`，此时提示“功能未实现”会误导用户，应改为“当前无逾期记录”。

---

### 11. 图书列表从 `/book/search` 改为 `/admin/api/books`

**实际代码位置**：`backend/templates/admin/books.html:179`

**审查结论**：✅ 正确。`loadBooks` 调用 `/admin/api/books`，对应 `admin_books_router.py:34-53` 的 `list_books` 接口，返回数据包含 `question_count`。

**P3 备注**：当前页统计使用 `books.length`（默认分页 20 条），而非后端 `total`，图书总数超过一页时统计不准确。

---

### 12. `advancement/service.py` 新增 `regenerate_certificate()`

**实际代码位置**：`backend/domain/advancement/service.py:732-769`

**审查结论**：✅ 正确。方法重新生成证书编号、更新 `issued_at`、同步 `child_name`/`child_english_name`/`level_name`/`badge_emoji` 冗余字段，并提交事务。

---

### 13. 证书重新生成路由调用真实 Service 方法

**实际代码位置**：`backend/domain/admin/routers/admin_advancement_router.py:145-153`

**审查结论**：✅ 正确。路由 `/certificates/{certificate_id}/regenerate` 调用 `service.regenerate_certificate(certificate_id)`。

---

### 14. 启用“重新生成”按钮并刷新列表

**实际代码位置**：`backend/templates/admin/certificates.html:149, 203-212`

**审查结论**：✅ 正确。表格行有“重新生成”按钮，`regenerate()` 调用 `/admin/api/advancement/certificates/{id}/regenerate`，成功后调用 `loadCertificates()` 刷新列表。

---

### 15. 启用“批量生成到期报告”按钮并刷新列表

**实际代码位置**：`backend/templates/admin/reports.html:21, 188-196`

**审查结论**：✅ 正确。按钮调用 `generateReports()`，请求 `/admin/api/reports/observation/generate`，成功后调用 `loadReports()` 刷新列表。

---

### 16. 评语接口路径从 `{child_id}/comment` 改为 `{report_id}/comment` 并传入 `admin.id`

**实际代码位置**：`backend/domain/admin/routers/admin_reports_router.py:89-98`

**审查结论**：✅ 正确。路径参数改为 `report_id`，调用 `service.add_teacher_comment(report_id, admin.id, data.comment)`。

**回归风险检查**：全局搜索确认已无其他调用点使用旧的 `{child_id}/comment` 路径，无回归风险。

---

### 17. 评语保存改为使用 `report_id`

**实际代码位置**：`backend/templates/admin/reports.html:168-174, 176-186`

**审查结论**：✅ 正确。`openComment()` 将 `currentReportId = r.id`，`saveComment()` 使用 `currentReportId` 调用 `/admin/api/reports/observation/{report_id}/comment`。

---

## 汇总

### 确认已正确修复（13 项）

2. `BookResponse` 新增 `question_count`
3. `search_books()` 批量聚合题库数量
4. “有测验题”统计改用 `question_count`
5. 图书馆页面 12 列表头/行对齐，新增 `age_min`/`age_max` 校验
7. `AdminDashboardResponse` 新增今日字段
8. `get_dashboard()` SQL 聚合今日统计
9. 仪表盘三个今日统计卡片填充
11. 图书列表切换为 `/admin/api/books`
12. `regenerate_certificate()` 新增
13. 证书重新生成路由调用真实 Service
14. 证书“重新生成”按钮启用并刷新
15. 报告“批量生成”按钮启用并刷新
16. 评语接口路径改为 `report_id` 并传入 `admin.id`
17. 评语保存使用 `report_id`

### 需改进项（2 项）

- **1. 证书弹窗数据**：`book_count`/`word_count` 在 Service 层未返回，导致弹窗显示恒为 0；`prev_level` 未展示；顶部统计卡片依赖缺失的 `resp.stats`。建议后端补充数据，或前端移除占位展示。
- **10. 逾期提醒按钮**：功能已实现，但 `sent_count == 0` 时提示“该功能暂未实现”会误导用户，应改为“当前无逾期记录”。

### 遗留问题（3 项 P3）

- **6. 报告状态过滤值错误**：前端 value 写死为 `2`/`3`，但后端状态为 `1`/`2`，导致过滤/统计全部失效。需要立即改为 `1`/`2`。
- **仪表盘 Service 重复实现**：`backend/domain/admin/service.py` 与 `backend/domain/admin/services/dashboard_service.py` 存在几乎完全相同的 `get_dashboard()` 逻辑；路由实际使用 `AdminService`，`AdminDashboardService` 成为死代码，建议合并或删除。
- **证书页面过滤失效**：`certificates.html` 中 `filterTable()` 依赖 `row.dataset.level` 和 `row.dataset.period`，但 `renderTable()` 从未设置这些属性，导致搜索/级别/时间段过滤不生效。

---

*报告落盘路径：`/Users/litianyu/cc-projects/librio/deliverables/audit-2026-07-06/p1p2-code-review.md`*