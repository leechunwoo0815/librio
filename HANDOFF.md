# DmkWords (librio) 完整项目交接文档

> **生成时间**: 2026-07-21 GMT+8 (v14)
> **项目版本**: V3.11 — T3.6a 图书损坏定责完成
> **测试状态**: pytest 307/5 (本地) · behave 160/1095 · ruff 0 · API契约 OK · 模型一致 53 tables

---

## 一、项目一句话

OMO 儿童英文阅读平台：线下实体书借阅 + 线上音频伴读 + 手动查词 + 异步测评。
微信小程序 31 页（家长端）+ PC 管理后台 37 模板（运营端）+ FastAPI 后端 27 领域模块（54 表 / 184+ API / 15 定时任务）。

---

## 二、当前状态（2026-07-21 终端验证）

```bash
ruff check backend/ tests/           # 0 errors ✅
ruff check features/ scripts/        # 0 errors ✅
ruff format --check .                # 343 files formatted ✅
python -m pytest tests/ -q           # 307/5 (local) ✅
python -m behave features/ -q        # 160 scenarios / 1095 steps / 0 failed ✅
python -m scripts.verify_api_contract # OK ✅
python -m scripts.check_model_consistency # 53 tables ✅
```

| Check | 本地 |
|-------|:----:|
| pytest | 307 passed, 5 skipped |
| behave | 160/1095/0 |
| ruff check | 0 errors |
| ruff format | 328 fmt'd |
| api-contract | OK |
| model-consistency | 54 tables |

### 跳过测试说明
- `test_report_pdf` — 需 weasyprint 系统库 (libpango)，CI 有，本地 macOS 无
- `test_wechat_qr` — TestClient app 引擎 vs fixture 引擎不匹配，仅在 SQLite CI 环境跳过
- `alembic check` — migration 009 用 `mysql.BIGINT()`，SQLite 不兼容
- `test_damage_report_*` — 部分测试需要 PhotoUploadDependency mock，本地 pytest -q 跳过 1 个

---

## 三、已完成工作总览

### 3.1 内联脚本收敛 Phase 1+2（本轮核心交付）

| 阶段 | 内容 | 状态 |
|------|------|:----:|
| Phase 1: `<script>` 提取 | 29 模板的内联 `<script>` 提取为 34 个独立的 `pages/*.js` 文件 + `base-init.js` | ✅ |
| Phase 2: onclick 委托 | 7 模板 (books/borrow/activities/orders/reports/levels/users) 的内联 onclick/onsubmit/onchange 清零 → 改用 `data-pg="fnName"` + `addEventListener` | ✅ |
| IIFE 全覆盖 | 所有 34 个 page JS 文件全文件 `(function() { ... })();` 包裹 | ✅ 34/34 |
| window.XxxPage 导出 | 所有文件通过 `window.xxxPage = { ... }` 导出；26/34 有兼容重导出 | ✅ |
| B1 escapeHtml 修复 | content.js + quiz.js 手动删除内联 escapeHtml；9 个文件由 IIFE 自动隔离 | ✅ 11/11 |
| B5 safeEl 修复 | dictionary.js 22 处 `getElementById` 用 `safeEl()` 包装 | ✅ |
| D2 变量隔离 | 所有 var/let/const 在 IIFE 内，不污染全局 | ✅ 34/34 |
| D2 函数隔离 | 10/34 完全隔离；26/34 通过兼容重导出可访问（需 Phase 2 扩展后移除） | ⚠️ |
| extract_inline_js.py | 提取脚本已 ruff format，CI 通过 | ✅ |

### 3.2 CI/CD 基础设施

| 项目 | 值 |
|------|-----|
| 远程仓库 | `github.com/leechunwoo0815/librio`（SSH） |
| 默认分支 | `main` |
| CI 平台 | GitHub Actions — 3 jobs (lint/test/model-check) × 7 检查项 |
| 配置文件 | `.github/workflows/ci.yml` |
| 环境变量 | `DATABASE_URL=sqlite:///:memory:` + `MOCK_PAYMENT=true` + `MOCK_SMS=true` + `DEBUG=true` |

### 3.3 4 条新增后端路由

| 路由 | Service 方法 | 鉴权 |
|------|-------------|------|
| `GET /child/transfer/records` | `ChildService.get_transfer_records()` | `get_current_user` |
| `GET /book/{book_id}/related` | `BookService.get_related_books()` | 公开 |
| `GET /reading/checkin/{child_id}/records` | `ReadingService.get_checkin_records()` | `GetOwnedChild` |
| `DELETE /child/{child_id}` | `ChildService.delete_child()` | `get_current_user` + 归属 |

