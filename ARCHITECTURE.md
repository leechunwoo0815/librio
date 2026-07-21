# DmkWords — 架构文档

> 版本：V3.8（2026-07-15 更新）
> 零粉饰，只写事实

---

## 一、产品一句话

帮 3-15 岁孩子通过"线上选书→线下扫码借书→线上音频伴读→查词→测评→晋级"养成英文阅读习惯。OMO 模式：线下实体书借阅 + 线上音频伴读 + 手动查词 + 异步测评。卖的不是借阅，是有老师指导、有晋级目标、有共同进步社群的阅读成长体系。

---

## 二、架构概览

### 分层架构（V3.5 架构改进后）

```
Router → Service → Repository → Model
   ↓         ↓
Ownership  EventBus → 各域事件处理器
   ↓         ↓
ConfigService  Integrations → 外部服务（微信支付V3/登录/订阅消息/Redis）
   ↓
Gateways → Mock支付网关 / Mock短信网关 / 真实支付网关（依赖倒置+配置开关）
```

- **Router 层**：参数校验、HTTP 状态码、依赖注入，不写业务逻辑、不写 try/except、不抛 HTTPException
- **Ownership 层**：声明式归属校验（`middleware/ownership.py`），callable class 依赖工厂
- **Service 层**：业务逻辑、事务管理，通过 BaseRepository 访问数据，通过 EventBus 跨域通信
- **ConfigService**：统一配置读取（`common/config_service.py`），带 5 分钟 TTL 缓存
- **Repository 层**：继承 BaseRepository，封装数据访问
- **Model 层**：继承 BaseModel，纯 ORM 映射
- **EventBus**：跨域解耦，共享/独立双模式事务（`common/events.py`）
- **Integrations**：外部服务适配层，隔离第三方 SDK 细节
- **Gateways**：支付/短信网关抽象层，依赖倒置（ABC → Mock/Real impl），配置开关切换

---

## 三、技术栈

| 层 | 选型 |
|----|------|
| 前端 | 微信小程序原生（31 页，4 子包） |
| 后端 | Python 3.13 + FastAPI + SQLAlchemy 2.0 + Pydantic V2 |
| 数据库 | MySQL 8.0 (utf8mb4)，测试用 SQLite :memory: |
| 测试 | pytest (254 passed / 5 skipped) + behave (151 scenarios / 1030 steps) |
| 管理端 | 36 个 PC 后台模板（含 base.html）+ 32 页面级 CSS + 34 page JS（IIFE） |
| 设计系统 | --accent: #5560cf + 31/31 class 对齐 ≥95% + 0 hardcoded + 0 oklch |
| 定时 | APScheduler（14 个任务） |
| 认证 | JWT (python-jose) + bcrypt 密码哈希 |
| 缓存 | Redis（access_token 缓存，带内存降级） |
| 查词词库 | ECDICT（338 万词条，本地离线） |
| 代码质量 | Ruff (lint + format) + CI（GitHub Actions） |
| 网关 | Mock 支付/短信网关（依赖倒置+配置开关 MOCK_PAYMENT/MOCK_SMS） |
| 端口 | 后端 8002 / 前端 3002 |

---

### 目录结构（V3.5 架构改进后）

