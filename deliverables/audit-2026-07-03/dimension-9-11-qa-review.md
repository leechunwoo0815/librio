# MegaWords 管理平台企业级审查报告

## 审查概要

- **审查日期**：2026-07-03
- **审查维度**：维度 9（测试覆盖审查）、维度 11（前端管理页面审查）
- **发现问题总数**：18 项
  - 致命（P0）：1 项
  - 严重（P1）：7 项
  - 一般（P2）：7 项
  - 建议（P3）：3 项
- **测试运行结果**：
  - `pytest tests/unit/`：100 个用例收集，94 通过，6 失败（源码返回类型错误）
  - `venv/bin/behave features/`：137 个场景，134 通过，4 报错（同源源码返回类型错误）
  - `python scripts/formal_test_v2.py`：119 个用例，101 通过，18 失败（测试脚本端点路径过期导致假阴性）

---

## 维度 9：测试覆盖审查

### 维度结论

**有条件通过**

单元测试与 BDD 场景覆盖了主要业务路径，测试质量尚可（无假测试、步骤定义清晰）。但存在关键源码缺陷导致测试无法通过，且大量 Service 方法、并发场景、API 集成路径、事务回滚场景缺失测试，无法支撑企业级上线要求。

### 发现的问题

#### [P0] Service 方法返回类型与签名不一致，导致 6 个单元测试 + 4 个 BDD 场景失败
- **位置**：
  - `backend/domain/advancement/service.py:127`
  - `backend/domain/book/service.py:56`
  - `backend/domain/book/service.py:88`
- **现状**：
  - `AdvancementService.start_quiz` 声明返回 `QuizResponse`，实际执行 `result.model_dump()` 返回 dict。
  - `BookService.get_book_detail` 声明返回 `BookResponse`，实际返回 dict。
  - `BookService.create_book` 同样返回 dict。
- **问题**：类型签名与实现不一致，调用方按 Schema 对象访问属性（`.id`、`.title`）时抛出 `AttributeError`。
- **影响**：
  - 单元测试失败：`test_start_quiz`、`test_submit_answers_*`、`test_get_quiz_questions`、`test_get_book_detail`。
  - BDD 场景报错：`老师出卷`、`测验通过更新借阅记录状态`、`测验未通过`、`测验通过后词数计入积分`。
  - 该问题同时影响真实 API：Router 层若直接序列化 dict，可能导致 OpenAPI 响应模型不一致。
- **修复建议**：移除 `result.model_dump()`，直接返回 Pydantic Schema 对象；由 FastAPI 自动处理 JSON 序列化。统一检查所有 Service 的返回类型注解与实现。
- **优先级**：P0

#### [P1] 单元测试未覆盖全部 Service 方法，大量业务域缺失测试
- **位置**：`tests/unit/` 19 个测试文件
- **现状**：100 个单元测试仅覆盖 advancement、book、borrow、certificate、child、deposit、leaderboard、observation_report、profile、reservation、teacher、vocabulary 等部分域。22 个业务域中至少以下 Service 没有对应单元测试：
  - `backend/domain/admin/service.py`
  - `backend/domain/activity/service.py`
  - `backend/domain/assessment/service.py`
  - `backend/domain/audio/service.py`
  - `backend/domain/bookshelf/service.py`
  - `backend/domain/dictionary/service.py`
  - `backend/domain/evaluation/service.py`
  - `backend/domain/message/service.py`
  - `backend/domain/order/service.py`（仅 models 测试）
  - `backend/domain/parent_course_time/service.py`
  - `backend/domain/quiz_question/service.py`
  - `backend/domain/reading/service.py`
  - `backend/domain/refund/service.py`
  - `backend/domain/report/service.py`
  - `backend/domain/user/service.py`
  - `backend/domain/voice/service.py`
- **问题**：核心财务、内容、消息、用户、阅读等域的业务逻辑缺乏单元级别防护。
- **影响**：回归时无法快速发现业务逻辑缺陷；重构风险高。
- **修复建议**：按模块补齐 Service 单元测试，优先覆盖订单、押金、退款、借阅、活动报名等资金/库存敏感域。
- **优先级**：P1

#### [P1] 缺少并发场景测试
- **位置**：`tests/unit/`、`features/`
- **现状**：未找到任何针对竞态条件的测试，如：
  - 活动报名库存扣减并发；
  - 预约取书锁定/释放并发；
  - 押金退款与借书操作的竞态；
  - 图书库存扣减并发。