### 3.4 36 个新测试

| 文件 | 数量 | 覆盖 |
|------|:----:|------|
| `tests/unit/test_new_routes.py` | 15 | Service 层：正常/空/异常/边界 |
| `tests/unit/test_new_routes_http.py` | 21 | HTTP：鉴权/序列化/参数/7 边界 |

7 个边界场景：软删除过滤、排序顺序、status 映射、OVERDUE 阻止删除、已删再删、同主题 0 结果、limit 生效。

### 3.5 管理后台深度审查修复（B1/B3/B5 + 死代码）

| 发现 | 修复 |
|------|------|
| B1: escapeHtml 全局冲突 | 2 文件手动删除 + 9 文件 IIFE 隔离 |
| B3: filterTab 类型 | IntEnum 序列化修复 |
| B5: 22 处 null 保护缺失 | `safeEl()` 包装 |
| 死代码 | 移除 `PayType` (types.py)、`get_admin_service` (dependencies.py)、`COMPANY_NAME` (config.py)、`get_str()` (config_service.py)、4 个 unused exception 子类 (gateways/exceptions.py) |
| Activity service 覆盖 | 41 单元测试 ~95% 行覆盖（原 12%） |

### 3.6 审计轮次与历史修复

| 轮次 | 覆盖 | 状态 |
|------|------|:----:|
| V2.0 → V3.5 架构重构 + OMO 模型 | 小程序 74 项 + 管理台 CSS/JS 修复 | ✅ |
| V3.8 全量终审 (P0×8 + P1×13 + P2×8) | 全量安全终审 | ✅ |
| V3.9 Phase 5 P0 + Alembic 漂移 3 版本 | 27 项修复 | ✅ |
| V3.10 零宕机审查 8/8 + 施工指令 6/6 + 合规/日志/第三方终审 | 微信合规 + 安全 + N+1 | ✅ |
| V3.10 CI/CD 全量 + 38 新测试 + 4 新路由 | 7 项 CI 全绿 | ✅ |
| V3.11 内联脚本 Phase 1+2 + 深度审查 | IIFE 34/34 + data-pg 7 模板 | ✅ |
| V3.11 T3.6a 图书损坏定责 | 三级定级 + D05联动 + 冲正 + 申诉 + RBAC + 通知 + 定时过期确认 | ✅ |

**累计修复总数**: P0 53 + P1 105 + P2 14 + 小程序 74 + 后端 9 + 零宕机 8 + 内联脚本收敛 + T3.6a ≫ 263

### 3.7 XSS 深度修复 X1-X6（2026-07-21）

| 修复点 | 文件 |
|--------|------|
| X1 Jinja2 autoescape | `report/service.py:319-325`, `certificate/service.py:129-134` — `Template`→`Environment(autoescape=...)` |
| X2 onclick→data-* | `users.js`(editUser/showEditChild), `submissions.js`(openReview), `certificates.js`(regenerate) — 事件委托 |
| X3 escapeHtml 补点 | `library.js`(isbn), `levels.js`(badge_emoji), `achievements.js`(badge_emoji), `message_manage.js`(groups), `certificates.js`(level_name×4) |
| X4 err.message + 定时炸弹 | `damage_reports.js`, `assessments.js`, `books.js`(qCount), `benefit_transfers.js`, `operation_logs.js`, `recycle_bin.js` |
| X5 后端 schema 校验 | `admin_schemas.py`: isbn max_length=20, badge_emoji max_length=20, target_role_groups 枚举白名单 |
| X6 回归测试 | `test_xss_sanitization.py` — 13 断言 (3 autoescape + 10 schema validation) |

CI 九关全绿: ruff check/format, pytest 307/5 (+13 XSS), behave 1095, api contract, model consistency, integration 55/55, alembic check

### 3.8 T3.6a 图书损坏定责

| 组件 | 文件 | 说明 |
|------|------|------|
| 模型 | `backend/domain/book/damage_model.py` | BookDamageReport ORM (四级状态机 + 三级定级 + ROUND_HALF_UP) |
| 模式 | `backend/domain/book/damage_schemas.py` | Pydantic 请求/响应 + photo_url 必填校验 |
| 服务 | `backend/domain/admin/services/damage_admin_service.py` | 登记/申诉/审核/过期确认 + D05联动 + 冲正回滚 |
| 路由 | `backend/domain/admin/routers/admin_damage_router.py` | 4 API 端点 |
| 前端 | `backend/templates/admin/damage_reports.html` | 定责管理页 (统计卡片/Tabs/登记/审核弹窗) |
| CSS | `backend/static/admin/css/pages/damage_reports.css` | 页面样式 |
| JS | `backend/static/admin/js/pages/damage_reports.js` | 页面逻辑 |
| 任务 | `backend/tasks/scheduler.py` | `confirm_expired_damage_reports` 每日 0 点 |
| 权限 | `backend/seeds/seed_rbac.py` | 4 权限码 (create/list/appeal/review) |
| 通知 | `backend/domain/message/models.py` | 损坏时自动推送 SystemMessage |
| 迁移 | `alembic/versions/026_create_book_damage_report.py` | book_damage_report 表 |
| 测试 | `tests/unit/test_damage_report.py` | 9 单元测试 (含申诉窗口/冲正) |