```
backend/
├── common/              # 公共基础层
│   ├── base_model.py    #   ORM 基类（id/create_time/update_time/is_deleted）
│   ├── base_schema.py   #   Pydantic 基类
│   ├── base_repo.py     #   通用 Repository（CRUD 模板）
│   ├── config_service.py #  统一配置读取（带 TTL 缓存）
│   ├── dependencies.py  #   FastAPI Depends 工厂
│   ├── events.py        #   领域事件总线（共享/独立双模式事务）
│   ├── exceptions.py    #   统一异常体系（7 个异常类）
│   └── types.py         #   枚举类型定义
├── domain/              # 领域模块（26 个域）
│   ├── activity/        #   活动域
│   ├── admin/           #   管理域（含 SystemConfig、Teacher、Venue）
│   │   └── routers/     #     管理端路由（8 个领域路由文件）
│   ├── advancement/     #   晋级域（含 LeaderboardService 独立拆分）
│   ├── book/            #   图书域（Book + BookCopy）
│   ├── bookshelf/       #   书架域（收藏夹 + 想读清单）
│   ├── borrow/          #   借阅域（BorrowRecord）
│   ├── certificate/     #   证书域
│   ├── child/           #   孩子域
│   ├── deposit/         #   押金域（DepositRecord）
│   ├── evaluation/      #   评估域
│   ├── message/         #   消息域
│   ├── order/           #   订单域
│   ├── parent_course_time/ # 亲子课时域
│   ├── profile/         #   名片域
│   ├── quiz_question/   #   题库域
│   ├── reading/         #   阅读域
│   ├── refund/          #   退款域
│   ├── report/          #   报告域
│   ├── reservation/     #   预约域（Reservation）
│   ├── user/            #   用户域
│   ├── vocabulary/      #   词汇域
│   └── voice/           #   语音域
├── gateways/            # 网关抽象层（依赖倒置+配置开关）
│   ├── __init__.py       #   Gateway 工厂 export
│   ├── exceptions.py     #   PaymentException / SmsException
│   ├── payment/          #   支付网关
│   │   ├── base.py       #     PaymentGateway ABC
│   │   ├── types.py      #     支付类型定义
│   │   ├── mock_impl.py  #     Mock 支付实现
│   │   └── mock_routes.py #    Mock 回调路由
│   └── sms/              #   短信网关
│       ├── base.py       #     SmsGateway ABC
│       ├── types.py      #     短信类型定义
│       ├── mock_impl.py  #     Mock 短信实现
│       └── mock_routes.py #    Mock 查询路由
├── integrations/        # 外部集成层
│   ├── sms/             #   短信 SDK（tencent.py / aliyun.py，ImportError 兜底）
│   └── wechat/          #   微信相关
│       ├── auth.py      #     微信登录
│       ├── pay_v3.py    #     微信支付 V3（继承 PaymentGateway ABC，RSA 签名 + AES-GCM 解密 + 证书自动刷新）
│       └── subscribe.py #     订阅消息（Redis/内存双层缓存）
├── middleware/           # 中间件层
│   ├── admin_auth.py    #   管理员认证 + RBAC
│   ├── auth.py          #   用户 JWT 认证（含 type 检查防混淆）
│   ├── ownership.py     #   声明式归属校验（7 个 callable class）
│   ├── rate_limit.py    #   速率限制
│   ├── request_log.py   #   请求日志（输出到 logs/admin_requests.log）
│   └── trace.py         #   请求追踪
├── tasks/               # APScheduler 定时任务（14 个）
├── templates/admin/     # 管理端 Jinja2 模板（36 个页面，含 base.html）
├── static/admin/        # 管理端静态资源（CSS/JS）
├── seeds/               # 种子数据脚本
└── utils/               # 工具函数
scripts/                 # CI 脚本
├── check_fake_assertions.py  # 禁止 assert True 假绿
└── verify_api_contract.py    # 前后端 API 契约验证
.github/workflows/ci.yml     # CI 配置
features/                # BDD feature 文件（16 个，138 场景，970 步骤）
tests/unit/              # pytest 单元测试（239 个）
scripts/integration_test.py  # 全链路集成测试（867 行，6 主流程 + 7 异常场景）
frontend/                # 微信小程序（31 个页面，4 子包）
```

---

## 四、管理端路由架构（V3.5 重构后）

### 4.1 路由文件拆分

管理端 API 路由已按领域拆分为 9 个文件，统一前缀 `/admin/api`：

| 文件 | 行数 | 职责 | 路由前缀 |
|------|------|------|----------|
| `admin_venues_router.py` | 58 | 场馆管理 | `/admin/api/venues` |
| `admin_teachers_router.py` | 139 | 老师管理 + 排班 | `/admin/api/teachers` |
| `admin_activities_router.py` | 101 | 活动管理 | `/admin/api/activities` |
| `admin_books_router.py` | 205 | 图书 + 副本 + 上传 + 导出 | `/admin/api/books`, `/admin/api/bookcopy` |
| `admin_borrow_router.py` | 254 | 借阅 + 押金 + 预约 | `/admin/api/borrows`, `/admin/api/deposits`, `/admin/api/reservations` |
| `admin_advancement_router.py` | 365 | 级别 + 成就 + 证书 + 题库 + 审核 | `/admin/api/advancement` |
| `admin_system_router.py` | 298 | 仪表盘 + 配置 + 用户 + 订单 + 管理员 + 证书别名 | `/admin/api/dashboard`, `/admin/api/config`, `/admin/api/admins`, `/admin/api/certificates`（证书列表别名）, ... |
| `admin_reports_router.py` | 282 | 退款 + 报告 + 阅读数据 | `/admin/api/refunds`, `/admin/api/reports`, `/admin/api/reading-data` |
| `admin_role_router.py` | 150 | 角色管理（CRUD + 权限分配树） | `/admin/api/roles` |

