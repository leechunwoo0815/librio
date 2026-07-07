# MegaWords (librio) 管理平台企业级审查报告

## 审查概要

- **审查日期**：2026-07-03
- **审查维度**：维度 5（安全审查）、维度 6（错误处理审查）、维度 8（代码质量审查）、维度 10（配置与部署审查）
- **发现问题总数**：34 项
  - 致命（P0）：0 项
  - 严重（P1）：9 项
  - 一般（P2）：16 项
  - 建议（P3）：9 项

> 审查范围：`/Users/litianyu/cc-projects/librio/backend/` 全部 Python 代码、`alembic/` 迁移脚本、`pyproject.toml`、`.gitignore`、`CLAUDE.md` 及关键管理端模板。

---

## 维度 5：安全审查

### 维度结论

- **结论**：有条件通过
- **关键改进项**：
  1. 必须引入 Token 黑名单/吊销机制，解决管理员登出后 token 仍有效的问题。
  2. 管理员代客退款、修改订单状态等资金操作必须补全业务校验与审计日志。
  3. 修复分片上传路径遍历与 `/admin/api/oplogs` 未授权写入问题。

### 发现的问题

#### [P1] Token 无黑名单/吊销机制，登出后仍可用
- **位置**：
  - `backend/middleware/auth.py:44`
  - `backend/middleware/admin_auth.py:45`
- **现状**：JWT 生成时带 `jti`，但代码未将其存入 Redis/数据库；`admin_logout` 仅返回 `{"success": True}`，由客户端清除 token。
- **问题**：token 在过期时间（管理员 8 小时、用户 2 小时）内无法吊销。一旦泄露或被中间人获取，可持续访问接口。
- **影响**：账号被盗、管理员离职/权限变更后，旧 token 仍能操作管理端；不符合 SOC 2 / ISO 27001 访问控制要求。
- **修复建议**：
  - 引入 Redis 黑名单，登出时将 `jti` 写入并设置与 token 相同的 TTL。
  - 在 `get_current_admin` / `get_current_user` 中校验 `jti` 是否在黑名单。
- **优先级**：P1

#### [P1] 管理员代客退款绕过未还书/罚款校验
- **位置**：`backend/domain/admin/routers/admin_system_router.py:173-210`
- **现状**：`admin_create_refund` 直接 `db.add(RefundApplication(...))`，未调用 `RefundService.apply_refund()`。
- **问题**：未执行 `apply_refund` 中的“名下是否有未归还实体书”校验（`borrow/service.py` 全局拦截网），也未校验押金/罚款状态。
- **影响**：存在未还书或欠款的情况下仍可发起订单退款，破坏业务红线与资金安全。
- **修复建议**：统一走 `RefundService.apply_refund()`，或在该路由中显式校验 `BorrowRecord` 活跃记录与 `child.outstanding_fines`。
- **优先级**：P1

#### [P1] 订单状态可被管理员直接标记为已支付且无审计日志
- **位置**：`backend/domain/admin/routers/admin_system_router.py:242-283`
- **现状**：`update_order_status` 接收 `data: dict`，允许直接将 `pay_status` 改为 `PAID`；`delete_order` 可直接软删除订单。两处均只校验 `ROLE_ADMIN`，未写入 `operation_log` 表。
- **问题**：高权限资金操作缺少不可抵赖的审计记录；`pay_status` 任意修改可导致账实不符。
- **影响**：资金舞弊难以追溯；财务对账存在风险。
- **修复建议**：
  - 对状态变更、删除、退款、创建订单等操作统一写入 `operation_log`（操作人、IP、原值、新值）。
  - 限制 `pay_status` 只允许特定状态转换。
- **优先级**：P1

#### [P1] 分片上传存在路径遍历风险
- **位置**：
  - `backend/domain/admin/routers/admin_books_router.py:156-170`
  - `backend/domain/admin/service.py:1420-1433`