- **问题**：PRD 中多次强调并发安全（活动报名 `WHERE current_participants < max_participants`、72 小时库存释放等），但无自动化测试验证。
- **影响**：高并发下可能出现超卖、重复退款、库存不一致等生产事故。
- **修复建议**：使用 `pytest-asyncio` + `asyncio.gather` 或线程池模拟并发请求，为关键路径添加并发回归测试。
- **优先级**：P1

#### [P1] 缺少 API 端点集成测试
- **位置**：`tests/unit/` 仅测试 Service 层
- **现状**：单元测试全部直接调用 Service，未使用 `TestClient` 调用 FastAPI 端点。`scripts/formal_test_v2.py` 是外部脚本，不属于 pytest 套件。
- **问题**：无法验证 Router 层参数绑定、认证、`response_model`、HTTP 状态码、错误响应格式。
- **影响**：可能出现 Service 正确但接口返回 422/500 的情况；无法保障 OpenAPI 契约。
- **修复建议**：新增 `tests/integration/` 目录，使用 `fastapi.testclient.TestClient` 为管理端和家长端关键端点编写集成测试。
- **优先级**：P1

#### [P1] 缺少数据库事务回滚测试
- **位置**：`tests/unit/` 全部测试文件
- **现状**：测试使用 SQLite 内存数据库，每个测试重新创建 schema，但未验证业务方法内部的事务边界（如借书创建 BorrowRecord + 扣减库存是否在同一事务；还书失败是否回滚）。
- **问题**：无法确认跨表操作的原子性，无法发现事务边界遗漏。
- **影响**：生产环境 MySQL 下可能出现部分提交导致的数据不一致。
- **修复建议**：针对跨表写操作（借阅、还书、退款、订单创建）添加事务回滚断言；必要时注入异常并断言两侧数据均未变更。
- **优先级**：P1

#### [P2] BDD 场景数量与文档不符（实际 137，文档声明 138）
- **位置**：`features/*.feature`
- **现状**：通过 `grep -c "^\s*场景"` 统计 16 个 feature 文件共 137 个场景，但 `docs/compose/specs/expert-audit-prompt.md` 与项目背景写明 138 个场景。
- **问题**：文档与代码不一致，可能遗漏了一个用户故事或场景。
- **影响**：需求跟踪不完整，审查方无法确认是否缺失关键验收场景。
- **修复建议**：核对 PRD 与 feature 文件，补齐缺失场景或修正文档。
- **优先级**：P2

#### [P2] 集成测试脚本端点路径过期，产生 18 个假阴性失败
- **位置**：`scripts/formal_test_v2.py:88-134`、`scripts/formal_test_v2.py:257-270`
- **现状**：脚本使用 `/admin/dashboard`、`/admin/users`、`/admin/config`、`/admin/venues`、`/admin/teachers`、`/admin/orders`、`/admin/operation-logs`、`/admin/recycle-bin` 等路径，但后端实际路由前缀为 `/admin/api/*`（除 `/admin/login`、`/admin/view/*`、上传/导出等少数路径外）。
- **问题**：后端服务可正常启动且路由正确，但测试脚本路径错误导致 404，误判为失败。
- **影响**：CI/交付报告中的 84.9% 通过率失真；运维/QA 会误判管理端接口不可用。
- **修复建议**：按 `backend/main.py` 中的实际路由批量更新 `formal_test_v2.py` 的管理端路径为 `/admin/api/*`；视图页面路径保持 `/admin/view/*`。
- **优先级**：P2

#### [P2] 边界值与异常路径覆盖不足
- **位置**：`tests/unit/*.py`、`features/*.feature`
- **现状**：
  - 数值边界：缺少负数 page/page_size、超大 ID、空字符串、极长字符串等测试。
  - 异常路径：部分 Service 仅测试正常路径（如 `TeacherService.create_schedule`、`VocabularyService.lookup_word_not_found` 虽已覆盖，但大量更新/删除异常未覆盖）。
  - 权限边界：BDD 未覆盖 STAFF/TEACHER 角色的管理端权限裁剪。
- **问题**：无法保证系统在非法输入下的鲁棒性。
- **影响**：容易出现 500 或数据污染。
- **修复建议**：为每个 Service 的公共方法补充异常分支和边界值测试；在 feature 中增加“无权限访问”“已删除资源”等负面场景。
- **优先级**：P2