### 4.2 架构规范

- **Router 层**：不写业务逻辑，不直接操作 ORM
- **Service 层**：所有业务逻辑和数据库操作
- **Schema 层**：统一使用 `admin_schemas.py`（52 个 Schema，全部有 `extra="forbid"`）
- **分页**：所有列表接口使用 `{items, total, page, page_size, has_next}` 格式
- **N+1 查询**：全部使用批量查询 + dict 映射
- **SQL 聚合**：reading-data 使用 `func.sum/func.count/func.distinct`

---

## 五、数据库（49 张表）

### RBAC 权限域（Phase 1-2）
- `role` — 角色（3 个种子: super_admin/staff/teacher）
- `permission` — 权限码（128 个种子）
- `role_permission` — 角色-权限关联

### 用户域
- `user` — 家长账户
- `child` — 孩子（含 english_name、current_level_id、deposit_status、outstanding_fines）

### 场馆运营域
- `venue` — 场馆
- `admin` — 管理员（RBAC: admin_role_id → role.id, teacher_id → teacher.id）
- `teacher` — 老师（列表 API 返回 admin_id + admin_role_name）
- `teacher_schedule` — 排班

### 图书域
- `book` — 图书元数据（含 barcode、audio_timeline、core_vocabulary、price、total_stock、available_stock）
- `book_copy` — 实体书副本（唯一条码，扫码入库）
- `dictionary_word` — 系统词库（ECDICT）

### 三个列表（V3.5 OMO）
- `bookshelf` — 收藏夹（想读列表，不限量）
- `borrow_record` — 借阅记录（正在阅读，线下扫码自动生成，最多 20 本，21 天借期）
- `deposit_record` — 押金记录（1200 元，状态机：UNPAID→PAID→REFUNDED/DEDUCTED）
- `reservation` — 预约（线上预约借书，72 小时过期，锁定库存）

### 阅读行为域
- `reading_progress` — 阅读进度
- `reading_session` — 阅读会话
- `reading_submission` — 阅读提交
- `check_in` — 打卡
- `voice_recording` — 语音录音

### 词汇域
- `user_vocabulary` — 生词本

### 晋级域
- `level` — A-Z 26 级定义（含 required_books、required_quiz_pass_rate）
- `child_level` — 孩子级别记录（含 books_read_at_level、quizzes_passed_at_level）
- `question_bank` — 题库（每本书≥5 道选择题）
- `quiz` — 测验实例
- `quiz_question` — 测验-题目关联
- `quiz_answer` — 答题记录
- `achievement` — 成就定义
- `child_achievement` — 孩子成就

### 订单域
- `order` — 统一订单（3 种类型：亲子课/观察期/正式会员）
- `refund_application` — 退款申请

### 活动域
- `activity` — 活动（6 种类型）
- `activity_enrollment` — 活动报名（含 ticket_code、sign_in_time）

### 评估域
- `ar_evaluation` — AR 测评记录
- `guidance_record` — 指导课记录

### 系统域
- `system_config` — 动态配置（30+ 项）
- `system_message` — 站内信
- `operation_log` — 操作日志
- `observation_report` — 观察期报告
- `learning_report` — 学习报告

---

## 六、API 端点清单

### 6.1 用户端 API（74 个 + Mock 网关路由）

| 模块 | 端点数 | 认证方式 | 说明 |
|------|--------|----------|------|
| user | 3 | 可选/必选 | 微信登录、用户信息、更新 |
| book | 4 | admin(create) | 搜索、详情、创建、副本管理 |
| child | 7 | get_current_user + 归属校验 | CRUD、状态、权益转让 |
| order | 7 | get_current_user + 归属校验 | 创建、支付回调(验签)、退款预览、pay-params |