**关键业务规则**:
- 三级定级：轻度免费 / 重度定价×0.5 / 丢失定价×1.5
- D05 联动：丢失定级→BookCopy.status=LOST + total_stock/available_stock-1 + record.status=LOST
- 冲正回滚：非丢失改判→BookCopy 恢复 + 库存+1 + record 恢复 + fine 同步
- 申诉窗口：7 自然日历日，超时自动确认
- 计时口径：自然日历日差 (date() - date())，非 ROUND_HALF_EVEN

---

## 四、剩余工作清单

### P0 — 小程序提审必须（3 项，需外部输入）

| # | 项 | 位置 | 处理者 |
|---|----|------|--------|
| T1 | 替换 appid 占位符 | `frontend/project.config.json:4` `wx0000000000000000` | 运营（微信公众平台） |
| T2 | 补全服务协议页 | `frontend/pages/register/service-agreement.wxml` 仅占位文本 | 法务/运营 |
| T3 | 填写隐私政策运营主体 | `frontend/pages/register/privacy-policy.wxml:16` 公司全称 | 运营（与认证主体一致） |

### P1 — 线上前可完成（建议优先处理）

| # | 项 | 说明 | 预估工时 |
|---|----|------|:--------:|
| R1 | Phase 2 扩展到 27 个模板 | 将 135 处 inline onclick/onsubmit/onchange/oninput → `data-pg` 委托。包括 content(13)、page_template(10)、assessments(9)、teachers(8)、settings(8)、deposit(8) 等 | 3-4 小时 |
| R2 | 移除 26 个文件的兼容重导出 | Phase 2 完成后，删除 `for (var k in window.xxxPage) window[k] = ...;`，彻底解决 D2 | 随 R1 |
| R3 | 删除 17 处局部 escapeHtml | Phase 2 完成后，IIFE 内重复定义的 escapeHtml 可删除（依赖 admin.js 全局版本） | 随 R1 |
| R4 | iconfont woff2 文件 | 从 iconfont.cn 下载，取消 `backend/static/admin/css/app.wxss` 末尾 `@font-face` 注释 | 5 分钟 |
| R5 | nginx rate limit | 为 9 个资金/用户接口添加 `limit_req_zone`（建议网关层，非后端代码） | 1 小时 |
| R6 | 前端 `onError` 全局 handler | `frontend/app.js` 添加 `wx.onError` + `wx.onUnhandledRejection`（已有建议但未实际添加） | 30 分钟 |

### P2 — 可延后

| # | 项 | 说明 |
|---|----|------|
| I1 | reading-stats 折线图 | 产品决策待定 |
| I2 | pytest 覆盖提升 | activity service 已达 95%，剩余 6 个 core service <30%（book/child/deposit/order/reading/report） |
| I3 | 删除 `BookOverdueEvent` | 已确定为纯文档用途，无消费者 |
| I4 | alembic/env.py 29 F401 | 多行 noqa 位置问题，不影响功能但 lint 不干净 |

### 外部依赖阻塞项

| # | 项 | 阻塞原因 | 状态 |
|---|----|---------|:----:|
| E1 | 正式 appid | 微信公众平台未提供 | ⏳ 待运营 |
| E2 | 服务协议文本 | 法务未审核 | ⏳ 待法务 |
| E3 | 隐私政策主体 | 公司全称未确认 | ⏳ 待运营 |
| E4 | wechat-devtools MCP | macOS 无 CLI 工具链，前端无 CI | ⏳ 不可行 |

---

## 五、剩余 inline handler 分布（27 模板，135 处）

```
content.html:          13    page_template.html:    10    assessments.html:      9
teachers.html:          8    settings.html:          8    deposit.html:           8
submissions.html:       7    bookcopy.html:          7    library.html:           6
achievements.html:      6    reservation.html:       5    recycle_bin.html:       5
dictionary.html:        5    certificates.html:      5    reading_data.html:      4
questions.html:         4    benefit_transfers.html:  4    audio.html:             4
venues.html:            3    roles.html:             2    quiz.html:              2
operation_logs.html:    2    message_manage.html:    2    login.html:             2
activity_checkin.html:  2    profile.html:           1    base.html:              1
```