- **现状**：`upload_id` 由客户端通过 Query 参数传入，直接作为 `CHUNK_DIR / upload_id` 的子目录名，未校验 `..`、斜杠等特殊字符。
- **问题**：攻击者可构造 `upload_id=../../../tmp/xyz`，在服务器任意可写目录创建子目录与文件。
- **影响**：目录遍历、磁盘占用、可能覆盖敏感文件。
- **修复建议**：
  - 对 `upload_id` 使用正则 `^[a-zA-Z0-9_-]+$` 严格校验。
  - 保存前使用 `Path.resolve()` 确保最终路径落在 `CHUNK_DIR` 下。
- **优先级**：P1

#### [P1] `/admin/api/oplogs` 未认证且写入外部日志文件
- **位置**：`backend/domain/admin/routers/admin_system_router.py:33-55`
- **现状**：该端点未加 `admin=Depends(...)`，接收任意 `dict` 后拼接字符串写入 `/tmp/admin_oplogs.log`。
- **问题**：未授权即可写入服务器日志文件；内容来自客户端，可注入伪造日志或导致磁盘占满。
- **影响**：日志完整性被破坏，且可能成为 DoS 入口。
- **修复建议**：
  - 添加 `admin=Depends(get_current_admin)`。
  - 使用结构化 Schema 校验字段；将审计日志写入 `operation_log` 表而非 `/tmp`。
- **优先级**：P1

#### [P2] 限流器为进程内存实现，多实例部署失效
- **位置**：`backend/middleware/rate_limit.py:14-51`
- **现状**：`RateLimiter` 使用 `_requests: dict` 保存在进程内存中。
- **问题**：生产环境多 worker / 多容器时，计数器不共享，单 IP 可在各实例上分别触发限额。
- **影响**：登录接口、支付回调等敏感端点的暴力破解/刷量防护能力被削弱。
- **修复建议**：使用 Redis（如 `redis-py` + 滑动窗口脚本）或 `fastapi-limiter` 替换内存计数器。
- **优先级**：P2

#### [P2] 文件上传仅校验扩展名，未校验文件内容与大小上限
- **位置**：
  - `backend/domain/admin/service.py:1376-1418`
  - `backend/domain/admin/routers/admin_books_router.py:141-191`
- **现状**：仅通过 `Path(filename).suffix` 白名单校验扩展名；单文件上限 10MB，但分片上传未限制每片大小与总分片数。
- **问题**：攻击者可将可执行文件重命名为 `.jpg` 上传；分片上传可无限累积临时文件。
- **影响**：上传 Webshell、磁盘耗尽。
- **修复建议**：
  - 增加 MIME type 与文件头 magic number 校验。
  - 分片上传限制单 chunk ≤ 5MB、总大小 ≤ 100MB、最多 200 片。
- **优先级**：P2

#### [P2] 用户导出包含 openid，用户列表暴露手机号
- **位置**：
  - `backend/domain/admin/service.py:1168-1170`（导出用户包含 `openid`）
  - `backend/domain/admin/service.py:486-550`（`list_users_with_children` 返回 `phone`）
- **现状**：管理端接口返回/导出用户隐私字段，未做脱敏或最小化。
- **问题**：内部人员可批量导出敏感标识与手机号，扩大泄露面。
- **影响**：违反儿童产品数据最小化原则，存在合规风险。
- **修复建议**：
  - 用户导出移除 `openid`。
  - 列表接口对手机号做中间四位脱敏；需要完整手机号的接口单独授权。
- **优先级**：P2

#### [P3] 数据导入脚本使用字符串拼接 LIMIT
- **位置**：`backend/seeds/import_ecdict.py:166`
- **现状**：`query += f" LIMIT {limit}"` 后直接 `src.execute(query)`。
- **问题**：该脚本非运行时接口，但仍为原生 SQL 拼接示例，可被后续复制为生产代码。
- **影响**：潜在的 SQL 注入范本。
- **修复建议**：使用参数化 `LIMIT :limit`。
- **优先级**：P3