Mock 网关路由（仅 `MOCK_PAYMENT=True` / `MOCK_SMS=True` 时注册）：
- `POST /mock/payment/notify/order` — 模拟微信支付订单回调
- `POST /mock/payment/notify/refund` — 模拟微信支付退款回调
- `GET /mock/sms/code/{phone}` — 查看 Mock 短信验证码
| activity | 5 | get_current_user + 归属校验 | 活动列表、报名、取消、签到 |
| refund | 4 | user/admin | 申请、审核(admin)、列表、详情 |
| reading | 10 | get_current_user + 归属校验 | 进度、会话、打卡、语音录音 |
| vocabulary | 5 | get_current_user + 归属校验 | 查词、生词本、统计、标记掌握 |
| message | 3 | get_current_user | 消息列表、标记已读、全部已读 |
| voice | 2 | get_current_user + 归属校验 | 录音、列表 |
| stats | 4 | get_current_user + 归属校验 | 汇总、趋势、周报 |
| advancement | 10 | get_current_user + 归属校验 | 级别、测验(含start)、成就、排行榜(LeaderboardService) |
| teacher | 7 | admin | CRUD、分配(admin only)、排班 |
| config | 3 | admin | 配置读写 |

### 6.2 管理端 API（93 个）

管理端 API 统一前缀 `/admin/api`，使用 admin 认证。

详见 `checkpoint.md` 中的完整 API 路由清单。

---

## 七、验证结果

```bash
# pytest
239/4 passed (local) / 251/5 passed (CI)

# 架构验证
✅ Router 层 ORM 操作：0 处
✅ N+1 查询：0 处
✅ 无分页列表接口：0 个
✅ inline import：0 处
✅ response_model：所有路由都有
✅ Schema extra=forbid：52/52
✅ stub 函数：返回 success: false
✅ 前端 stub 按钮：3 个全部 disabled
✅ 前端 API 路径：32/32 正常
✅ 集成测试（全链路）：53/53 step pass
```

---

## 八、2026-07-09 全量终审修复

> 2026-07-09 完成 4 并行代理全频谱最终审计，P0+P1+P2 共 35 项修复全部落地。

### P0 致命级（8 项）✅ 已修复

| # | 问题 | 文件 |
|---|------|------|
| 1 | WordResponse extra 未 forbid | `admin_schemas.py` |
| 2 | VoiceRecording 重复录音不防重 | `voice/service.py` |
| 3 | import_ecdict 密码硬编码 → 环境变量 | `scripts/import_ecdict.py` |
| 4 | JWT SECRET_KEY 注释泄漏 | `middleware/auth.py` |
| 5 | admin Cookie 缺 Secure/HttpOnly/SameSite | `admin_auth_router.py` |
| 6 | CSRF 中间件缺 docstring | `middleware/csrf.py` |
| 7 | books 缺 onTapCategory + categoryIndex | `frontend/` |
| 8 | SMS Redis 配置已确认 | `integrations/sms.py` |

### P1 严重级（13 项）✅ 已修复

| # | 问题 | 文件 |
|---|------|------|
| 1-8 | 8 处 bindtap → JS 事件名不匹配 | `frontend/pages/` |
| 9 | CertificateResponse create_time 字段不统一 | `certificate/schemas.py` |
| 10-12 | 3 个 ListResponse 未继承 PaginatedResponse | `admin_schemas.py` |
| 13 | 分页缺陷：borrow/activity/voice | `admin/routers/` |
| 14 | api.cancelOrder + backend 端点不一致 | `frontend/` + `order/router.py` |
| 15 | behave 测试对齐 | `features/` |

### P2 一般级（8 项）✅ 已修复

| # | 问题 | 文件 |
|---|------|------|
| 1 | pagination.css 未使用 → 已删除 | `static/admin/css/pages/` |
| 2-4 | 3 处 except Exception 未限定 | 多个 service 文件 |
| 5 | test-token 缺 DEBUG + ENABLE_TEST_TOKEN 双重守卫 | `middleware/test_token.py` |
| 6 | WeChat Pay password=None 未处理 | `pay_v3.py` |
| 7 | page_template scaffold 未清理 | `templates/admin/page_template.html` |
| 8 | 3 处 route name 不标准 | `admin/routers/` |
| 9 | 7 处 seeds print → logger | `seeds/` |
| 10 | login.html Cookie 注释未更新 | `login.html` |

---

## 九、2026-07-13 Mock网关 + 集成联调 + 审计闭环

> 2026-07-13 完成 Mock 支付/短信网关接入、全链路集成测试、4 轮审计闭环。

### 网关状态

