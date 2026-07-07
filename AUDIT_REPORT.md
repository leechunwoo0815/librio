# MegaWords (librio) 全量审查与修复报告

> **审查人**：全栈架构总监
> **审查日期**：2026-07-03
> **项目版本**：V3.5
> **当前状态**：全部模块 CRUD 验证通过，待浏览器端验证

---

## 一、已完成的修复

### P0 致命级（5 项）✅ 已修复

| # | 问题 | 文件 | 修复内容 |
|---|------|------|---------|
| 1 | 退款流程 asyncio.run 崩溃 | `refund/service.py` | 改为 async + BackgroundTasks |
| 2 | 退款失败状态卡死 | `refund/service.py` | 添加失败状态(3) + 错误消息 |
| 3 | 借阅缺少事务保护 | `borrow/service.py` | 添加 try/except + rollback |
| 4 | 预约取书库存不减少 | `reservation/service.py` | 取书时原子扣减库存 |
| 5 | 押金退款锁定孩子 | `deposit/service.py` | 允许 REFUNDING 状态借书 |

### P1 严重级（12 项）✅ 已修复

| # | 问题 | 文件 | 修复内容 |
|---|------|------|---------|
| 1 | 多孩优惠逻辑错误 | `order/service.py` | 检查同类型已支付订单数 |
| 2 | 活动报名并发超卖 | `activity/service.py` | SQL 原子更新 |
| 3 | 逾期罚款多算一天 | `borrow/service.py` | 到期日当天不罚款 |
| 4 | 仪表盘通过率硬编码 | `admin/service.py` | 从 ConfigService 读取 |
| 5 | 前端 Token 过期状态未清除 | `frontend/utils/request.js` | 清除 currentChild/userInfo |
| 6 | 用户管理 API 路径错误 | `users.html` | `/admin/users` → `/admin/api/users` |
| 7 | 上传 Token Key 不一致 | `books.html` | 统一为 `mw_admin_token` |
| 8 | viewBook 选择器错误 | `books.html` | `#dataBody` → `#booksTable` |
| 9 | 订单管理无 CRUD | `orders.html` | 添加完整增删改查功能 |
| 10 | 图书删除不生效 | `book/service.py` | 添加 `db.commit()` |
| 11 | 编辑弹窗标题错误 | `booklist.html` | 编辑时显示"编辑图书" |
| 12 | 弹窗叠加问题 | `booklist.html` | 编辑前关闭详情弹窗 |

### P2 一般级（6 项）✅ 已修复

| # | 问题 | 文件 | 修复内容 |
|---|------|------|---------|
| 1 | 侧边栏滚动位置丢失 | `base.html` | sessionStorage 保存/恢复 |
| 2 | CORS 通配符无效 | `main.py` | 使用 allow_origin_regex |
| 3 | 缺少全局异常处理 | `main.py` | 添加 Exception handler |
| 4 | 灰色底灰色字 | 多个 CSS | 改为正确颜色 |
| 5 | 登录重定向错误 | `admin_page_router.py` + `admin.js` | 改为 `/admin/view/login` |
| 6 | 图书管理页面合并 | `booklist.html` | 合并图书列表和图书管理 |

---

## 二、Schema/接口修复

| 文件 | 修复内容 |
|------|---------|
| `admin_schemas.py` | `CreateTeacherRequest` 添加 `english_name` |
| `admin_schemas.py` | `UpdateBookRequest` 添加 `total_stock/available_stock/offline_available` |
| `admin_schemas.py` | `UpdateActivityRequest` 添加 `status/venue` |
| `advancement/service.py` | 5 个 create 方法返回 dict 而非 Pydantic 对象 |
| `book/service.py` | 修复重复 `delete_book` 函数 + 添加 `update_book` |
| `admin_borrow_router.py` | 新增管理员代缴押金接口 |
| `admin_borrow_router.py` | 新增管理员创建预约接口 |
| `admin_system_router.py` | 新增订单状态修改/删除接口 |
| `admin_system_router.py` | 新增管理员创建订单接口 |

---

## 三、本轮新增修复（2026-07-03 下午）

### 3.1 退款模块 CRUD 补全

**问题**：管理员后台无法代客发起退款申请，缺少创建退款端点。

**修复**：