#### [P3] DEBUG 模式硬编码测试 Token
- **位置**：`backend/middleware/auth.py:79-84`
- **现状**：当 `settings.DEBUG` 且 token 为 `"test-token-mock"` 时，返回 id=1 的用户。
- **问题**：测试后门仅在 DEBUG 生效，但常量硬编码。
- **影响**：若 DEBUG 误开则生产环境可被绕过认证。
- **修复建议**：将测试 token 改为环境变量注入；部署脚本禁止 DEBUG=true。
- **优先级**：P3

#### [P3] CORS 允许方法未包含 PATCH
- **位置**：`backend/main.py:126`
- **现状**：`allow_methods=["GET", "POST", "PUT", "DELETE"]`，缺少 `PATCH`。
- **问题**：项目中暂无 PATCH 接口，但未来若使用会触发预检失败。
- **影响**：前瞻性兼容性问题。
- **修复建议**：补充 `"PATCH"` 或改为 `allow_methods=["*"]` 并配合白名单。
- **优先级**：P3

---

## 维度 6：错误处理审查

### 维度结论

- **结论**：有条件通过
- **关键改进项**：
  1. 补充 `IntegrityError` 等数据库异常的全局/业务层处理，避免唯一约束冲突返回 500。
  2. 微信支付回调缺少平台证书时应返回业务错误而非 500。
  3. 增加集中式日志配置，确保异常可追溯。

### 发现的问题

#### [P1] 数据库唯一/外键冲突未友好处理，直接返回 500
- **位置**：
  - `backend/main.py:86-93`（全局 Exception handler 捕获但未区分）
  - `backend/domain/user/service.py:30-51`（仅校验手机号，未处理 openid 唯一冲突）
  - `backend/domain/book/service.py:58-88`（仅校验 ISBN，未处理并发唯一冲突）
- **现状**：`SQLAlchemy IntegrityError` 被全局 `Exception` handler 捕获，返回 `{"detail": "服务器内部错误，请稍后重试"}`。
- **问题**：用户重复提交、并发创建等场景会得到 500，而非 409 冲突提示；Sentry/日志中也缺少明确的错误分类。
- **影响**：用户体验差，错误监控噪音大，违背“零 500”目标。
- **修复建议**：
  - 在 `main.py` 增加 `IntegrityError` handler，返回 `409 Conflict` 与友好消息。
  - 或在 `UserService.create_user`、`BookService.create_book` 等服务层捕获 `IntegrityError` 后转 `ConflictError`。
- **优先级**：P1

#### [P2] 微信支付回调在平台证书未配置时抛出 500
- **位置**：
  - `backend/integrations/wechat/pay_v3.py:183-184`
  - `backend/domain/order/router.py:59-97`
- **现状**：`verify_callback` 中 `if not self.platform_cert: raise RuntimeError(...)`，`payment_callback` 未捕获 `RuntimeError`。
- **问题**：生产环境证书配置遗漏时，回调接口返回 500 堆栈（虽然全局 handler 会隐藏堆栈，但仍为 500）。
- **影响**：微信支付回调失败排查困难，且不符合友好错误响应要求。
- **修复建议**：将 `RuntimeError` 改为 `PaymentError`，或在 router 层捕获后返回明确的 400/422 错误。
- **优先级**：P2

#### [P2] 微信退款异步失败仅写站内消息，无结构化重试
- **位置**：`backend/domain/refund/service.py:94-141`
- **现状**：`_execute_wechat_refund_async` 捕获 Exception 后更新订单状态并写入 `SystemMessage`。
- **问题**：没有指数退避重试、没有死信队列、没有通知运维。
- **影响**：偶发网络抖动可能导致退款长期挂起，依赖定时任务告警（7 天后）才发现。
- **修复建议**：
  - 使用 APScheduler 或 Celery 任务重试最多 3 次。
  - 失败超阈值后发企业微信/邮件告警。
- **优先级**：P2