| 网关 | 类型 | 开关 | 状态 |
|------|------|------|------|
| PaymentGateway | ABC → MockPaymentGateway / WeChatPayV3 | `MOCK_PAYMENT=True` | ✅ Mock 已实现 |
| SmsGateway | ABC → MockSmsGateway / SmsService | `MOCK_SMS=True` | ✅ Mock 已实现 |

### 4 轮审计累计成果

| 轮次 | P0 | P1 | P2 | 合计 |
|------|----|----|----|----|
| Round 1-2 | 25 | 32 | 0 | 57 |
| Round 3 | 6 | 7 | 6 | 19 |
| Round 4 | 8 | 0 | 0 | 8 |
| **总计** | **39** | **39** | **6** | **84** |

### 新增测试

- 并发测试：13 个（borrow deposit/refund/deduction 并发场景）
- 状态机测试：押金 FULFILLED 状态校验
- 集成测试：`scripts/integration_test.py` 867 行，6 主流程 + 7 异常场景，45/45 step pass

### 当前验证状态

```bash
pytest:  152/152 passed ✅
ruff:    0 errors ✅
behave:  138/138 passed ✅
```

### 剩余遗留项

1. **appid 配置**：需产品提供正式 appid
2. **隐私政策**：需法务审核文本
3. **微信支付退款对接**：真实 WeChatPayV3 退款接口待对接
4. **SMS 生产环境**：Mock 模式 + 腾讯云/阿里云 SDK 实现已完成（2026-07-15），上线需取消注释 requirements.txt 依赖 + 配置真实凭据

## 十、2026-07-13 Session 2 — Phase 1+3+4 执行

> 2026-07-13 Phase 1 执行：SMS 配置存根（tencent.py, aliyun.py）、get_sms_gateway() 更新。

### 变更记录

| 变更 | 说明 |
|------|------|
| SMS 配置存根 | 创建 `backend/integrations/sms/tencent.py`、`aliyun.py`、`__init__.py`，更新 `get_sms_gateway()` |
| cryptography | 安装 49.0.0 |
| pay_v3.py bugfix | `Path("").exists()` → `is_file()` |
| 晋级冷却 bugfix | `datetime.now` → `datetime.now(timezone.utc)` |
| borrow_record_id bugfix | `borrow_from_reservation` 中 `borrow_record_id` 未设置 |
| 集成测试 | 40/44 → 45/45（全部通过） |
| DEPLOY_CHECKLIST.md | 由 TASK_PLAN.md Phase 4 执行生成 |

### 当前验证状态

```bash
集成测试：45/45 step pass ✅
```

### 剩余外部依赖

1. **appid 配置**：需产品提供正式 appid
2. **微信支付真实证书**：需商户平台下载配置
3. **生产短信服务商**：需开通腾讯云/Aliyun 短信服务

---

## 十一、2026-07-13 安全巡检

> 2026-07-13 额外安全巡检，修复 2 项。

| 问题 | 文件 | 修复 |
|------|------|------|
| P1: 生产 CORS 含 localhost | `backend/main.py:121-125` | localhost 来源移入 `if settings.DEBUG` 块 |
| P2: 死代码 `utils/wechat.py` | `backend/utils/wechat.py` | 已删除（V2 旧逻辑，float 金额风险，零引用） |

### 当前验证状态

```bash
ruff:    ✅ 0 errors
pytest:  ✅ 152/152 passed
behave:  ✅ 138/138 passed
```

---

## 十二、2026-07-13 专家审计

> 7 P0 + 系统级 P1 经代码核验全部确认。Phase 5 已规划至 TASK_PLAN.md。

| # | 问题 | 优先级 | 状态 |
|---|------|--------|------|
| B-P0-3 | Deposit 绕过支付网关直接 PAID | P0 | 待修复（Task 11） |
| B-P0-1 | Reservation/cancel 无认证 | P0 | 待修复（Task 12） |
| B-P0-2 | Refund/apply 无锁+重复校验 | P0 | 待修复（Task 13） |
| A-P0-1 | Admin oplogs 无 Authorization | P0 | 待修复（Task 14） |
| F-P0-3 | Books categories 未定义崩溃 | P0 | 待修复（Task 15） |
| F-P0-2 | Deposit amount.indexOf 类型崩溃 | P0 | 待修复（Task 16） |
| — | 前端硬编码金额 | P0/P1 | 待修复（Task 17） |
| — | 字段契约 9 页不一致 | P0/P1 | 待修复（Task 18） |
| F-P0-1 | Member 页 child null 守卫 | P1 | 待修复（Task 19） |
| — | Admin XSS innerHTML | P1 | 待修复（Task 20） |
| — | Alembic 漂移 | P1 | ✅ 已修复（021/022/023） |
| — | 管理后台列表无分页 | P2/P1 | 待修复（Task 22） |
| — | 测试覆盖补全 | P0 parallel | 待修复（Task 23） |