#### [P2] 单元测试使用 SQLite，与生产 MySQL 存在方言差异
- **位置**：`tests/unit/*.py` 中多个 `create_engine("sqlite:///:memory:")` 调用
- **现状**：测试使用 SQLite 内存数据库，而生产为 MySQL 8.0。某些 SQLAlchemy 查询、JSON 字段、Decimal 精度、事务行为在两种数据库下表现不同。
- **问题**：可能掩盖 MySQL 特有的性能或兼容性问题。
- **影响**：测试通过但上线后出现未预期错误。
- **修复建议**：集成测试层使用与生产一致的 MySQL（Docker 或测试库），或在 CI 中增加 MySQL 兼容性测试。
- **优先级**：P2

#### [P3] 测试文件命名与注释语言不统一
- **位置**：`tests/unit/test_v2_book_extension.py`、`tests/unit/test_advancement_integration.py` 等
- **现状**：部分文件名使用英文，部分注释中英混杂；没有统一规范。
- **问题**：可读性稍差，不影响功能。
- **影响**：维护成本轻微上升。
- **修复建议**：统一使用中文注释/文档字符串，或统一使用英文，遵循项目规范。
- **优先级**：P3

---

## 维度 11：前端管理页面审查

### 维度结论

**有条件通过**

33 个管理页面整体结构完整，Token/API/错误处理基本实现统一，CRUD 页面具备列表、分页、搜索、删除确认、Toast 反馈等能力。但存在 1 个致命 JS 缺陷（全局表单提交拦截）、2 个页面 API 端点错误、1 个纯静态 mock 页面未接入后端等严重问题，必须修复后方可上线。

### 发现的问题

#### [P0] admin.js 全局拦截所有表单提交并重复提交，导致无 Authorization 头且 Content-Type 错误
- **位置**：`backend/static/admin/js/admin.js:345-364`
- **现状**：`DOMContentLoaded` 中为所有 `button[type="submit"]`/`input[type="submit"]` 绑定了提交监听器：
  ```javascript
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    ...
    return fetch(form.action || location.href, {
      method: form.method || 'POST',
      body: formData,
    })...
  });
  ```
  该 fetch 未附加 `Authorization` 头，也未将数据序列化为 JSON，而是直接发送 `FormData`。
- **问题**：
  1. 与各页面自身表单的 `onsubmit` 处理函数（如 `submitBook`、`submitTeacher`）重复触发，产生两次提交。
  2. 第二次提交没有携带 JWT，管理端接口会返回 401。
  3. 后端接口普遍期望 `application/json`，`FormData` 会导致 422。
- **影响**：绝大多数带表单的 CRUD 页面（图书、老师、场馆、级别、成就等）无法正常工作；登录后的核心管理功能不可用。
- **修复建议**：
  - 移除该全局表单拦截逻辑；各页面已自行通过 `api.post/put` 处理提交。
  - 如需要统一防重提交，仅提供 `submitWithLock` 工具函数，不要覆盖默认提交行为。
- **优先级**：P0

#### [P1] 内容管理页面（content.html）未接入后端，按钮仅关闭弹窗
- **位置**：`backend/templates/admin/content.html:82-120`
- **现状**：页面包含“上传 PDF 自动切页”“新增页面”“上传音频”等 UI，但所有保存/上传/处理按钮的 `onclick` 仅调用 `closeUploadModal()`、`closePageModal()`、`closeAudioModal()`，没有任何 `api.*` 或 `fetch` 调用。
- **问题**：内容管理（页面、音频、PDF 切页）完全不可用，属于未实现功能。
- **影响**：运营人员无法维护图书阅读内容，严重阻塞内容上线流程。
- **修复建议**：
  - 对接后端阅读/音频相关 API（如 `/admin/api/upload/*`、`/admin/api/reading/*` 或新增内容管理端点）。
  - 实现图书选择、页面列表加载、音频列表加载、PDF 上传、音频绑定等完整交互。
- **优先级**：P1

#### [P1] 操作日志页面 API 端点前缀错误
- **位置**：
  - `backend/templates/admin/operation_logs.html:54`
  - `backend/templates/admin/operation_logs.html:125`
- **现状**：
  - 列表接口调用 `/admin/operation-logs`。
  - 导出接口调用 `/admin/export/operation-logs`。
- **问题**：后端实际路由为 `/admin/api/operation-logs` 与 `/admin/api/export/{module}`，导致 404。
- **影响**：操作日志无法加载、无法导出，系统审计能力缺失。
- **修复建议**：将路径改为 `/admin/api/operation-logs` 和 `/admin/api/export/operation-logs`。
- **优先级**：P1

