# MegaWords — 架构文档

> 版本：V3.6（2026-07-05 更新）
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
```

- **Router 层**：参数校验、HTTP 状态码、依赖注入，不写业务逻辑、不写 try/except、不抛 HTTPException
- **Ownership 层**：声明式归属校验（`middleware/ownership.py`），callable class 依赖工厂
- **Service 层**：业务逻辑、事务管理，通过 BaseRepository 访问数据，通过 EventBus 跨域通信
- **ConfigService**：统一配置读取（`common/config_service.py`），带 5 分钟 TTL 缓存
- **Repository 层**：继承 BaseRepository，封装数据访问
- **Model 层**：继承 BaseModel，纯 ORM 映射
- **EventBus**：跨域解耦，共享/独立双模式事务（`common/events.py`）
- **Integrations**：外部服务适配层，隔离第三方 SDK 细节

---

## 三、技术栈

| 层 | 选型 |
|----|------|
| 前端 | 微信小程序原生（27 页，4 子包） |
| 后端 | Python 3.13 + FastAPI + SQLAlchemy 2.0 + Pydantic V2 |
| 数据库 | MySQL 8.0 (utf8mb4)，测试用 SQLite :memory: |
| 测试 | pytest (100 单元) |
| 管理端 | 33 个 PC 后台页面（含 base.html）+ 31 页面级 CSS |
| 设计系统 | --accent: #5560cf + 31/31 class 对齐 ≥95% + 0 hardcoded + 0 oklch |
| 定时 | APScheduler（11 个任务） |
| 认证 | JWT (python-jose) + bcrypt 密码哈希 |
| 缓存 | Redis（access_token 缓存，带内存降级） |
| 查词词库 | ECDICT（338 万词条，本地离线） |
| 代码质量 | Ruff (lint + format) + CI（GitHub Actions） |
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
├── domain/              # 领域模块（23 个域）
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
├── integrations/        # 外部集成层
│   └── wechat/          #   微信相关
│       ├── auth.py      #     微信登录
│       ├── pay_v3.py    #     微信支付 V3（RSA 签名 + AES-GCM 解密 + 证书自动刷新）
│       └── subscribe.py #     订阅消息（Redis/内存双层缓存）
├── middleware/           # 中间件层
│   ├── admin_auth.py    #   管理员认证 + RBAC
│   ├── auth.py          #   用户 JWT 认证（含 type 检查防混淆）
│   ├── ownership.py     #   声明式归属校验（7 个 callable class）
│   └── trace.py         #   请求追踪
├── tasks/               # APScheduler 定时任务（11 个）
├── templates/admin/     # 管理端 Jinja2 模板（33 个页面，含 base.html）
├── static/admin/        # 管理端静态资源（CSS/JS）
├── seeds/               # 种子数据脚本
└── utils/               # 工具函数
scripts/                 # CI 脚本
├── check_fake_assertions.py  # 禁止 assert True 假绿
└── verify_api_contract.py    # 前后端 API 契约验证
.github/workflows/ci.yml     # CI 配置
features/                # BDD feature 文件（16 个，136 场景，954 步骤）
tests/unit/              # pytest 单元测试（100 个）
frontend/                # 微信小程序（27 个页面，4 子包）
```

---

## 四、管理端路由架构（V3.5 重构后）

### 4.1 路由文件拆分

管理端 API 路由已按领域拆分为 8 个文件，统一前缀 `/admin/api`：

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

### 4.2 架构规范

- **Router 层**：不写业务逻辑，不直接操作 ORM
- **Service 层**：所有业务逻辑和数据库操作
- **Schema 层**：统一使用 `admin_schemas.py`（52 个 Schema，全部有 `extra="forbid"`）
- **分页**：所有列表接口使用 `{items, total, page, page_size, has_next}` 格式
- **N+1 查询**：全部使用批量查询 + dict 映射
- **SQL 聚合**：reading-data 使用 `func.sum/func.count/func.distinct`

---

## 五、数据库（45 张表）

### 用户域
- `user` — 家长账户
- `child` — 孩子（含 english_name、current_level_id、deposit_status、outstanding_fines）

### 场馆运营域
- `venue` — 场馆
- `admin` — 管理员（RBAC: ADMIN/STAFF/TEACHER）
- `teacher` — 老师
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

### 6.1 用户端 API（74 个）

| 模块 | 端点数 | 认证方式 | 说明 |
|------|--------|----------|------|
| user | 3 | 可选/必选 | 微信登录、用户信息、更新 |
| book | 4 | admin(create) | 搜索、详情、创建、副本管理 |
| child | 7 | get_current_user + 归属校验 | CRUD、状态、权益转让 |
| order | 7 | get_current_user + 归属校验 | 创建、支付回调(验签)、退款预览、pay-params |
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
100 passed, 5 warnings in 1.60s

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
```

---

*架构文档更新完成。所有 P0 + P1 + P2 问题已修复。*