#### [P2] 外部词典 API 异常静默返回 None
- **位置**：`backend/utils/dict_api.py:67-69`
- **现状**：所有异常被捕获后返回 `None`。
- **问题**：调用方难以区分“查无此词”与“网络超时”。
- **影响**：可能将网络故障误判为无结果，影响学习体验。
- **修复建议**：返回 `{"error": "timeout"}` 或抛 `ValidationError`，由调用层决定兜底。
- **优先级**：P2

#### [P2] 缺少集中式日志配置与轮转
- **位置**：项目根目录无 `logging.yaml` 或 `dictConfig`
- **现状**：仅依赖 `alembic.ini` 的日志配置与 FastAPI/uvicorn 默认日志。
- **问题**：生产环境日志级别、格式、轮转、告警未统一。
- **影响**：关键错误可能未被收集；日志文件无限增长。
- **修复建议**：在 `backend/config.py` 或独立 `logging_config.py` 中配置 `dictConfig`，输出 JSON 格式到 stdout，并由外部 logrotate / Fluentd 收集。
- **优先级**：P2

#### [P3] 全局未捕获异常仅服务端记录堆栈
- **位置**：`backend/main.py:86-93`
- **现状**：`logger.error(..., exc_info=True)` 记录完整 traceback，但响应中仅返回 `detail`。
- **问题**：无（响应端符合要求）。
- **影响**：无用户影响，仅作为确认项。
- **修复建议**：保持当前行为；建议同时输出 `trace_id` 便于排查。
- **优先级**：P3

---

## 维度 8：代码质量审查

### 维度结论

- **结论**：有条件通过
- **关键改进项**：
  1. 消除系统管理路由中直接操作数据库的跨层调用。
  2. 统一 Schema 校验，移除 `data: dict` 的裸参数。
  3. 删除重复函数，规范返回格式。

### 发现的问题

#### [P1] 系统管理路由存在大量跨层直接查库
- **位置**：
  - `backend/domain/admin/routers/admin_system_router.py:186-210`（代客退款直接查 `Order`）
  - `backend/domain/admin/routers/admin_system_router.py:224-239`（代客创建订单直接查 `Child`）
  - `backend/domain/admin/routers/admin_system_router.py:242-265`（修改订单状态直接查 `Order`）
  - `backend/domain/admin/routers/admin_system_router.py:268-283`（删除订单直接查 `Order`）
  - `backend/domain/admin/routers/admin_system_router.py:377-391`（删除消息直接查 `SystemMessage`）
  - `backend/domain/admin/routers/admin_system_router.py:396-437`（管理员列表直接查 `Admin`）
  - `backend/domain/admin/routers/admin_system_router.py:451-471`（单个管理员直接查 `Admin`）
- **现状**：Router 层直接构造 SQLAlchemy 查询并 `db.commit()`，未通过 Service/Repository。
- **问题**：违反 `CLAUDE.md` 分层宪法（Router 不应含业务逻辑/事务）。
- **影响**：重复代码、事务边界混乱、单元测试难以 mock、未来权限/审计改造成本高。
- **修复建议**：将上述逻辑迁移到 `AdminService`、`RefundService`、`OrderService` 或新增 `MessageService`。
- **优先级**：P1

#### [P2] `BookService` 存在重复定义的 `update_book`
- **位置**：`backend/domain/book/service.py:90-103` 与 `104-117`
- **现状**：同一类中两个完全相同的 `update_book` 方法，后者覆盖前者。
- **问题**：Python 运行时不会报错，但属于代码重复与维护隐患。
- **影响**：修改时容易漏改；代码阅读者困惑。
- **修复建议**：删除其中一个定义。
- **优先级**：P2

#### [P2] 多处路由使用裸 `data: dict` 接收请求体
- **位置**：
  - `backend/domain/admin/routers/admin_system_router.py:176`
  - `backend/domain/admin/routers/admin_system_router.py:213`
  - `backend/domain/admin/routers/admin_system_router.py:245`
