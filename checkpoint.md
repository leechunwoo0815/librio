# MegaWords (librio) 项目检查点

> 更新时间：2026-07-05 23:00 GMT+8
> 状态：✅ 所有架构问题已修复，代码质量达标

---

## 一、项目概况

MegaWords 是一个儿童英语阅读管理平台，包含：
- **微信小程序**：家长端，用于孩子阅读打卡、借书、测验等
- **PC 管理后台**：管理员端，用于管理图书、老师、场馆、活动等
- **后端 API**：FastAPI + SQLAlchemy + MySQL

---

## 二、当前状态

### 2.1 验证结果

| 检查项 | 状态 |
|--------|------|
| pytest | ✅ 100 passed |
| behave | ✅ 138 passed |
| ruff check | ✅ 0 errors |
| Router 层 ORM 操作 | ✅ 0 处（原 43 处） |
| N+1 查询 | ✅ 0 处 |
| 无分页列表接口 | ✅ 0 个 |
| inline import | ✅ 0 处 |
| response_model | ✅ 所有路由都有 |
| Schema extra=forbid | ✅ 全部覆盖（BaseSchema 统一设置） |
| 前端上传路径 | ✅ 3/3 修复 |
| 前端 API 路径 | ✅ 32/32 正常 |
| 前端内联 JS 外迁 | ✅ 7/7 核心页面 |
| showConfirm HTML 渲染 | ✅ 已修复 |
| JS 语法检查 | ✅ 0 errors |

### 2.2 架构规范

**路由架构**（8 个文件）：
```
admin_venues_router.py      → /admin/api/venues
admin_teachers_router.py    → /admin/api/teachers
admin_books_router.py       → /admin/api/books, /admin/api/bookcopy, /admin/api/upload
admin_activities_router.py  → /admin/api/activities
admin_borrow_router.py      → /admin/api/borrows, /admin/api/deposits, /admin/api/reservations
admin_advancement_router.py → /admin/api/advancement
admin_reports_router.py     → /admin/api/refunds, /admin/api/reports, /admin/api/reading-data
admin_system_router.py      → /admin/api/dashboard, /admin/api/config, /admin/api/admins, ...
```

**Schema 架构**：
```
backend/common/base_schema.py → BaseSchema（extra="forbid"）+ PaginatedResponse + ApiResponse
backend/domain/admin/admin_schemas.py → 管理端 Schema（52 个）
backend/domain/*/schemas.py → 业务域 Schema（20 个，继承 BaseSchema）
```

**Service 层架构**：
```
backend/domain/admin/service.py → AdminService（管理端业务逻辑）
backend/domain/advancement/service.py → AdvancementService（晋级域业务逻辑）
backend/domain/*/service.py → 各业务域 Service
```

---

## 三、文件清单

### 3.1 核心文档

| 文件 | 用途 | 最后更新 |
|------|------|----------|
| `CLAUDE.md` | 项目配置 | 2026-07-05 |
| `ARCHITECTURE.md` | 架构文档 | 2026-07-05 |
| `TASK_PLAN.md` | 任务计划 | 2026-07-05 |
| `checkpoint.md` | 检查点 | 2026-07-05 |
| `HANDOFF.md` | 交接文档 | 2026-07-05 |

### 3.2 路由文件（8 个）

| 文件 | 行数 | 职责 |
|------|------|------|
| `admin_venues_router.py` | ~60 | 场馆管理 |
| `admin_teachers_router.py` | ~140 | 老师管理 + 排班 |
| `admin_activities_router.py` | ~100 | 活动管理 |
| `admin_books_router.py` | ~200 | 图书 + 副本 + 上传 + 导出 |
| `admin_borrow_router.py` | ~160 | 借阅 + 押金 + 预约 |
| `admin_advancement_router.py` | ~210 | 级别 + 成就 + 证书 + 题库 + 审核 |
| `admin_reports_router.py` | ~140 | 退款 + 报告 + 阅读数据 |
| `admin_system_router.py` | ~320 | 仪表盘 + 配置 + 用户 + 订单 + 管理员 |

### 3.3 Service 文件

| 文件 | 新增方法 |
|------|----------|
| `admin/service.py` | list_deposits, list_reservations, list_refunds, approve_refund, list_observation_reports, get_reading_stats, get_reading_trends, get_order, mark_message_read, list_admins, get_admin, create_refund, create_order, update_order_status, delete_order, delete_message |
| `advancement/service.py` | list_achievement_records, list_certificates, get_certificate, update_certificate, delete_certificate, list_submissions, list_questions |

---

## 四、API 路由清单

### 4.1 场馆管理
- `GET /admin/api/venues` - 获取场馆列表
- `POST /admin/api/venues` - 创建场馆
- `PUT /admin/api/venues/{id}` - 更新场馆
- `DELETE /admin/api/venues/{id}` - 删除场馆