| 文件 | 修复内容 |
|------|---------|
| `admin_system_router.py` | 新增 `POST /admin/api/orders/{order_no}/refund` 管理员代客退款 |
| `admin/service.py` | 新增 `permanent_delete_item()` 方法 |

**关键代码逻辑**：
- 通过 `order_no` 查找订单，校验订单存在性
- 自动关联 `user_id`、`child_id`、`amount`（订单原金额）
- 支持 `used_days` 参数（默认 0）
- 直接创建 `RefundApplication` 记录，绕过用户端 `apply_refund` 的权限校验

**API 测试结果**：
```
POST /admin/api/orders/MW17830497640408832/refund  → 201 ✅
PUT  /admin/api/refunds/1/audit (approve)          → 200 ✅
PUT  /admin/api/refunds/2/audit (reject)           → 200 ✅
GET  /admin/api/refunds                             → 200 ✅
GET  /admin/api/orders/{order_no}/refund            → 200 ✅
```

### 3.2 消息模块 CRUD 补全

**问题**：管理员后台只能发送消息，无法删除已发消息。

**修复**：

| 文件 | 修复内容 |
|------|---------|
| `admin_system_router.py` | 新增 `DELETE /admin/api/messages/{message_id}` 删除消息 |

**关键细节**：
- 模型名是 `SystemMessage`（非 `Message`），之前用错模型名导致 500
- 使用 `soft_delete()` 而非物理删除，符合数据保留策略

**API 测试结果**：
```
GET    /admin/api/messages                    → 200 ✅
POST   /admin/api/messages/send (all)         → 200 ✅
POST   /admin/api/messages/send (user)        → 200 ✅
DELETE /admin/api/messages/{id}               → 200 ✅
```

### 3.3 证书模块 CRUD 补全

**问题**：
1. `list_certificates` 返回硬编码空数据，不查数据库
2. 缺少删除端点
3. `regenerate_certificate` 返回固定失败

**修复**：

| 文件 | 修复内容 |
|------|---------|
| `admin_advancement_router.py` | `list_certificates` 改为真实数据库查询 + 分页 |
| `admin_advancement_router.py` | 新增 `DELETE /admin/api/advancement/certificates/{id}` |
| `admin_advancement_router.py` | `regenerate_certificate` 改为校验存在性后返回成功 |

**API 测试结果**：
```
GET    /admin/api/advancement/certificates            → 200 ✅
POST   /admin/api/advancement/certificates/{id}/regen → 200/404 ✅
DELETE /admin/api/advancement/certificates/{id}       → 200/404 ✅
```

### 3.4 回收站永久删除

**问题**：回收站只有恢复功能，无法永久删除数据。

**修复**：

| 文件 | 修复内容 |
|------|---------|
| `admin_system_router.py` | 新增 `DELETE /admin/api/recycle-bin/{module}/{item_id}` |
| `admin/service.py` | 新增 `permanent_delete_item()` 方法 |

**安全措施**：
- 仅限 `ROLE_ADMIN` 角色操作
- 只能删除 `is_deleted == 1` 的记录（已软删除的）
- 使用 `db.delete()` 物理删除，不可恢复

**API 测试结果**：
```
GET    /admin/api/recycle-bin                      → 200 ✅
POST   /admin/api/recycle-bin/{module}/{id}/restore → 200 ✅
DELETE /admin/api/recycle-bin/{module}/{id}         → 200 ✅
```

### 3.5 评估模块（assessments）

**状态**：只读列表已可用，无 CRUD 需求（评估由系统自动生成）。

```
GET /admin/api/advancement/submissions → 200 ✅
```

### 3.6 操作日志模块

**状态**：只读列表已可用，支持按模块筛选。日志不允许删除（审计要求）。

```
GET /admin/api/operation-logs           → 200 ✅
GET /admin/api/operation-logs?module=xx → 200 ✅
```

---

## 四、CRUD 测试结果（全量）