- **现状**：管理员退款、创建订单、修改订单状态均使用 `data: dict`。
- **问题**：无字段校验、无 `extra="forbid"`、无文档化 Schema，OpenAPI 生成的请求体显示为 `{}`。
- **影响**：前端对接困难；非法字段会被静默忽略。
- **修复建议**：定义 `AdminRefundCreateRequest`、`AdminOrderCreateRequest`、`AdminOrderStatusUpdateRequest` 等 Pydantic Schema。
- **优先级**：P2

#### [P2] `AdminService.update_admin` 角色比较逻辑低效且可读性差
- **位置**：`backend/domain/admin/service.py:1652`
- **现状**：在 `for key, value in update_data.items()` 循环内部，每次迭代都查询当前管理员角色：`self.db.query(Admin).filter(Admin.id == current_admin_id).first().role`。
- **问题**：重复查询数据库；且 `data.role < current_role` 的语义（数字越小权限越高）不够直观。
- **影响**：性能浪费，代码可维护性差。
- **修复建议**：将当前管理员角色查询移到循环外；使用 `AdminRole` 枚举比较并添加注释。
- **优先级**：P2

#### [P2] 返回格式不一致，部分接口手动 `model_dump`
- **位置**：
  - `backend/domain/admin/routers/admin_books_router.py:38-44`
  - `backend/domain/admin/service.py:213-222`（`list_venues` 返回 dict）
  - `backend/domain/admin/service.py:348-358`（`list_teachers` 返回 dict）
- **现状**：部分列表接口返回 `PaginatedResponse`，部分返回手写 dict；`BookService` 有时返回模型，有时 `model_dump()`。
- **问题**：响应结构不统一，增加前端与测试成本。
- **影响**：API 契约不一致。
- **修复建议**：所有列表接口统一使用 `PaginatedResponse[T]`；路由层不手动 `model_dump()`。
- **优先级**：P2

#### [P2] `BaseSchema` 未设置 `extra="forbid"`
- **位置**：`backend/common/base_schema.py:82-85`
- **现状**：`model_config` 仅配置 `from_attributes=True` 与 `populate_by_name=True`。
- **问题**：默认 `extra="ignore"`，未知字段会被静默丢弃。
- **影响**：拼写错误的字段无法被前端及时发现。
- **修复建议**：`ConfigDict(..., extra="forbid")`；对必须兼容旧字段的 Schema 单独覆盖。
- **优先级**：P2

#### [P3] 回收站支持的模块硬编码且仅 4 个
- **位置**：`backend/domain/admin/service.py:914-919`
- **现状**：`model_map` 仅支持 `book/activity/teacher/venue`。
- **问题**：其他实体（订单、消息、题库等）删除后无法恢复或永久删除。
- **影响**：功能不完整，与“33 个页面”的管理范围不匹配。
- **修复建议**：按模块注册模型映射表，或提供通用 `BaseModel` 注册机制。
- **优先级**：P3

#### [P3] 代码注释中英文混用但总体一致
- **位置**：跨文件
- **现状**：函数/类/变量命名基本为英文，注释与错误消息为中文，符合项目约定。
- **问题**：个别错误消息夹杂英文代码（如 `ValidationError("未知订单类型: {order_data.type}")`）。
- **影响**：用户可读性一般。
- **修复建议**：用户可见的错误消息统一为中文，内部日志保留英文。
- **优先级**：P3

#### [P3] `User.password` 字段未使用且无哈希方法
- **位置**：`backend/domain/user/models.py:18`
- **现状**：User 表有 `password` 字段，但项目仅使用微信登录，未提供 `set_password`/`verify_password`。
- **问题**：未来若增加账号密码登录，容易误用明文存储。
- **影响**：潜在安全隐患。
- **修复建议**：移除该字段；或添加 bcrypt 哈希方法并明确仅用于未来扩展。
- **优先级**：P3

---

## 维度 10：配置与部署审查

### 维度结论

