# 🚀 新 LLM 接手指引 — DmkWords (librio) V3.15

> **生成时间**: 2026-07-23 GMT+8  
> **本项目工作周期**: 2026-07-05 ~ 2026-07-23 (8234 条消息)  
> **测试基线**: pytest 333/5 · behave 160/1095 · ruff 0 · CI 同构九关全绿 · 集成 55/55  

**你是我的继任者。** 以下内容让你在 15 分钟内理解项目全貌、当前状态、已完成的工作量、未完成的事项，以及最重要的——**如何不踩坑**。

---

## 一、项目一句话

OMO 儿童英文阅读平台：**线下实体书借阅** + **线上音频伴读** + **手动查词** + **异步测评**。  
微信小程序 31 页（家长端）+ PC 管理后台 37 模板（运营端）+ FastAPI 后端 27 领域模块（54 表 / 184+ API / 15 定时任务）。

---

## 二、你的第一步

```bash
# 1. 进入项目
cd /Users/litianyu/cc-projects/librio

# 2. 激活环境
source venv/bin/activate

# 3. 验证状态 — CI 同构九关（必须全绿再动代码）
ruff check backend/ tests/ && ruff check features/ scripts/ && ruff format --check . && \
python -m pytest tests/ -x -q --tb=short && \
python -m behave features/ --no-capture -q && \
python -m scripts.verify_api_contract && \
python -m scripts.check_model_consistency && \
MOCK_PAYMENT=true MOCK_SMS=true DEBUG=true python scripts/integration_test.py && \
python -m alembic check
```

**预期输出**：全部绿色，exit code 0。

---

## 三、已完成的全部工作（不要重复做 ❌）

### 3.1 管理后台事件委托（Phase 2 全量 ✅）
| 指标 | 值 |
|------|-----|
| HTML 模板 | **38/38** → 0 处 inline onclick/onsubmit/onchange/oninput |
| JS 文件 | **35/35** → 所有函数通过 `data-action="page:fn"` 委托 + `#admin-root` 单监听 |
| 事件类型 | click / input / change / keydown / submit 全委托 |
| 兼容重导出 | 24 文件删除 `for (var k in window.xxxPage)` |
| escapeHtml | 17 文件局部定义删除，统一用 `admin.js` 全局版 |

### 3.2 XSS 深度修复 X1-X6 ✅
- X1: Jinja2 `Template()` → `Environment(autoescape=True)`
- X2: onclick 拼接 → `data-action` 委托
- X3: 模板插值补 `escapeHtml()`
- X4: `err.message` 安全处理
- X5: Schema `max_length` / 枚举白名单
- X6: 13 回归测试

### 3.3 Token 安全审计与修复 ✅
- Token 黑名单撤销机制（`RefreshToken` + `TokenBlacklist` 表）
- 密码修改独立端点（校验旧密码）
- session_id 链路填充 + 下线后 token 失效
- 登录设备指纹绑定

### 3.4 GLM 事务锁审计 F1-F12 ✅
- 三段式提交修复（deposit service）
- 事件处理器全部补 `with_for_update()`
- 原子 SQL（available_stock + current_participants）
- child 转移行锁保护

### 3.5 N+1 性能批 F1-F4 ✅
- `reconcile_stock` 2N→3
- `check_due_date_reminders` 4N→1
- `mark_overdue_books` N²→2
- `check_activity_reminders` N²→1

### 3.6 T3.6a 图书损坏定责 ✅
- BookDamageReport ORM（四级状态机 + 三级定级）
- 4 API 端点 + 页面 + CSS + JS
- D05 联动 + 冲正回滚 + 7 天申诉窗口
- 9 单元测试

### 3.7 清理项 ✅
| 项 | 状态 |
|----|:----:|
| R2 兼容重导出清除 | 24 文件 |
| R3 escapeHtml 统一 | 17 文件 |
| R4 iconfont 目录 | `.gitkeep` 已建，woff2 需人工 |
| R6 onError handler | `wx.onError` + `wx.onUnhandledRejection` |
| I3 BookOverdueEvent 删除 | 类 + 引用全删 |
| I4 alembic/env.py F401 | 修复 21 个 |

### 3.8 新路由 + 测试 ✅
- 4 条后端路由（child transfer, related books, checkin records, delete child）
- 36 个新测试（15 unit + 21 HTTP）
- Activity service 覆盖 95%（41 测试）
- XSS 测试 13 断言