### 4.2 老师管理
- `GET /admin/api/teachers` - 获取老师列表
- `GET /admin/api/teachers/{id}` - 获取老师详情
- `POST /admin/api/teachers` - 创建老师
- `PUT /admin/api/teachers/{id}` - 更新老师
- `DELETE /admin/api/teachers/{id}` - 删除老师
- `POST /admin/api/teachers/assign` - 分配老师
- `GET /admin/api/teachers/{id}/children` - 获取老师负责的孩子
- `GET /admin/api/teachers/child/{id}` - 获取孩子的老师
- `POST /admin/api/teachers/schedule` - 创建排班
- `GET /admin/api/teachers/{id}/schedule` - 获取老师排班
- `DELETE /admin/api/teachers/schedule/{id}` - 删除排班

### 4.3 图书管理
- `GET /admin/api/books` - 搜索图书
- `POST /admin/api/books` - 创建图书
- `PUT /admin/api/books/{id}` - 更新图书
- `DELETE /admin/api/books/{id}` - 删除图书
- `PUT /admin/api/books/{id}/toggle-publish` - 切换发布状态
- `POST /admin/api/books/bulk-import` - 批量导入
- `GET /admin/api/bookcopy` - 获取副本列表
- `POST /admin/api/bookcopy/batch-generate` - 批量生成副本
- `POST /admin/api/bookcopy/{id}/copies` - 创建副本
- `POST /admin/api/upload` - 上传文件
- `POST /admin/api/upload/chunk` - 分片上传
- `POST /admin/api/upload/complete` - 完成上传
- `GET /admin/api/upload/status/{id}` - 上传状态

### 4.4 借阅管理
- `GET /admin/api/borrows/{child_id}` - 获取孩子借阅列表
- `POST /admin/api/borrows` - 借书
- `POST /admin/api/borrows/return` - 还书
- `POST /admin/api/borrows/send-overdue-reminders` - 发送逾期提醒（stub）

### 4.5 押金管理
- `GET /admin/api/deposits` - 获取押金列表
- `POST /admin/api/deposits/refund` - 申请退款
- `POST /admin/api/deposits/pay` - 管理员代缴押金

### 4.6 预约管理
- `GET /admin/api/reservations` - 获取预约列表
- `POST /admin/api/reservations/fulfill` - 完成预约
- `PUT /admin/api/reservations/{id}/cancel` - 取消预约

### 4.7 活动管理
- `GET /admin/api/activities` - 获取活动列表
- `GET /admin/api/activities/{id}` - 获取活动详情
- `POST /admin/api/activities` - 创建活动
- `PUT /admin/api/activities/{id}` - 更新活动
- `DELETE /admin/api/activities/{id}` - 删除活动
- `GET /admin/api/activities/{id}/enrollments` - 获取报名列表
- `POST /admin/api/activities/{id}/checkin` - 批量签到

### 4.8 晋级管理
- `GET /admin/api/advancement/levels` - 获取级别列表
- `POST /admin/api/advancement/levels` - 创建级别
- `PUT /admin/api/advancement/levels/{id}` - 更新级别
- `DELETE /admin/api/advancement/levels/{id}` - 删除级别
- `GET /admin/api/advancement/achievements` - 获取成就列表
- `POST /admin/api/advancement/achievements` - 创建成就
- `PUT /admin/api/advancement/achievements/{id}` - 更新成就
- `DELETE /admin/api/advancement/achievements/{id}` - 删除成就
- `GET /admin/api/advancement/achievements/records` - 获取成就记录
- `GET /admin/api/advancement/certificates` - 获取证书列表（别名：`GET /admin/api/certificates`）
- `GET /admin/api/advancement/certificates/{id}` - 获取证书详情
- `PUT /admin/api/advancement/certificates/{id}` - 更新证书
- `DELETE /admin/api/advancement/certificates/{id}` - 删除证书
- `POST /admin/api/advancement/certificates/{id}/regenerate` - 重新生成证书
- `GET /admin/api/advancement/submissions` - 获取审核列表
- `PUT /admin/api/advancement/submissions/{id}/review` - 审核提交
- `GET /admin/api/advancement/questions` - 获取题目列表
- `POST /admin/api/advancement/questions` - 创建题目
- `PUT /admin/api/advancement/questions/{id}` - 更新题目
- `DELETE /admin/api/advancement/questions/{id}` - 删除题目
- `GET /admin/api/advancement/questions/search` - 搜索题库
- `POST /admin/api/advancement/questions/bulk-import` - 批量导入题目

### 4.9 退款管理
- `GET /admin/api/refunds` - 获取退款列表
- `PUT /admin/api/refunds/{id}/audit` - 审核退款