- **结论**：不通过
- **关键改进项**：
  1. 立即补充锁定版本的依赖清单（`requirements.txt` 或 `pyproject.toml` [project]）。
  2. 根据 `alembic check` 结果生成新的迁移脚本，消除模型漂移。
  3. `alembic.ini` 改为从环境变量读取数据库连接。
  4. 建立日志配置、回滚方案与部署文档。

### 发现的问题

#### [P1] 缺少锁定版本的依赖清单
- **位置**：`pyproject.toml`、`requirements.txt`
- **现状**：`pyproject.toml` 仅包含 Ruff 配置，无 `[project]` 依赖；项目根目录无 `requirements.txt` 或 `poetry.lock`。
- **问题**：无法复现生产环境依赖；无法运行 `pip-audit` / `safety` 检查已知漏洞；部署依赖人工 pip install。
- **影响**：供应链安全不可控，可能出现“开发环境可跑、生产跑不了”或安装到带漏洞版本。
- **修复建议**：
  - 使用 `pip freeze > requirements.txt` 或迁移到 Poetry / PDM。
  - 区分 `requirements.txt` 与 `requirements-dev.txt`。
- **优先级**：P1

#### [P1] Alembic 模型与当前数据库存在漂移
- **位置**：`alembic/versions/`、`backend/domain/*/models.py`
- **现状**：执行 `alembic check` 后出现大量差异，包括但不限于：
  - 删除表：`collection`、`audio_file`、`borrow`、`assessment`
  - 删除列：`venue.latitude`、`venue.longitude`、`venue.cover`、`venue.business_hours`
  - 新增唯一约束：`uq_child_word`
- **问题**：当前迁移脚本未覆盖模型 recent 变更，新环境 `alembic upgrade head` 后的表结构与代码模型不一致。
- **影响**：生产部署可能出现 `Column not found` 或约束冲突。
- **修复建议**：
  - 在干净数据库上运行 `alembic revision --autogenerate -m "sync_v35_model_drift"`。
  - 审查生成的 upgrade/downgrade 脚本，补充数据迁移（如 `venue` 旧列数据保留或清理）。
- **优先级**：P1

#### [P2] `alembic.ini` 硬编码数据库连接
- **位置**：`alembic.ini:89`
- **现状**：`sqlalchemy.url = mysql+pymysql://root:@localhost:3306/megawords?charset=utf8mb4`。
- **问题**：部署到不同环境需要手动改文件，容易泄露凭据，且与 `backend/config.py` 的环境变量注入不一致。
- **影响**：CI/CD 与多环境部署困难。
- **修复建议**：在 `alembic/env.py` 中读取 `DATABASE_URL` 环境变量覆盖 `config.set_main_option("sqlalchemy.url", ...)`。
- **优先级**：P2

#### [P2] 无集中式日志配置与错误告警
- **位置**：项目根目录、`backend/main.py`
- **现状**：未配置 Python logging；未接入 Sentry / PagerDuty / 企业微信告警。
- **问题**：生产异常只能通过 uvicorn stdout 查看，无结构化、无分级、无告警。
- **影响**：故障响应慢，关键错误可能被忽略。
- **修复建议**：
  - 增加 `LOG_LEVEL`、`LOG_FORMAT` 环境变量与 `dictConfig`。
  - 关键异常（支付失败、退款失败、定时任务失败）发送告警通知。
- **优先级**：P2

#### [P2] 缺少数据迁移与回滚方案文档
- **位置**：`docs/`、`README.md`
- **现状**：未见 `ROLLBACK.md`、部署回滚 SOP、数据备份策略说明。
- **问题**：上线后若迁移失败或代码 Bug，无法快速回滚到上一版本。
- **影响**：生产事故恢复时间（MTTR）长。
- **修复建议**：
  - 记录每次发版对应的 Alembic `down_revision`。
  - 制定“代码回滚 + 数据库 downgrade + 数据备份”三步回滚方案。
- **优先级**：P2

