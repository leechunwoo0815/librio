# MegaWords P1/P2 修复完整审查报告

- **审查日期**：2026-07-06
- **审查范围**：17 项声称已完成的 P1/P2 修复（字段不匹配 + 功能启用 + 评语路径修复）
- **审查团队**：软件开发团队（寇豆码 · 工程师、严过关 · QA 工程师）
- **报告输出**：齐活林 · 交付总监
- **项目路径**：`/Users/litianyu/cc-projects/librio`

---

## TL;DR

开发模型声称 17 项 P1/P2 修复全部完成且测试全绿。经工程师逐条代码审查和 QA 全量测试验证：

- **13 项已正确落地**，动态测试（pytest 100/100、behave 138/138、formal_test 119/119）全部通过
- **1 个 P1 严重错误**：报告状态过滤值与后端状态码错位，功能完全失效
- **2 个 P2 风险项**：证书弹窗展示假数据、逾期提醒按钮误导文案
- **1 个 Ruff 静态检查失败** + **2 个管理端接口 404**

**结论：有条件通过。动态测试全绿，但代码静态质量、接口一致性、前端功能正确性仍有明确缺陷，必须修复后再交付。**

---

## 一、审查方法与验证项

### 1.1 审查维度

| 维度 | 执行者 | 覆盖内容 |
|------|--------|----------|
| 代码实现审查 | 工程师（寇豆码） | 17 项修复逐条核对代码位置、字段一致性、逻辑正确性、回归风险 |
| 全量测试验证 | QA（严过关） | pytest、behave、ruff、formal_test_v2、管理端接口回归抽查 |

### 1.2 验证命令

```bash
venv/bin/pytest tests/unit/ -q
venv/bin/behave features/ -q
ruff check backend/
venv/bin/python scripts/formal_test_v2.py
```

---

## 二、测试结果总览

| 检查项 | 声称结果 | 实际结果 | 状态 |
|--------|----------|----------|------|
| pytest 单元测试 | 100/100 | **100/100** | ✅ |
| behave BDD 测试 | 138/138 | **138/138** | ✅ |
| ruff check backend/ | 0 errors | **1 处 F401** | ❌ |
| formal_test_v2 接口测试 | 119/119 | **119/119** | ✅ |
| 后端服务启动 | — | 正常启动，无 500 | ✅ |
| 管理端接口一致性 | — | 2 个接口 404 | ❌ |

**说明**：formal_test_v2 对管理端列表接口的判定逻辑为"状态码 < 500 即通过"，因此 404 未被标记为失败。QA 额外做了回归抽查才发现。

---

## 三、P1 字段不匹配修复审查（8 项）

| # | 修复项 | 文件 | 结论 | 说明 |
|---|--------|------|------|------|
| 1 | 证书弹窗改用后端真实字段 | `backend/templates/admin/certificates.html` | ⚠️ P2 风险 | 弹窗字段已改对，但 `book_count`/`word_count` 后端未返回，永远显示 0；`prev_level` 未使用；表头"发证时间"与"生成时间"均用 `create_time` 重复渲染；顶部统计卡片依赖缺失的 `resp.stats` |
| 2 | `BookResponse` 新增 `question_count` | `backend/domain/book/schemas.py` | ✅ | `question_count: int \| None = None` 已添加 |
| 3 | `search_books()` 批量聚合题库数量 | `backend/domain/book/service.py` | ✅ | 一次性聚合 `QuestionBank`，无 N+1 |
| 4 | “有测验题”统计改用 `question_count` | `backend/templates/admin/books.html` | ✅ | 统计逻辑已修正 |
| 5 | 图书馆页面列对齐并补充 `age_min`/`age_max` | `backend/templates/admin/library.html` | ✅ | 表头/行 12 列对齐；表单有年龄校验（3-15 岁，且 `age_min <= age_max`） |
| 6 | 报告状态过滤 value 改为 int 2/3 | `backend/templates/admin/reports.html` | ❌ **P1** | 前端改为 2/3，但后端 `ObservationReport` 状态为 `1=已生成` / `2=已查看`，过滤/统计全部失效 |
| 7 | `AdminDashboardResponse` 新增今日统计字段 | `backend/domain/admin/admin_schemas.py` | ✅ | `today_reading_minutes` / `today_new_words` / `today_voice_count` 已添加 |
| 8 | `get_dashboard()` SQL 聚合今日统计 | `backend/domain/admin/service.py` | ✅ | 今日阅读分钟、新增生词、朗读次数均通过 SQL 聚合计算 |
| 9 | 仪表盘填充三个今日统计卡片 | `backend/templates/admin/dashboard.html` | ✅ | 三个卡片已绑定并渲染 |