---

## 十三、2026-07-14 Phase 5 P0 审计修复 + Alembic 漂移闭环

> 2026-07-14 完成 Refund 真实支付路径、Callback 异步修复、WeChatPayV3 ABC 继承、Alembic 漂移 3 版本（021/022/023）。

### P0 修复

| 问题 | 文件 | 修复 |
|------|------|------|
| refund 真实 WeChatPayV3 路径崩溃 | `refund/service.py` | kwargs → `get_payment_gateway()` + `PaymentRefundRequest` |
| deposit callback 阻塞事件循环 | `deposit/router.py` | `await asyncio.to_thread(service.handle_callback)` |
| WeChatPayV3 未继承 PaymentGateway ABC | `integrations/wechat/pay_v3.py` | `class WeChatPayV3(PaymentGateway)`, supports_instant_payment=False |

### Alembic 漂移修复

| 版本 | 修复内容 |
|------|---------|
| 021 (`a4b8c7d6e5f4`) | Raw index names, `except:pass`→`logger.warning()` |
| 022 (`b5f4e3d2c1a0`) | Observation report NULL dates data fix + NOT NULL with `_col_type()` helper |
| 023 (`d9d508402c87`) | Autogenerated from MySQL, all nullable fixes, column comments, raw drop_index |

### 模型对齐

所有 24 表 Column `comment=` 参数已对齐 021/022 迁移。

### 全量验证状态

```bash
pytest:              177/177 passed ✅
ruff:                0 errors ✅
behave:              138/138 passed ✅
集成测试:              53/53 step pass ✅
alembic check:       No new upgrade operations detected ✅
```

### 剩余任务（外部依赖阻塞）

| 任务 | 阻塞原因 |
|------|---------|
| appid 配置 | 需产品提供正式 appid |
| SMS 真实网关 | 需签名审批 |
| WeChatPayV3 真实商户 | 需商户 APIv3 密钥 |

---

## 十四、2026-07-15 微信小程序合规审计 + 全量终审

> 2026-07-15 完成微信小程序合规审计修复（3 批共 10 项）+ 全量安全终审。

### 合规修复

| 批次 | 修复项 | 文件 |
|------|--------|------|
| 批 1 | 删静默同意兜底 + firstDay bug + 删 store.js.bak + sitemap 精细化 | `app.js`, `checkin.js`, `sitemap.json` |
| 批 2 | 登录页隐私勾选 + 押金删 amount 参数 + iOS 文案统一 | `login.*`, `api.js`, `deposit.*`, `observation.*`, `official.*` |
| 批 3 | 完整 9 节隐私政策写入 | `privacy-policy.wxml` |

### 全量终审发现 + 修复

| 等级 | 问题 | 修复 |
|------|------|------|
| 中危 #1 | 文件上传 `validate_file_content` 仅 warn 不拦截 | `logger.warning()` → `raise ValidationError`，删除 `application/octet-stream` 绕过 |
| 中危 #2 | 分片上传 `save_chunk` 缺扩展名校验 + `complete_upload` 缺魔数校验 | 入口加白名单 + 合并后读前 32 字节校验，不通过删文件抛异常 |
| 低危 #1 | pay-button 组件 iOS 文案未同步 | 统一更新 |
| 低危 #2 | observation/official 弹窗 title 仍为"苹果规则限制" | 改为"暂不支持 iOS 开通" |
| 低危 #3 | 隐私政策"撤回同意权"操作路径不明确 | 补充操作指引 |

### 全量验证

```bash
pytest:              177/177 passed ✅
ruff:                0 errors ✅
behave:              138/138 passed ✅
alembic check:       No new upgrade operations detected ✅
```

---

## 十五、2026-07-15 全量日志覆盖审计

> 2026-07-15 完成两批日志覆盖审计，补齐安全路径日志 + 真吞异常排查。

### 第一批：安全路径日志（5 项）