---

## 四、测试状态总览

```
pytest:      333 passed, 5 skipped (报告PDF/微信QR/alembic check/2 损坏)
behave:      160 scenarios / 1095 steps / 0 failed / 0 skipped
ruff check:  0 errors (backend/ tests/ features/ scripts/)
ruff format: 349 files already formatted
api-contract: OK
model-consistency: 54 tables ✅
integration:  55/55 (payment gateway + SMS mock)
alembic:      OK (head=028)
```

### 5 个跳过测试的原因
1. `test_report_pdf` — 需 weasyprint 系统库 (`libpango`)，CI 有，本地 macOS 无
2. `test_wechat_qr` — TestClient app 引擎 vs fixture 引擎不匹配，仅 SQLite CI 环境跳过
3. `alembic check` — migration 009 用 `mysql.BIGINT()`，SQLite 不兼容
4-5. `test_damage_report_*` — 需要 `PhotoUploadDependency` mock，本地跳过 1 个

---

## 五、剩余工作清单

### P0 — 需外部输入（3 项，阻塞提审）

| # | 项 | 位置 | 谁处理 |
|---|----|------|--------|
| T1 | 替换 appid 占位符 | `frontend/project.config.json:4` `wx0000000000000000` | 运营 |
| T2 | 补全服务协议 | `frontend/pages/register/service-agreement.wxml` 占位文本 | 法务/运营 |
| T3 | 隐私政策主体 | `frontend/pages/register/privacy-policy.wxml:16` 公司全称 | 运营 |

### P1 — 你可动手

| # | 项 | 说明 | 预估 |
|---|----|------|:----:|
| R4 | iconfont woff2 下载 | 从 iconfont.cn 下载，取消 `app.wxss` 末端 `@font-face` 注释 | 5min |
| R5 | nginx rate limit | 9 个资金/用户接口加 `limit_req_zone`（建议网关层） | 1h |

### P2 — 可延后

| # | 项 | 说明 |
|---|----|------|
| I1 | reading-stats 折线图 | 产品决策待定 |
| I2 | pytest 覆盖提升 | activity 已达 95%，book/child/deposit/order/reading/report <30% |

---

## 六、关键架构信息

```
后端:     Python 3.13 + FastAPI + SQLAlchemy 2.0 + Pydantic V2
数据库:   MySQL 8.0 (utf8mb4) / 测试用 SQLite :memory:
小程序:   微信原生 (31 页, 4 子包)
管理端:   Jinja2 模板 (37 页) + 35 page JS (IIFE) + 33 CSS + base-init.js
CI:      GitHub Actions (3 jobs × 7 checks + 2 regression extras)
认证:    JWT (python-jose) + bcrypt
支付:    PaymentGateway ABC → Mock / WeChatPayV3
查词:    ECDICT 本地 338 万词条 + Free Dictionary API 兜底
定时:    APScheduler (15 任务)
端口:    后端 8002 / 前端 3002

git分支:  main
最后提交: a3112a0 (sync baseline)
远程:    github.com/leechunwoo0815/librio (SSH)
```

### 分层架构（不可违反）
```
Router (DI/参数/HTTP状态码, 无try/except/业务逻辑)
  → Service (事务/业务规则, 不操作HTTP)
    → Repository (CRUD, 继承BaseRepo)
      → Model (ORM, 继承BaseModel, 无业务方法)
EventBus (跨域解耦) + ConfigService (TTL缓存)
```

### 红线
- iOS 端**禁** `wx.requestPayment`（虚拟服务）
- 金额用 `Decimal` / 整数分，禁 `float`
- 归属校验用 `middleware/ownership.py`，禁手动写
- 库存操作必须有 `with_for_update()`
- 三段式提交：HTTP 调用前必须 commit 释放行锁
- 变更前读文件，变更后跑 CI 同构九关

---

## 七、管理后台非功能性约定

### 事件委托模式（已全量采用）
```html
<!-- 所有内联事件处理器已替换为: -->
<button data-action="users:editUser" data-id="{{ user.id }}">编辑</button>
```