### 4.10 报告管理
- `GET /admin/api/reports/observation` - 获取观察期报告
- `POST /admin/api/reports/observation/generate` - 生成报告（stub）
- `PUT /admin/api/reports/observation/{id}/comment` - 添加评语

### 4.11 阅读数据
- `GET /admin/api/reading-data/stats` - 获取阅读统计
- `GET /admin/api/reading-data/trends` - 获取阅读趋势

### 4.12 系统管理
- `GET /admin/api/dashboard` - 获取仪表盘数据
- `GET /admin/api/config` - 获取所有配置
- `GET /admin/api/config/{key}` - 获取单个配置
- `PUT /admin/api/config/{key}` - 更新配置
- `POST /admin/api/config/init` - 初始化默认配置
- `GET /admin/api/users` - 获取用户列表
- `GET /admin/api/users/{id}` - 获取用户详情
- `GET /admin/api/children/search` - 搜索孩子
- `GET /admin/api/orders` - 获取订单列表
- `GET /admin/api/orders/{no}` - 获取订单详情
- `POST /admin/api/orders` - 管理员代客创建订单
- `PUT /admin/api/orders/{no}/status` - 更新订单状态
- `DELETE /admin/api/orders/{no}` - 删除订单
- `POST /admin/api/orders/{no}/refund` - 管理员代客发起退款
- `GET /admin/api/submissions` - 获取待审核提交
- `GET /admin/api/operation-logs` - 获取操作日志
- `GET /admin/api/recycle-bin` - 获取回收站
- `POST /admin/api/recycle-bin/{m}/{id}/restore` - 恢复数据
- `DELETE /admin/api/recycle-bin/{m}/{id}` - 永久删除
- `POST /admin/api/messages/send` - 发送消息
- `GET /admin/api/messages` - 获取消息列表
- `DELETE /admin/api/messages/{id}` - 删除消息
- `GET /admin/api/admins` - 获取管理员列表
- `POST /admin/api/admins` - 创建管理员
- `GET /admin/api/admins/{id}` - 获取管理员详情
- `PUT /admin/api/admins/{id}` - 更新管理员
- `DELETE /admin/api/admins/{id}` - 删除管理员
- `GET /admin/api/export/{module}` - 导出数据

---

## 五、启动指南

```bash
# 启动后端
cd /Users/litianyu/cc-projects/librio
python3 -m uvicorn backend.main:app --reload --port 8002

# 访问管理后台
URL: http://localhost:8002/admin/view/login
账号: admin
密码: Admin@2026

# 运行测试
python3 -m pytest tests/unit/ -v
python3 -m behave features/ -v
```

---

## 六、修复历史

### 2026-07-06 前端优化

1. **新增公共组件 `admin-pages.js`**
   - 统一确认弹窗 `AdminConfirm`（替代原生 confirm/prompt，支持 HTML 内容）
   - 通用分页 `AdminPagination`
   - 通用表格 `AdminTable`
   - 通用弹窗 `AdminModal`
   - 批量选择 `BatchSelect`

2. **7 个核心页面前端 JS 外迁**
   - `books.html` → `pages/books.js`
   - `booklist.html` → `pages/booklist.js`
   - `orders.html` → `pages/orders.js`
   - `reports.html` → `pages/reports.js`
   - `borrow.html` → `pages/borrow.js`
   - `activities.html` → `pages/activities.js`
   - `levels.html` → `pages/levels.js`

3. **修复 `showConfirm` HTML 渲染问题**
   - 原 `showConfirm('标题', html, null, '关闭')` 会把 HTML 当纯文本显示
   - 新 `AdminConfirm.show` 支持 HTML body，详情弹窗可正常渲染

### 2026-07-05 修复内容

1. **BaseSchema 设置 extra=forbid**
   - 修改 `backend/common/base_schema.py`
   - 所有继承 BaseSchema 的 Schema 自动禁止额外字段
   - 覆盖全部 22 个业务域

2. **路由层 ORM 操作清零**（43 处 → 0 处）
   - AdvancementService 新增 7 个查询方法
   - AdminService 新增 17 个管理方法
   - 所有路由改为调用 Service 方法

3. **前端上传路径修复**（3 处）
   - `backend/templates/admin/booklist.html`: `/admin/upload` → `/admin/api/upload`
   - `backend/templates/admin/books.html`: 3 处上传路径修复

4. **测试修复**
   - 移除测试中多余的 `amount` 字段（因为 `extra=forbid` 会拒绝额外字段）
   - 修复文件：`features/steps/deposit_steps.py`, `features/steps/user_enrollment_steps.py`

---

*检查点更新完成。所有架构问题已修复，代码质量达标。*