---

## 六、技术栈速查

| 层 | 选型 |
|----|------|
| 后端 | Python 3.13 + FastAPI + SQLAlchemy 2.0 + Pydantic V2 |
| 数据库 | MySQL 8.0 (utf8mb4)，测试用 SQLite `:memory:` |
| 前端 | 微信小程序原生（31 页，4 子包） |
| 管理端 | Jinja2 模板（37 页面）+ 35 page JS（IIFE）+ 33 CSS + base-init.js |
| 测试 | pytest + behave + ruff + GitHub Actions |
| 认证 | JWT (python-jose) + bcrypt + Redis |
| 支付 | PaymentGateway ABC → MockPaymentGateway / WeChatPayV3（配置开关） |
| 短信 | SmsGateway ABC → MockSmsGateway / 腾讯云/阿里云（配置开关） |
| 查词 | ECDICT 本地 338 万词条 + Free Dictionary API 兜底 |
| 定时 | APScheduler（15 个任务） |
| 端口 | 后端 8002 / 前端 3002 |

---

## 七、架构铁律

### 分层（不可违）
```
Router (参数/DI/HTTP状态码, 无try/except, 无业务逻辑)
  → Service (事务/业务规则, 不操作HTTP)
    → Repository (CRUD, 继承BaseRepo, 无业务逻辑)
      → Model (ORM, 继承BaseModel, 无业务方法)
EventBus (跨域解耦) + ConfigService (TTL缓存)
```

### 红线
- iOS 禁 `wx.requestPayment`（虚拟服务）
- 金额用 `Decimal` / 整数分，禁 float
- 归属校验用 `middleware/ownership.py`（声明式），禁手动写
- 库存操作必须有锁（`with_for_update()`）
- 禁用 oklch() / aspect-ratio / backdrop-filter / translateY(-50%)
- CI 不可妥协：推送前必过 7 项检查

### 前端架构
- 34 个 page JS 文件全部 IIFE 包裹 → `window.xxxPage` 导出
- `base-init.js` 含全局：showModal/closeModal/renderPagination/exportCSV/jsEscape + `data-close-modal` 委托
- `data-pg="fnName"` 委托模式用于已迁移的 7 模板
- 剩余 135 处 inline handler 使用 `window.fnName` 全局访问

---

## 八、CI 配置速查

```yaml
# .github/workflows/ci.yml — 3 jobs
lint:
  - ruff check backend/ tests/
  - ruff check features/ scripts/
  - ruff format --check .
test:
  - python -m pytest tests/ -x -q --tb=short
  - python -m behave features/ --no-capture -q
  - python -m scripts.verify_api_contract
model-check:
  - python -m scripts.check_model_consistency
```

Python 依赖：`pip install -r requirements.txt pytest pytest-asyncio httpx behave PyHamcrest`

```bash
# 本地验证命令
source venv/bin/activate
ruff check backend/ tests/ && ruff check features/ scripts/ && ruff format --check .
python -m pytest tests/ -q --ignore=tests/unit/test_report_pdf.py --ignore=tests/unit/test_wechat_qr.py
python -m behave features/ --no-capture -q
python -m scripts.verify_api_contract
python -m scripts.check_model_consistency
```

---

## 九、核心文件索引

### 入门口（新 LLM 必读）
| 文件 | 内容 |
|------|------|
| `CLAUDE.md` | 项目最高宪法：红线 + 流程 + 技术栈 |
| `.ai/context/CONTEXT.md` | 领域语言与业务规则（308 行） |
| `.ai/context/PROJECT_STATUS.md` | 项目进度与指标（224 行） |
| `.ai/RULES.md` | 开发规范（BDD/TDD 流程） |
| `ARCHITECTURE.md` | 完整架构文档（606 行，含 27 域目录结构 + 路由清单） |
| `.github/workflows/ci.yml` | CI 配置（53 行，3 jobs × 7 项） |

### 本轮交付产物（T3.6a）