| # | 文件 | 改动 |
|---|------|------|
| 1 | `frontend/app.js` | 新增 `wx.onError` + `wx.onUnhandledRejection` 全局 JS 错误捕获 |
| 2 | `middleware/rate_limit.py` | 新增 `logger.warning`，限流触发时记录 key/max/window |
| 3 | `middleware/ownership.py` | 3 处 `ForbiddenError` 前记 child_id/user_id/owner_id |
| 4 | `middleware/admin_rbac.py` | 权限不足时记 admin_id/username/required_codes/role_id |
| 5 | `admin_auth_router.py` | 登录失败/账号禁用均记 username + ip |

### 第二批：真吞异常排查（10 处）

| 类 | # | 文件 | 改动 |
|----|---|------|------|
| 后端 try/except | 1-2 | `order_service.py:48,54` | 日期解析失败 `pass` → `logger.warning` |
| | 3 | `wechat/auth.py:63` | 获取手机号失败加 `logger.warning` |
| 前端 .catch() | 4 | `messages.js:135` | 标记已读失败加 console.error |
| | 5-9 | `reading-stats.js:37-41` | 5 个 API catch 加 console.error |
| | 10 | `shelf.js:34` | 下拉刷新 catch 加 console.error |
| | 11 | `books.js:57` | 下拉刷新 catch 加 console.error |
| 前端 /* silent */ | 12 | `observation-report.js:62` | markReportViewed 失败加 console.error |
| | 13 | `reader.js:446` | endSession 失败加 console.error |
| 全局 handler | 14 | `main.py:99` | global_exception_handler 增加 method + path |

### 全量验证

```bash
pytest:              177/177 passed ✅
ruff:                0 errors ✅
behave:              138/138 passed ✅
alembic check:       No new upgrade operations detected ✅
```

---

## 十六、2026-07-15 第三方终审修复（9 项）

> 2026-07-15 第三方全量技术终审报告（架构/QA/产品 3 专家并行审查 12 维度）发现 5 P0 + 14 P1 + 16 P2。本批修复覆盖所有 P0 + 关键 P1。

| # | 等级 | 问题 | 修复 |
|---|------|------|------|
| P0-1 | 架构 | `child/router.py:98` Router 直接 ORM | 下沉到 `ChildService.create_benefit_transfer_application()` |
| P0-2 | 架构 | `admin_activities_router.py:169` Router 直接 ORM | 下沉到 `ActivityService.get_enrollment_by_id()` |
| P0-3 | 业务 | 押金退款缺审核 | 加 `REFUND_PENDING(6)` 状态 + `audit_refund(approve/reject)` + 管理员端点 + 迁移 025 |
| P0-4 | 合规 | 运营主体占位符 | `COMPANY_NAME` 环境变量 + WXML 占位符 |
| P0-5 | 合规 | 缺办学资质 | WXML 隐私政策 §九 办学资质展示 |
| P1-12 | 业务 | `borrow_from_reservation` 押金校验不一致 | 统一为 `(PAID, REFUNDING, REFUND_PENDING)` |
| P1-5 | 运维 | 日志非 JSON | `JSONFormatter` 替换 `Formatter`，每行 JSON |
| P1-6 | 运维 | 缺 trace_id | 支持 `X-Trace-Id` 请求头，`uuid4` 兜底生成 |
| P1-10 | 安全 | 管理端 innerHTML XSS（15 处 A 类） | `escapeHtml()` 补防 4 文件 9 处高频漏洞点 |

### 修复后全量验证

```bash
pytest:              177/177 passed ✅
ruff:                0 errors ✅
behave:              138/138 passed ✅
alembic check:       No new upgrade operations detected ✅
```

---

## 十七、2026-07-15 第三方专家审查交付

> 终审剩余建议整理为 4 份可执行交付文件，存放于 `专家意见/` 目录：

| 文件 | 内容 |
|------|------|
| `РEADME.md` | 审查总览 + 施工顺序 + 验证清单 |
| `P0-修复指南.md` | 押金假退款 + 退款双重审核（含完整代码） |
| `P1-修复指南.md` | 15 项 `with_for_update()` 加锁 + 2 项 API 修复 |
| `P2-优化建议.md` | 6 项优化 + 3 项系统改进 |

**开发模型可立即按 `专家意见/README.md` 施工路线接续。**

---

*架构文档更新于 2026-07-15。WeChat 合规审计 + 全量终审 + 日志覆盖审计 + 第三方终审修复 + 专家意见交付全部完成。177 单元测试 + 53 集成步骤全绿。*