#### [P2] 生产环境默认数据库密码为空
- **位置**：`backend/config.py:29`
- **现状**：`DB_PASSWORD: str = ""`。
- **问题**：若环境变量未设置，生产环境将使用空密码连接数据库。
- **影响**：虽然 `SECRET_KEY` 有生产校验，但数据库密码无类似保护。
- **修复建议**：参考 `SECRET_KEY` 校验逻辑，在非 DEBUG 环境下若 `DB_PASSWORD` 为空则启动失败。
- **优先级**：P2

#### [P3] 定时任务无分布式锁
- **位置**：`backend/tasks/scheduler.py`
- **现状**：14 个 APScheduler 任务全部在单进程 BackgroundScheduler 中运行。
- **问题**：多实例部署时任务会重复执行。
- **影响**：消息重复发送、报告重复生成。
- **修复建议**：使用 Redis 分布式锁（如 `redis_lock`）或采用单一 worker 跑定时任务。
- **优先级**：P3

#### [P3] 健康检查端点暴露版本号
- **位置**：`backend/main.py:229-232`
- **现状**：`/health` 返回 `{"status": "ok", "version": settings.APP_VERSION}`。
- **问题**：版本信息可被外部获取，利于攻击者匹配已知漏洞。
- **影响**：低危信息泄露。
- **修复建议**：`version` 仅在内部 `/health/detail` 返回，或要求认证。
- **优先级**：P3

---

## 总体结论

- **整体评级**：C（有条件通过，需完成 P1 项后方可进入生产环境）
- **关键风险项**：
  1. 缺少锁定版本的依赖清单与 Alembic 模型漂移，部署不可预测。
  2. 管理员资金操作（代客退款、改订单状态）绕过业务校验且无审计日志。
  3. Token 无吊销机制， stolen token 可长期滥用。
  4. 分片上传路径遍历与 `/admin/api/oplogs` 未认证写入是明确的安全漏洞。
- **建议的修复优先级**：
  1. **立即（P1）**：补充依赖清单、修复 Alembic 漂移、修复路径遍历与 oplogs 未认证、统一资金操作校验与审计、引入 Token 黑名单。
  2. **短期（P2）**：补齐数据库异常处理、微信支付回调错误、日志与告警、限流 Redis 化、文件上传内容校验、分层重构。
  3. **中期（P3）**：清理重复代码、统一 Schema/响应格式、完善回收站模块、文档化回滚方案。
- **下一步行动项**：
  1. 由架构师确认资金操作审计字段与 Token 黑名单方案。
  2. 由后端工程师按上述优先级修复并补充单元测试。
  3. 修复后重新运行 `pytest`、`ruff`、`alembic check` 与渗透测试（重点：文件上传、未授权接口、JWT 吊销）。

---

## 审查依据文件

| 文件 | 用途 |
|------|------|
| `docs/compose/specs/expert-audit-prompt.md` | 审查 Prompt 与维度定义 |
| `CLAUDE.md` | 项目宪法、分层架构与业务红线 |
| `pyproject.toml` | 依赖与 Ruff 配置 |
| `backend/main.py` | 全局异常、CORS、路由挂载 |
| `backend/config.py` | 环境变量与敏感配置 |
| `backend/common/exceptions.py` | 业务异常体系 |
| `backend/middleware/auth.py` / `admin_auth.py` / `rate_limit.py` | 认证、授权、限流 |
| `backend/domain/admin/routers/admin_system_router.py` | 系统管理路由（问题集中区） |
| `backend/domain/admin/routers/admin_books_router.py` | 图书/文件上传路由 |
| `backend/domain/admin/service.py` | 管理端业务逻辑 |
| `backend/domain/refund/service.py` | 退款逻辑 |
| `backend/domain/order/router.py` / `service.py` | 订单与支付回调 |
| `backend/integrations/wechat/pay_v3.py` | 微信支付 V3 |
| `backend/alembic/` | 数据库迁移脚本 |

*报告生成时间：2026-07-03*