---

## 四、P2 功能启用修复审查（6 项）

| # | 修复项 | 文件 | 结论 | 说明 |
|---|--------|------|------|------|
| 10 | 解除“发送逾期提醒”按钮禁用 | `backend/templates/admin/borrow.html` | ⚠️ P2 风险 | 按钮已启用并调用后端，但 `sent_count == 0` 时提示"该功能暂未实现"，会误导用户 |
| 11 | 图书列表改为 `/admin/api/books` | `backend/templates/admin/books.html` | ✅ | 已切换至管理端端点，返回含 `question_count` |
| 12 | 新增 `regenerate_certificate()` | `backend/domain/advancement/service.py` | ✅ | 重新生成证书编号、更新 `issued_at`、同步冗余字段 |
| 13 | 证书重新生成路由调用真实 Service | `backend/domain/admin/routers/admin_advancement_router.py` | ✅ | 路由已正确调用 |
| 14 | 启用证书“重新生成”按钮 | `backend/templates/admin/certificates.html` | ✅ | 按钮启用，成功后刷新列表 |
| 15 | 启用报告“批量生成”按钮 | `backend/templates/admin/reports.html` | ✅ | 按钮启用，成功后刷新列表 |
| 16 | 评语接口路径改为 `report_id` 并传 `admin.id` | `backend/domain/admin/routers/admin_reports_router.py` | ✅ | 路径参数已改，全局无旧调用点 |
| 17 | 评语保存改用 `report_id` | `backend/templates/admin/reports.html` | ✅ | 前端已改用 `report_id` |

---

## 五、缺陷清单（必须修复）

### 5.1 P1 严重错误

#### P1-1：报告状态过滤值与后端状态码错位

- **位置**：`backend/templates/admin/reports.html:19, 91-113`
- **现状**：
  - `<select>` 的 value 写死为 `2`（已生成）/`3`（已查看）
  - 后端 `backend/domain/report/models.py:25-26` 定义为 `STATUS_GENERATED = 1`、`STATUS_VIEWED = 2`
  - 报告生成时写入 `status=1`，标记已查看时写入 `status=2`
- **影响**：
  - 状态过滤永远无结果
  - 顶部统计卡片基于错误值计算，永远显示 0
  - 状态文本渲染写死为 `r.status === 3 ? '已查看' : '已生成'`，与真实状态错位
- **修复建议**：
  - 前端 value 改为 `1`/`2`
  - 统计逻辑同步改为 `1`/`2`
  - 状态文本判断改为 `r.status === 2 ? '已查看' : '已生成'`

### 5.2 P2 风险项

#### P2-1：证书弹窗展示“假数据”

- **位置**：`backend/templates/admin/certificates.html:166-197`、`backend/domain/advancement/service.py:570-620`
- **问题**：`book_count` / `word_count` / `prev_level` 在 Service 返回的证书对象中不存在，前端用 `|| 0` 或 `-` 占位，用户看到的数据是虚假的
- **修复建议**：
  - 方案 A（推荐）：在 `list_certificates` / `get_certificate` 中聚合或冗余这些字段
  - 方案 B：如果业务不需要，前端移除这些占位展示

#### P2-2：逾期提醒按钮误导文案

- **位置**：`backend/templates/admin/borrow.html:211-225`
- **问题**：当没有逾期记录时，`sent_count == 0`，前端提示"该功能暂未实现，敬请期待"
- **影响**：功能实际已实现，用户会被误导
- **修复建议**：`sent_count === 0` 时提示"当前无逾期记录"；`sent_count > 0` 时提示"已发送 N 条提醒"