#### [P1] 回收站页面 API 端点前缀错误
- **位置**：`backend/templates/admin/recycle_bin.html:71`
- **现状**：回收站列表调用 `/admin/recycle-bin`。
- **问题**：后端实际路由为 `/admin/api/recycle-bin`。
- **影响**：回收站列表无法加载，软删除数据无法恢复或清理。
- **修复建议**：将路径改为 `/admin/api/recycle-bin`。
- **优先级**：P1

#### [P2] 登录页遗留调试 alert
- **位置**：`backend/templates/admin/login.html:46`
- **现状**：`<button type="button" ... onclick="alert('按钮被点击了！'); doLogin();">登 录</button>`
- **问题**：生产环境出现调试弹窗，影响用户体验与专业度。
- **影响**：每次点击登录都会弹出无意义提示。
- **修复建议**：移除 `alert('按钮被点击了！')`。
- **优先级**：P2

#### [P2] CSS 中仍存在大量硬编码颜色值，样式一致性不足
- **位置**：
  - `backend/static/admin/css/base.css:377-381`（`.level-1` ~ `.level-5`）
  - `backend/static/admin/css/pages/certificates.css:36-61`
  - `backend/static/admin/css/pages/*.css` 多处（共 129 处 `#rgb/hex/rgba`）
- **现状**：虽有 CSS 变量，但等级色、证书边框渐变、状态色等仍使用硬编码 `#e8f5e9`、`#d4a843`、`rgba(0,0,0,0.55)` 等。
- **问题**：主题切换、品牌色变更、深色模式支持困难；不同页面视觉不一致。
- **影响**：可维护性与设计一致性下降。
- **修复建议**：将等级、证书、状态色统一映射到 CSS 变量（如 `--level-1-bg`、`--cert-gold`），禁止新增硬编码颜色。
- **优先级**：P2

#### [P2] 图书上传使用原生 fetch 绕过统一 api 客户端
- **位置**：
  - `backend/templates/admin/booklist.html:430-432`
  - `backend/templates/admin/books.html:545-604`
- **现状**：图书封面上传、分片上传使用原生 `fetch` 并手动拼接 `Authorization: Bearer + localStorage.getItem('mw_admin_token')`，未使用 `api.request`。
- **问题**：Token 获取方式与 `admin.js` 的 `auth.getToken()` 不一致；错误处理、401 跳转、Toast 反馈均未复用统一逻辑。
- **影响**：上传失败时用户体验不一致；Token 管理分散。
- **修复建议**：将上传逻辑封装进 `admin.js` 的 `api.upload` 方法，统一处理 Token、进度、错误。
- **优先级**：P2

#### [P2] content.html 标题 block 被 HTML 内容污染
- **位置**：`backend/templates/admin/content.html:2-3`
- **现状**：
  ```html
  {% block title %}图书内容管理<!-- class alignment refs -->
  <div style="display:none" class="page-card page-drag-handle page-info page-num page-status page-thumb published"></div>
  {% endblock %}
  ```
  `title` block 中混入了 HTML 注释和 `div`。
- **问题**：Jinja 渲染后 `<title>` 标签内会包含 HTML，可能导致浏览器标签页标题异常，且破坏 HTML 语义。
- **影响**：页面标题显示异常；HTML 不规范。
- **修复建议**：将 `class alignment refs` 和隐藏 div 移出 `title` block，放到 `content` 或 `head` block 中。
- **优先级**：P2

#### [P2] operation_logs.html 与 recycle_bin.html 重复实现分页器
- **位置**：
  - `backend/templates/admin/operation_logs.html:107-122`
  - `backend/templates/admin/recycle_bin.html:146-161`
- **现状**：两个页面各自内联实现分页逻辑，未复用 `base.html` 提供的 `renderPagination`。
- **问题**：代码重复，分页样式/行为可能不一致。
- **影响**：维护成本上升，后续修改分页 UI 需要改多处。
- **修复建议**：统一调用 `renderPagination(containerId, total, page, pageSize, 'loadLogs')`/`'loadRecycle'`。
- **优先级**：P2

#### [P3] 仪表盘柱状图使用静态占位数据
- **位置**：`backend/templates/admin/dashboard.html:83-88`
- **现状**：阅读量统计图表的 4 个柱子高度写死为 `45%`、`62%`、`78%`、`90%`，未从 `/admin/api/dashboard` 获取真实数据。
- **问题**：数据概览页的部分图表为假数据。
- **影响**：运营人员无法通过图表了解真实阅读趋势。
- **修复建议**：后端 dashboard 接口返回阅读量趋势数据，前端动态渲染柱状图。
- **优先级**：P3