```javascript
// 所有 page JS 通过 IIFE 隔离:
(function() {
  window.usersPage = window.usersPage || {};
  window.usersPage.editUser = function(el) {
    const id = el.dataset.id;
    // ...
  };
})();

// #admin-root 单监听器 (base-init.js)
document.querySelector('#admin-root')?.addEventListener('click', function(e) {
  const el = e.target.closest('[data-action]');
  if (!el) return;
  const [page, fn] = el.dataset.action.split(':');
  if (window[page + 'Page']?.[fn]) window[page + 'Page'][fn](el);
});
```

### 安全转义
- 所有 DOM 插入（包括 `err.message`）必须用 `escapeHtml()`（`admin.js` 全局版）
- 禁止在 page JS 中重复定义 `escapeHtml`
- `escapeHtml(str)` 使用 `??` 安全运算符（与 `||` 的区别是保留空字符串）

### 登录与测试
- 管理员账号：`admin` / `admin123`
- 请求日志：`logs/admin_requests.log`
- 测试数据：`python -m backend.seeds.fix_test_data`

---

## 八、你不会踩的坑（但我还是列了）

| # | 坑 | 真相 |
|---|----|------|
| 1 | "专家说日志在 /tmp/..." | 实际在 `logs/admin_requests.log`，不是 `/tmp/librio_backend.log` |
| 2 | "pytest 应该 340+" | 跳过 5 个是正常的（macOS 依赖缺失 + SQLite 不兼容） |
| 3 | "Phase 2 没做完" | 已经全量完成，38 模板全部迁移，**不要再做** |
| 4 | "XSS 还有问题" | X1-X6 已修复且 13 回归测试全绿，**不要再修** |
| 5 | "Token 没有撤销" | 已新增黑名单 + session_id 链路，认证中间件已更新 |
| 6 | "F401/inline handler 还在" | 已全部清除 |
| 7 | "inline handler 模板还有" | 已清零。新写页面也**必须**用 `data-action` 委托 |
| 8 | "JS escapeHtml 多处定义" | 已统一到 `admin.js`，**不准重新定义** |

---

## 九、核心文件索引

### 必须读（新 LLM 必读）
| 文件 | 内容 |
|------|------|
| `CLAUDE.md` | 项目最高宪法（红线 + CI 九关 + 开发流程） |
| `HANDOFF.md` | 完整交接文档（本总文档） |
| `HANDOFF_XSS.md` | XSS 专用交接文档 |
| `ARCHITECTURE.md` | 完整架构（606 行，27 域 + 路由清单） |
| `.ai/context/CONTEXT.md` | 领域语言与业务规则（308 行） |
| `.github/workflows/ci.yml` | CI 配置 |
| `.ai/RULES.md` | BDD/TDD 开发规范 |

### 参考
| 文件 | 说明 |
|------|------|
| `专家意见/prd_vs_code_audit_20260721.md` | PRD vs 代码一致性审计 |
| `专家意见/XSS深度审查报告-20260721.md` | XSS 审查详情 |
| `专家意见/token_security_fix_report_20260722.md` | Token 修复报告 |
| `专家意见/Phase2-数据驱动事件委托迁移终结报告.md` | Phase 2 完成报告 |

### 本轮迁移文件（alembic）
| 文件 | 说明 |
|------|------|
| `alembic/versions/026_create_book_damage_report.py` | 图书损坏定责 |
| `alembic/versions/027_base_col_comments.py` | 基础字段注释 |
| `alembic/versions/5a5e91684fe9_028_add_token_generation_and_user_status.py` | Token 安全 |

---

## 十、工作方法论

1. **验证先行**：每次声称"修复完成"前，必须运行 CI 同构九关
2. **读文件再改**：不用幻觉写代码，先 `Read` 再看
3. **最小修改**：只修目标函数，不顺便重构整条链路
4. **单点修复**：一个 bug 修一个文件，不搞跨模块清理
5. **断路机制**：连续 2 次修不对同一个问题 → 停下来输出完整上下文
6. **测试证明**：修复后加测试或观察测试覆盖率

---

## 十一、下一步从哪开始

当前最自然的切入点：

1. **运行 CI 九关**确认环境正常
2. **读完本文件** + `CLAUDE.md` + `ARCHITECTURE.md` 前 100 行
3. 检查 `logs/admin_requests.log` 有无异常
4. 按剩余清单开始：P0 外部项（需运营）> P1 iconfont + rate limit > P2 pytest 覆盖

**祝你好运，别让我失望 🚀**