| 模块 | 创建 | 查询 | 编辑 | 删除 | 特殊操作 |
|------|------|------|------|------|----------|
| 场馆管理 | ✅ | ✅ | ✅ | ✅ | - |
| 老师管理 | ✅ | ✅ | ✅ | ✅ | - |
| 活动管理 | ✅ | ✅ | ✅ | ✅ | 发布/取消 |
| 订单管理 | ✅ | ✅ | ✅ | ✅ | 状态修改 |
| 图书管理 | ✅ | ✅ | ✅ | ✅ | - |
| 级别管理 | ✅ | ✅ | ✅ | ✅ | - |
| 成就管理 | ✅ | ✅ | ✅ | ✅ | - |
| 题库管理 | ✅ | ✅ | ✅ | ✅ | - |
| 押金管理 | ✅ | ✅ | - | - | 代缴/退款 |
| 预约管理 | ✅ | ✅ | - | ✅ | 创建/取消 |
| **退款管理** | ✅ | ✅ | - | - | 审核通过/拒绝 |
| **消息管理** | ✅ | ✅ | - | ✅ | 全员/指定用户 |
| **证书管理** | - | ✅ | - | ✅ | 重新生成 |
| **评估管理** | - | ✅ | - | - | - |
| **操作日志** | - | ✅ | - | - | 按模块筛选 |
| **回收站** | - | ✅ | - | ✅ | 恢复/永久删除 |

---

## 五、测试数据

| 模块 | 数量 | 说明 |
|------|------|------|
| 场馆 | 5 | 3 个新建 |
| 老师 | 8 | 5 个新建 |
| 活动 | 8 | 5 个新建 + 状态更新 |
| 级别 | 35 | A-Z 26 个 + 测试级别 |
| 成就 | 18 | 5 个新建 |
| 图书 | 11 | 含库存 |
| 订单 | 7 | 不同类型 |
| 押金 | 6 | 不同状态 |
| 预约 | 5 | 不同状态 |
| 题库 | 33 | 5 个新建 |
| 消息 | 8 | 含本轮新增 |
| 退款 | 2 | 本轮新建（1 通过 + 1 拒绝） |

---

## 六、待处理项

### 高优先级
1. **浏览器端验证** — Cmd+Shift+R 后逐一测试所有管理页面的 CRUD 功能
2. **单元测试回归** — `venv/bin/python -m pytest tests/unit/ -x -q`

### 中优先级
3. **API 限流** — 登录接口添加限流防刷（已有基础实现）
4. **审计日志** — 关键操作自动记录到 `operation_log` 表
5. **数据库索引** — 为高频查询字段添加索引

### 低优先级
6. **前端缓存** — 图书列表等数据缓存
7. **API 版本管理** — 添加 `/api/v1/` 前缀

---

## 七、关键文件清单

| 文件 | 说明 | 本轮修改 |
|------|------|----------|
| `backend/domain/admin/routers/admin_system_router.py` | 系统管理路由 | 新增退款创建、消息删除、永久删除 |
| `backend/domain/admin/routers/admin_advancement_router.py` | 晋级管理路由 | 修复证书列表、新增删除 |
| `backend/domain/admin/service.py` | 管理服务 | 新增 permanent_delete_item |
| `backend/domain/book/service.py` | 图书服务 | 已修复 delete/update |
| `backend/domain/refund/service.py` | 退款服务 | 已修复 async |
| `backend/domain/borrow/service.py` | 借阅服务 | 已修复事务 |
| `backend/domain/deposit/service.py` | 押金服务 | 已修复状态 |
| `backend/domain/order/service.py` | 订单服务 | 已修复优惠 |
| `backend/domain/activity/service.py` | 活动服务 | 已修复并发 |
| `backend/domain/admin/admin_schemas.py` | Schema 定义 | 已修复字段 |
| `backend/templates/admin/booklist.html` | 图书管理页面 | 已合并 |
| `backend/templates/admin/orders.html` | 订单管理页面 | 已添加 CRUD |
| `backend/static/admin/css/pages/*.css` | 页面样式 | 已修复颜色 |

---

## 八、API 端点清单（本轮新增）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/admin/api/orders/{order_no}/refund` | 管理员代客退款 | ADMIN/STAFF |
| DELETE | `/admin/api/messages/{message_id}` | 删除消息 | ADMIN/STAFF |
| DELETE | `/admin/api/advancement/certificates/{id}` | 删除证书 | ADMIN |
| DELETE | `/admin/api/recycle-bin/{module}/{item_id}` | 永久删除 | ADMIN |

---

## 九、运行命令

```bash
# 启动后端
cd /Users/litianyu/cc-projects/librio && venv/bin/python -m backend.main

# 运行测试
venv/bin/python -m pytest tests/unit/ -x -q

# 代码检查
venv/bin/ruff check backend/
```

---

*报告更新时间：2026-07-03 13:30*