#### [P3] 部分页面大量使用内联样式
- **位置**：`backend/templates/admin/content.html`、`backend/templates/admin/message_manage.html`、`backend/templates/admin/books.html` 等
- **现状**：多处使用 `style="..."` 直接定义布局与颜色。
- **问题**：与 CSS 变量/类规范不一致，响应式与主题适配困难。
- **影响**：可维护性轻微下降。
- **修复建议**：逐步将内联样式抽离到页面级 CSS 文件，优先使用 base.css 中已定义的类。
- **优先级**：P3

---

## 测试运行结果详情

### 1. pytest 单元测试
```
cd /Users/litianyu/cc-projects/librio && pytest tests/unit/
=========================== test session starts ===========================
100 collected
94 passed, 6 failed, 5 warnings
```
**失败用例**：
- `tests/unit/test_advancement_service.py::test_start_quiz`
- `tests/unit/test_advancement_service.py::test_submit_answers_all_correct`
- `tests/unit/test_advancement_service.py::test_submit_answers_partial`
- `tests/unit/test_advancement_service.py::test_submit_answers_already_completed`
- `tests/unit/test_advancement_service.py::test_get_quiz_questions`
- `tests/unit/test_book_service.py::test_get_book_detail`

**错误根因**：Service 层将 Pydantic Schema 对象调用 `.model_dump()` 返回 dict，而测试/步骤定义按 Schema 对象访问属性。

### 2. behave BDD 测试
```
cd /Users/litianyu/cc-projects/librio && venv/bin/behave features/
15 features passed, 0 failed, 1 error, 0 skipped
134 scenarios passed, 0 failed, 4 error, 0 skipped
955 steps passed, 0 failed, 4 error, 11 skipped
```
**报错场景**：
- `features/advancement.feature:51  老师出卷`
- `features/advancement.feature:58  测验通过更新借阅记录状态`
- `features/advancement.feature:66  测验未通过`
- `features/advancement.feature:73  测验通过后词数计入积分（去重）`

**错误根因**：与 pytest 同源，均为 `AdvancementService.start_quiz` 返回 dict 导致 `quiz.id` 访问失败。

### 3. scripts/formal_test_v2.py 集成测试
```
总计: 119
通过: 101
失败: 18
通过率: 84.9%
```
**失败项全部为管理端路径错误**：脚本使用 `/admin/dashboard`、`/admin/users`、`/admin/config`、`/admin/venues`、`/admin/teachers`、`/admin/orders`、`/admin/operation-logs`、`/admin/recycle-bin` 等，后端实际为 `/admin/api/*`。

**结论**：18 个失败为测试脚本过期导致的假阴性，源码路由正确；但脚本本身需要更新才能作为有效回归测试。

---

## 总体结论

- **整体评级**：C（有条件通过，需修复关键缺陷）
- **关键风险项**：
  1. 前端 `admin.js` 全局表单拦截会导致管理端 CRUD 无法使用（P0）。
  2. Service 返回类型错误同时破坏单元测试与 BDD（P0/P1）。
  3. 内容管理页面未接入后端、操作日志/回收站端点错误，导致关键管理功能不可用（P1）。
  4. 测试覆盖存在大量盲区：并发、API 集成、事务回滚、多个 Service 缺失（P1）。
- **建议的修复优先级**：
  1. 立即修复 P0 的 `admin.js` 表单提交问题。
  2. 立即修复 Service 返回类型问题，恢复 10 个测试（6 单元 + 4 BDD）。
  3. 一周内补齐操作日志、回收站、内容管理页面的后端对接与端点修正。
  4. 两周内补齐缺失 Service 单元测试、并发测试、API 集成测试与事务回滚测试。
- **下一步行动项**：
  1. 由后端工程师修正 `AdvancementService.start_quiz`、`BookService.get_book_detail`、`BookService.create_book` 的返回类型。
  2. 由前端工程师移除 `admin.js` 的全局表单拦截，修正操作日志/回收站端点，实现 content.html 后端对接。
  3. 由 QA 更新 `scripts/formal_test_v2.py` 的管理端路径，并扩展测试矩阵。
  4. 修复后重新运行 `pytest`、`behave`、`formal_test_v2.py` 全量回归。