### 5.3 P3 遗留问题

| # | 问题 | 位置 | 建议 |
|---|------|------|------|
| P3-1 | `get_dashboard()` Service 重复实现 | `backend/domain/admin/service.py` 与 `backend/domain/admin/services/dashboard_service.py` | 合并或删除 `AdminDashboardService` |
| P3-2 | 证书页面过滤失效 | `backend/templates/admin/certificates.html` | `renderTable()` 未设置 `row.dataset.level` / `row.dataset.period`，导致搜索/级别/时间段过滤不生效 |
| P3-3 | 图书统计使用当前页数量 | `backend/templates/admin/books.html` | 统计应基于后端 `total`，而非 `books.length`（分页 20 条） |

### 5.4 静态检查失败

| # | 问题 | 位置 | 修复 |
|---|------|------|------|
| F401 | `decimal.Decimal` 未使用导入 | `backend/domain/admin/services/order_service.py:6:21` | 删除该导入或运行 `ruff check backend/ --fix` |

### 5.5 接口一致性异常

| # | 接口 | 状态 | 说明 | 修复建议 |
|---|------|------|------|----------|
| API-1 | `GET /admin/api/certificates` | 404 | 前端实际调用 `/admin/api/advancement/certificates` | 确认是否保留该路径；若保留则添加别名路由 |
| API-2 | `GET /admin/api/reports` | 404 | `ARCHITECTURE.md` 声明存在，但实际仅注册 `/admin/api/reports/observation` | 补充 `/admin/api/reports` 汇总列表接口，或更新架构文档 |

---

## 六、工程师与 QA 路由判定

| 问题 | 责任方 | 判定依据 |
|------|--------|----------|
| 报告状态过滤值错误 | Engineer | 前端 value 与后端状态码不一致，属于代码实现错误 |
| 证书弹窗数据缺失 | Engineer | Service 未返回前端展示所需字段 |
| 逾期提醒误导文案 | Engineer | 前端文案与后端实现状态不匹配 |
| Ruff F401 | Engineer | 源码未使用导入 |
| `/admin/api/reports` 404 | Engineer | 路由实现与架构文档不一致 |
| `/admin/api/certificates` 404 | Engineer / PM | 需确认是否为保留路径 |
| pytest/behave/formal_test 全绿 | NoOne | 动态测试与实际输出一致 |

---

## 七、修复建议清单

### 必须立即修复（阻塞交付）

1. **P1-1**：`reports.html` 状态过滤 value 改为 `1`/`2`，统计与状态文本同步修改
2. **Ruff F401**：删除 `backend/domain/admin/services/order_service.py:6` 的 `decimal.Decimal` 导入
3. **API-2**：确认 `/admin/api/reports` 是否保留；若保留则补充路由

### 强烈建议修复（影响用户体验）

4. **P2-1**：补充证书弹窗真实数据或移除假数据展示
5. **P2-2**：修正逾期提醒按钮提示文案

### 下一阶段清理（P3）

6. 合并/删除重复的 `get_dashboard()` 实现
7. 修复证书页面过滤失效
8. 图书统计基于 `total` 而非当前页数量
9. 确认 `/admin/api/certificates` 路径是否保留

---

## 八、最终结论

| 维度 | 状态 |
|------|------|
| 动态功能测试 | ✅ 通过（pytest 100、behave 138、formal_test 119） |
| 代码静态质量 | ❌ 未通过（1 处 Ruff 错误） |
| 前端功能正确性 | ❌ 未通过（报告状态过滤完全失效） |
| 接口一致性 | ❌ 未通过（`/admin/api/reports` 缺失） |
| 服务稳定性 | ✅ 通过（无新增 500） |

**综合评定：有条件通过 / 需修复后复测**

当前代码不建议直接上线。请先修复 3 个阻塞项，再运行 `ruff check backend/` 和 5 个管理端接口抽查验证。

---

## 九、附录：原始分项报告

- 工程师代码审查：`deliverables/audit-2026-07-06/p1p2-code-review.md`
- QA 测试报告：`deliverables/audit-2026-07-06/p1p2-test-report.md`