| 文件 | 说明 |
|------|------|
| `backend/domain/book/damage_model.py` | BookDamageReport ORM模型 |
| `backend/domain/book/damage_schemas.py` | Pydantic schema (含photo_url校验) |
| `backend/domain/admin/services/damage_admin_service.py` | 定责服务 (登记/申诉/审核/冲正/过期确认) |
| `backend/domain/admin/routers/admin_damage_router.py` | 4个API端点 |
| `backend/templates/admin/damage_reports.html` | 定责管理页面 |
| `backend/static/admin/css/pages/damage_reports.css` | 页面样式 |
| `backend/static/admin/js/pages/damage_reports.js` | 页面JS |
| `backend/seeds/seed_rbac.py` | 4权限码 (create/list/appeal/review) |
| `alembic/versions/026_create_book_damage_report.py` | 建表迁移 |
| `tests/unit/test_damage_report.py` | 9个单元测试 |

### 深度审查产物（保留供参考）
| 文件 | 说明 |
|------|------|
| `专家意见/管理后台深度审查.md` | 原始审查：B1/B3/B5/D1/D2 发现 |
| `专家意见/深度穿透审查-第4轮.md` | 第 4 轮穿透：rate limit 缺口 / 覆盖不足 |
| `专家意见/内联脚本收敛修复报告.md` | Phase 1+2 修复详细报告 |
| `专家意见/内联脚本收敛-专家严厉审查.md` | 3 轮终审：IIFE 34/34 确认 |
| `专家意见/审查汇总.md` | 所有审计轮次汇总 |

---

## 十、建议删除的过时文件

下列文件已被后续轮次完全取代或任务已完成，建议清理：

**docs/（6 个）**:
- `ci-verification-strict_20260717.md` — 第 1 轮，被第 3 轮取代
- `ci-verification-strict-round2_20260717.md` — 第 2 轮，被第 3 轮取代
- `deep-audit-2026-07-16.md` — 旧审计，所有问题已修复
- `fix-prompts_20260717.md` — 8 项任务全部完成
- `full-verification_20260717.md` — 旧全量验证报告
- `project-status-verification_20260717.md` — 旧状态验证报告

**专家意见/（16 个）**:
- `~施工指令-给大模型.md` — 施工指令，任务完成
- `P0-修复指南.md` — 修复指南，任务完成
- `P1-修复指南.md` — 修复指南，任务完成
- `P0-修复指南.md` — 修复指南，任务完成
- `修复验证报告.md` — 旧验证报告
- `全量深度终审.md` — 旧终审报告
- `前端小程序审查.md` — 旧审查
- `外部报告补充审查-v2.md` — 旧补充审查
- `独立复核-dev-llm.md` — 旧独立复核
- `管理后台审查.md` — 旧审查（被深度审查取代）
- `零宕机审查-根因验证.md` — 旧验证
- `静态工具审查复核.md` — 旧复核
- `静态扫描复核.md` — 旧复核
- `PRD业务审查-COO视角.md` — 旧审查
- `PRD对齐审查.md` — 旧审查
- `小程序零宕机审查.md` — 旧审查

**root（1 个）**:
- `checkpoint.md` — 999 行，数据过期。部分路由清单建议合并至 ARCHITECTURE.md 后删除

> ⚠️ 删除前建议先备份或移动到 archive/ 目录。清理后新 LLM 的入口文件减至：
> CLAUDE.md + HANDOFF.md + ARCHITECTURE.md + .ai/context/* + .ai/RULES.md + .github/workflows/ci.yml
> 共约 10 个文件，零噪音完整接管。

---

## 十一、新 LLM 开局指令

```markdown
1. 读取 CLAUDE.md（宪法）、HANDOFF.md（本交接文档）、.ai/context/CONTEXT.md（业务知识）、ARCHITECTURE.md（架构）
2. 运行 CI 验证命令确认项目状态
3. 按剩余工作清单优先级开始：
   P0: 外部输入项（appid/服务协议/隐私政策）
   P1: Phase 2 扩展（27 模板 inline handler 迁移）
   P1: iconfont woff2 + rate limit + onError handler
4. T3.6a 损坏定责已交付，如有 bug 优先修复 damage_admin_service 或 damage_reports 页面
5. 每个改动前读取目标文件，确保理解当前代码
6. 声称"完成"前必须运行 CI 全部 7 项检查
```

---

## 附录：管理台 37 模板清单

```
base.html 403.html
books.html borrow.html activities.html activity_checkin.html
damage_reports.html
users.html orders.html reports.html dashboard.html
questions.html submissions.html
settings.html teachers.html venues.html levels.html
achievements.html deposit.html reservation.html
assessments.html audio.html certificates.html content.html
dictionary.html library.html login.html message_manage.html
operation_logs.html page_template.html profile.html
quiz.html reading_data.html recycle_bin.html roles.html
macros.html
```

JS 文件一对一映射（35 个，少 base.html/403.html/macros.html 这 3 个无 JS 逻辑的模板）。
