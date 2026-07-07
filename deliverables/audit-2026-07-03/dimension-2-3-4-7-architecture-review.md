# MegaWords（librio）管理平台企业级审查报告

## 审查概要

- **审查日期**：2026-07-03
- **审查维度**：维度 2（API 接口）、维度 3（业务逻辑）、维度 4（数据库与模型）、维度 7（性能）
- **发现问题总数**：39 项
  - 致命（P0）：6 项
  - 严重（P1）：17 项
  - 一般（P2）：12 项
  - 建议（P3）：4 项

> 审查范围：backend/domain/ 下 23 个业务域的 router/service/models/schemas、backend/main.py、backend/common/、backend/middleware/、backend/tasks/scheduler.py、backend/events/。对照 PRD V3.5 与 ARCHITECTURE.md 逐条核验。

---

## 维度 2：API 接口审查

**维度结论：有条件通过**

整体 RESTful 分层与认证框架已落地，管理端统一前缀 `/admin/api`、用户端统一前缀 `/`， ownership 层有效消除大量手动越权校验。但存在少量未认证端点、过多裸 `dict` 入参、用户端 Schema 未统一 `extra="forbid"`、部分端点响应模型缺失等问题，影响接口契约一致性与安全基线。

### 发现的问题

#### [P0] `/admin/api/oplogs` 接收前端操作日志未做任何认证
- **位置**：`backend/domain/admin/routers/admin_system_router.py:33`
- **现状**：`@router.post("/oplogs") def receive_oplogs(data: dict):` 未声明 `admin=Depends(get_current_admin)` 或任何依赖，任何匿名客户端均可向该端点推送数据，并直接写入 `/tmp/admin_oplogs.log`。
- **问题**：未认证即允许写入服务器本地文件，存在日志伪造、磁盘耗尽（无长度限制循环写入）及潜在目录遍历/命令注入风险（虽然当前拼接固定，但后续扩展易被忽略）。
- **影响**：违反 SOC 2 / ISO 27001 认证最小权限原则；可被恶意刷屏写满 `/tmp` 导致服务异常。
- **修复建议**：
  1. 立即添加 `admin=Depends(get_current_admin)`；
  2. 用 Pydantic Schema 校验 `data` 结构并限制单条/批量日志大小；
  3. 写入路径改为按日期轮转，不直接写 `/tmp`；
  4. 生产环境建议通过标准日志库或日志平台接收，不暴露文件写接口。
- **优先级**：P0

#### [P0] 用户端业务 Schema 未配置 `extra="forbid"`，可接受未知字段
- **位置**：`backend/common/base_schema.py:74-85`、`backend/domain/borrow/schemas.py`、`backend/domain/deposit/schemas.py`、`backend/domain/order/schemas.py`、`backend/domain/reservation/schemas.py`、`backend/domain/activity/schemas.py` 等全部用户端 Schema
- **现状**：`BaseSchema` 仅配置 `from_attributes=True, populate_by_name=True`，未设置 `extra="forbid"`。用户端 Schema 直接继承 `BaseSchema`，未再覆盖 `model_config`。
- **问题**：与架构文档“52/52 admin_schemas 已 forbid”形成鲜明对比，但用户端同样应当拒绝未知字段，避免客户端误传/恶意字段被静默忽略或导致内部状态异常。
- **影响**：接口契约无法严格约束；后续字段扩展时旧客户端/恶意请求可塞入未知字段而不报错，增加排障与安全隐患。
- **修复建议**：在 `BaseSchema.model_config` 中统一加入 `extra="forbid"`；若个别接口确实需要宽松，可单独配置 `extra="ignore"` 并显式注释。
- **优先级**：P0

#### [P1] 管理端多个关键端点仍使用裸 `dict` 作为请求 Schema
- **位置**：
  - `backend/domain/admin/routers/admin_system_router.py:173` `data: dict`（管理员代发起退款）
  - `backend/domain/admin/routers/admin_system_router.py:213` `data: dict`（管理员代创建订单）
  - `backend/domain/admin/routers/admin_system_router.py:242` `data: dict`（更新订单状态）
  - `backend/domain/admin/routers/admin_system_router.py:325` `data: dict`（回收站恢复）
  - `backend/domain/admin/routers/admin_reports_router.py:168` `data: dict = None`（生成观察期报告）
  - `backend/domain/admin/routers/admin_reports_router.py:178` `data: dict`（添加评语）
  - `backend/domain/admin/routers/admin_borrow_router.py:167` `data: dict`（管理员代缴押金）
  - `backend/domain/admin/routers/admin_borrow_router.py:273` `data: dict`（管理员创建预约）
- **现状**：上述端点未定义 Pydantic Request Schema，直接使用 `dict`。
- **问题**：缺少字段校验、类型转换、长度限制、`extra="forbid"`；路由层无法生成准确 OpenAPI 文档，前端契约无法自动校验。
- **影响**：不符合架构文档“所有请求参数使用 Pydantic Schema（而非裸 dict）”的约束；容易引入 422/500 错误及越权参数（如订单状态被任意整数覆盖）。
- **修复建议**：为每个端点在 `admin_schemas.py` 中定义专用 Request Schema，显式声明字段类型、max_length、ge/le、枚举值等，并替换 `dict` 入参。
- **优先级**：P1

#### [P1] 管理端 `RefundResponse` 等金额字段使用 `float`
- **位置**：`backend/domain/admin/admin_schemas.py:579-591`
- **现状**：`RefundResponse.amount: float | None = None`，且 `order_no`、`admin_comment` 等字段名与 `RefundApplication` 模型字段不一致（模型为 `refund_amount`、`review_comment`）。
- **问题**：金融业务金额使用 float 会产生精度丢失；Schema 字段与模型字段命名不一致，导致 `from_attributes=True` 时可能取不到值（当前 router 中手动组装已规避，但不应依赖手动拼接）。
- **影响**：退款金额显示/计算可能出现 0.01 元级偏差；财务对账存在风险。
- **修复建议**：金额字段统一改为 `Decimal`；Schema 字段与模型字段对齐，或显式使用 `Field(..., alias=...)`。
- **优先级**：P1

#### [P1] `/activity/{activity_id}/checkin` 批量签到未限定管理员角色
- **位置**：`backend/domain/activity/router.py:73-82`
- **现状**：`batch_checkin` 仅依赖 `current_user=Depends(get_current_user)`，未调用 `require_role(ROLE_ADMIN, ROLE_STAFF)`。
- **问题**：普通家长用户只要登录即可对活动进行批量签到（虽然 child_ids 需对应已报名孩子，但接口语义是管理员/组织者签到）。
- **影响**：普通用户可伪造或覆盖签到状态，破坏活动运营数据。
- **修复建议**：该端点应限定管理员角色；若小程序端需要用户自助签到，应使用单条签到端点 `/enroll/{enrollment_id}/sign-in` 并严格校验归属。
- **优先级**：P1

#### [P1] `/order/upgrade-options/{child_id}` 与 `/order/upgrade` 未校验孩子归属
- **位置**：`backend/domain/order/router.py:162-183`
- **现状**：两个端点仅注入 `current_user=Depends(get_current_user)`，未使用 `GetOwnedChild` 或 `verify_child_ownership`。
- **问题**：任何登录用户只要知道 child_id 即可查询/创建其他用户的会员升级订单，存在 IDOR 越权风险。
- **影响**：用户信息泄露（剩余价值、当前会员类型）、可被恶意创建升级订单。
- **修复建议**：两个端点均添加 `child=Depends(GetOwnedChild())` 或在 service 中校验 `child.user_id == user_id`。
- **优先级**：P1

#### [P2] 多个列表/详情端点未声明 `response_model` 或返回裸字典
- **位置**：
  - `backend/domain/admin/routers/admin_books_router.py:25` `@router.get("/books")` 无 response_model，返回手动 dict
  - `backend/domain/admin/routers/admin_system_router.py:396` `@router.get("/admins")` 无 response_model
  - `backend/domain/admin/routers/admin_borrow_router.py:106` `@router.get("/deposits")` 无 response_model
  - `backend/domain/admin/routers/admin_borrow_router.py:189` `@router.get("/reservations")` 无 response_model
  - `backend/domain/admin/routers/admin_advancement_router.py:35` `@router.get("/levels")` 无 response_model
  - `backend/domain/activity/router.py:63` `@router.get("/{activity_id}/enrollments")` 无 response_model
- **现状**：端点返回 `dict` 或 `list[dict]`，未通过 Pydantic 模型约束输出。
- **问题**：OpenAPI 文档不完整；输出字段与类型无法自动校验；前端契约维护成本高。
- **影响**：接口文档不准确，前后端联调容易出错；架构文档“所有路由都有 response_model”未完全落地。
- **修复建议**：为上述端点补齐 `response_model`，已有 `PaginatedResponse` 等可用则优先复用；确实需要动态字段的，定义专用 Response Schema。
- **优先级**：P2

#### [P2] `OrderCreate.type` 用整数范围校验，未使用枚举
- **位置**：`backend/domain/order/schemas.py:12-19`
- **现状**：`type: int = Field(..., ge=1, le=5, description="订单类型: 1=亲子课...")`
- **问题**：仅限制范围，不限制具体枚举值；调用方传入 4.5 等值会被 Pydantic 截断或校验失败，且文档无法展示枚举语义。
- **影响**：接口可读性差，容易出现非法订单类型。
- **修复建议**：使用 `Literal[1, 2, 3, 4, 5]` 或 `OrderType` 枚举，与 `common/types.py` 保持一致。
- **优先级**：P2

#### [P2] `BatchCheckinRequest.child_ids` 未限制最大长度
- **位置**：`backend/domain/admin/admin_schemas.py:325-329`
- **现状**：`child_ids: list[int] = Field(..., min_length=1)`，无 `max_length`。
- **问题**：一次性传入超大列表可能导致事务超长、内存占用高、数据库锁定时间延长。
- **影响**：存在性能/可用性风险，极端情况可造成请求超时或连接池耗尽。
- **修复建议**：增加 `max_length=100` 或 `200`，超出时分批处理。
- **优先级**：P2

#### [P3] `/admin/api/config/{key}` 使用 query 参数传递 value，不符合 PUT 语义
- **位置**：`backend/domain/admin/routers/admin_system_router.py:90-98`
- **现状**：`@router.put("/config/{key}") def set_config(key: str, value: str, ...)` 将待更新值放在 query string。
- **问题**：配置值可能较长或含特殊字符，query 参数有长度限制且需 URL 编码；不符合 RESTful 资源更新语义。
- **影响**：超长配置值无法保存，接口使用不直观。
- **修复建议**：改为 Body 参数，定义 `UpdateConfigRequest(value: str)`。
- **优先级**：P3

---

## 维度 3：业务逻辑审查

**维度结论：不通过**

核心流程（借阅、押金、预约、活动、测评、订单）的主干已实现，但存在多项关键业务规则缺失或实现偏差：多孩优惠逻辑错误、观察期/正式会员前置条件未校验、测验积分去重条件错误、阅读提交审核不触发晋级统计、丢书罚款未从押金记录扣减、活动取消/预约取消库存回退不完整。这些问题会导致财务计费错误、用户权益异常、库存不一致，必须修复后方可上线。

### 发现的问题

#### [P0] 多孩优惠逻辑与 PRD 不符，仅按同类型订单判断
- **位置**：`backend/domain/order/service.py:130-172`
- **现状**：`_apply_discount` 仅检查“该用户是否已有同类型（OBSERVATION/OFFICIAL_MEMBER/QUARTERLY/SEMI_ANNUAL）的已支付订单”，有则打 9 折。
- **问题**：PRD 1.3 明确“同一 user 下已有 1 个孩子是观察期或正式会员 → 第 2 个孩子起享 9 折”，即优惠应跨订单类型、按“孩子”维度判断。当前逻辑：
  - 若用户已有观察期孩子，再为第二个孩子购买正式会员时，不会打折（因为 OFFICIAL_MEMBER 类型无历史订单）；
  - 若用户已有正式会员孩子，再为第二个孩子购买观察期时，也不会打折。
- **影响**：财务计费错误，家长无法获得应享优惠，可能引发客诉；与 PRD 价格体系冲突。
- **修复建议**：按 PRD 语义重写：查询同一 user 下是否存在状态为 OBSERVATION/OFFICIAL 的 child，若存在且当前订单类型为会员类（OBSERVATION/OFFICIAL/QUARTERLY/SEMI_ANNUAL），则应用 `multi_child_discount`。
- **优先级**：P0

#### [P0] 订单创建未校验观察期/正式会员前置条件
- **位置**：`backend/domain/order/service.py:86-105`
- **现状**：
  - 观察期订单仅校验 `child.status == MemberStatus.TRIAL`；
  - 正式会员订单仅校验 `child.status in (OBSERVATION, OFFICIAL, EXPIRED)`。
- **问题**：PRD 1.2 要求观察期前置条件为“孩子已完成亲子课程并获得测评报告”；PRD 1.3 要求正式会员前置条件为“观察期评估结果为通过”。代码均未校验。
- **影响**：未达条件用户可绕过 funnel 直接购买后续产品，破坏商业模型与教学闭环；可能导致正式会员质量下降。
- **修复建议**：
  - 观察期：校验孩子存在已支付的 PARENT_COURSE 订单，且存在 AR 测评通过记录；
  - 正式会员：校验观察期订单已结束且生成观察期报告/评估通过（可配置是否强制）。
- **优先级**：P0

#### [P0] 测验积分去重条件错误：任意完成即视为已计分
- **位置**：`backend/domain/advancement/service.py:196-209`
- **现状**：去重逻辑为：若该 child+book 存在任意 `status==COMPLETED` 的 Quiz（无论是否通过、无论 score），则 `effective_word_count = 0`。
- **问题**：PRD 11.4 要求“同一 child+book 只计入一次 word_count”。但首次测验失败后再通过时，由于已存在失败的 COMPLETED 记录，导致通过后的积分也不计入；且未通过记录不应触发去重。此外，该判断处于评分后的同一事务中，高并发下可能出现重复计分（无唯一约束兜底）。
- **影响**：孩子通过测验后无法获得正确积分；排行榜/累计词数数据错误；高并发存在重复加分风险。
- **修复建议**：
  1. 去重条件改为“存在其他 status==COMPLETED 且 passed 为真的 Quiz”；
  2. 数据库增加 `UNIQUE(child_id, book_id, passed)` 或 `UNIQUE(child_id, book_id)` 并在 Quiz 表增加 `word_counted` 标记，用唯一约束兜底；
  3. 在 `submit_answers` 中使用 `with_for_update` 锁定相关 Quiz 行。
- **优先级**：P0

#### [P0] 阅读提交审核通过不增加“该级别已读完书数”
- **位置**：`backend/domain/advancement/service.py:492-503`
- **现状**：`review_submission` 仅更新 `ReadingSubmission.status` 和 `comment`，未调用 `increment_books_read` 或更新 `ChildLevel.books_read_at_level`。
- **问题**：PRD 11.2 明确“审核通过 → 提交状态变为 APPROVED → 该级别已读完书数 +1”。当前逻辑导致晋级条件中的 `books_read_at_level >= required_books` 无法满足（除非通过测验事件误打误撞触发 `increment_books_read`，但那是测验通过的事件，不是老师审核）。
- **影响**：孩子无法正常晋级，级别体系失效。
- **修复建议**：在 `review_submission` 中，当 `data.status == ReadingSubmission.STATUS_APPROVED` 时，调用 `increment_books_read(sub.child_id)` 并触发 `check_and_advance`。
- **优先级**：P0

#### [P1] 押金状态机缺少“已退款”终态，退款申请后状态停留在 REFUNDING
- **位置**：`backend/domain/deposit/service.py:76-118`、`backend/domain/deposit/models.py:38`
- **现状**：`refund_deposit` 将 `DepositRecord.status` 设为 `REFUNDING`（DepositStatus.REFUNDING=4），并同步设置 `child.deposit_status = REFUNDING`。PRD 状态机为 UNPAID → PAID → REFUNDED/DEDUCTED，代码注释也写“UNPAID → PAID → REFUNDED / DEDUCTED”。
- **问题**：没有后续逻辑在 WeChat 退款回调成功后把状态改为 REFUNDED；`DepositStatus` 枚举多出 REFUNDING 但未在 PRD 中定义；押金查询接口返回 REFUNDING=4，前端/后台可能无法识别。
- **影响**：押金状态不一致，退款完成后仍显示“退款中”；无法准确判断用户是否可重新缴纳押金。
- **修复建议**：
  1. 在微信退款回调或定时任务确认退款到账后，将 `DepositRecord.status` 与 `child.deposit_status` 更新为 `REFUNDED`；
  2. 在 `RefundApplication` 增加 `deposit_record_id` 关联，便于跟踪；
  3. 明确 PRD 状态机与代码枚举一致性。
- **优先级**：P1

#### [P1] 丢书罚款未从押金记录余额扣除
- **位置**：`backend/domain/deposit/service.py:147-197`
- **现状**：`mark_book_lost` 计算 `fine_amount = book_price * multiplier`，更新 `BorrowRecord.fine_amount` 与 `child.outstanding_fines`，但仅减少 `book.total_stock`，未更新 `DepositRecord` 的 `deduct_amount` 或扣减 `amount`。
- **问题**：PRD 6.2/7.3 明确“从押金中扣除罚款金额”。当前只是在孩子身上记一笔欠款，押金记录余额未动，造成 `DepositRecord.amount` 与 `child.outstanding_fines` 不一致。
- **影响**：财务对账困难；若用户随后申请退款，系统可能按原始押金全额退，而忘记抵扣丢书罚款。
- **修复建议**：在 `mark_book_lost` 中查找该孩子的 `PAID` 押金记录，将 `deduct_amount` 累加罚款额（或维护 `remaining_amount` 字段），并更新 `DepositRecord.status = DEDUCTED` 当扣除后余额为 0；同时确保 `refund_deposit` 校验时 outstanding_fines 包含丢书罚款。
- **优先级**：P1

#### [P1] 预约取书未绑定实体副本，BookCopy 状态不会变为已借出
- **位置**：`backend/domain/borrow/service.py:258-353`、`backend/events/borrow_handlers.py:14-21`
- **现状**：`borrow_from_reservation` 创建 `BorrowRecord` 时未设置 `book_copy_id`；事件处理器 `handle_book_borrowed_for_copy_status` 仅在 `event.book_copy_id` 非空时更新副本状态。
- **问题**：PRD 8.2 描述“到店取书 → 转为正式借阅”，线下场景应扫描/指定具体实体书副本。当前预约取书后，`BookCopy.status` 仍为 AVAILABLE，库存与副本状态不一致。
- **影响**：门店无法通过 BookCopy 状态追踪实体书；还书时 `BookReturnedEvent` 也无法恢复对应副本状态。
- **修复建议**：在 `fulfill_reservation` 时要求传入 `book_copy_id`（或由门店扫码选择副本），并写入 `BorrowRecord.book_copy_id`，再发布 `BookBorrowedEvent`。
- **优先级**：P1

#### [P1] 用户端取消预约未释放库存
- **位置**：`backend/domain/reservation/service.py:167-178`
- **现状**：`cancel_reservation` 将记录状态设为 3（Cancelled），调用 `reservation_repo.update`，然后 commit，未发布 `ReservationExpiredEvent` 或调用库存恢复逻辑。
- **问题**：PRD 未显式说明用户主动取消，但库存一致性要求取消后应释放锁定的库存。当前逻辑导致可用库存永久减少。
- **影响**：用户取消预约后该书仍显示无库存，影响借阅体验与库存准确性。
- **修复建议**：在 `cancel_reservation` 中，当原状态为 PENDING 时，发布 `ReservationExpiredEvent`（或新增 `ReservationCancelledEvent`）以触发 `BookService.increase_available_stock`。
- **优先级**：P1

#### [P1] 活动名额取消存在并发下溢风险
- **位置**：`backend/domain/activity/service.py:90-122`
- **现状**：`cancel_enrollment` 读取 activity 后，直接 `activity.current_participants = max(0, ... - 1)` 并 commit，未使用 SQL 原子更新或行锁。
- **问题**：两个并发取消可能导致计数被覆盖而小于 0，或报名/取消并发导致超卖。
- **影响**：活动名额计数不准确，可能出现“已满”但名额还有余，或“-1/30”的异常显示。
- **修复建议**：使用 `UPDATE activity SET current_participants = current_participants - 1 WHERE id = ? AND current_participants > 0` 的原子更新；并在报名时同样使用 `WHERE current_participants < max_participants` 原子递增。
- **优先级**：P1

#### [P1] 晋级条件默认要求 5 次测验通过，与 PRD 的“至少 1 次”不符
- **位置**：`backend/domain/advancement/service.py:260-264`
- **现状**：`check_and_advance` 从配置读取 `quiz_pass_count`（默认 5），要求 `current.quizzes_passed_at_level >= min_quiz_pass`。
- **问题**：PRD 11.5 明确“本级已通过至少 1 次测验（quizzes_passed_at_level >= 1）”。默认 5 次会让孩子永远无法晋级（因为 required_books 也是 5，而每本书只能测验一次）。
- **影响**：晋级体系无法运转，与孩子/家长预期严重不符。
- **修复建议**：将默认值改为 1；或改为读取 `level.required_books` 与 `level.required_quiz_pass_rate` 的组合逻辑（PRD 语义）。
- **优先级**：P1

#### [P1] 活动组织者取消后自动退款缺少执行链路
- **位置**：`backend/domain/activity/service.py:220-300`
- **现状**：组织者取消活动时，为收费活动报名创建 `RefundApplication(order_id=None, ...)`，但 `order_id=None` 导致后续无法关联原支付订单执行微信退款；也没有触发 `BackgroundTasks` 或定时任务处理。
- **问题**：PRD 2.3 要求“付费用户自动全额退款，无需用户申请”。当前仅写了一条退款申请记录，没有实际退款动作。
- **影响**：活动取消后用户收不到退款，引发客诉。
- **修复建议**：收费活动报名应关联到具体订单（ activity enrollment 增加 order_id 字段），取消时通过原订单发起微信退款；或在创建 `RefundApplication` 后异步执行 `_execute_wechat_refund_async`。
- **优先级**：P1

#### [P1] 借阅逾期罚款与 child.outstanding_fines 双写可能分叉
- **位置**：`backend/domain/borrow/service.py:148-184`、`backend/tasks/scheduler.py:777-853`
- **现状**：`return_book` 计算逾期罚款并写入 `BorrowRecord.fine_amount`，但不更新 `child.outstanding_fines`；定时任务 `mark_overdue_books` 遍历所有逾期记录后，按 child 汇总覆盖 `outstanding_fines`。
- **问题**：PRD 6.2/7.3 要求逾期罚款应实时计入未缴罚款。当前归还时孩子看不到待缴罚款，只有定时任务次日才汇总；若定时任务失败，数据长期不一致。
- **影响**：用户归还书籍时押金退款校验可能通过（outstanding_fines 为 0），但实际上存在逾期罚款。
- **修复建议**：在 `return_book` 中同步累加 `child.outstanding_fines`；定时任务改为对账/修复用途，而非唯一写入来源。
- **优先级**：P1

#### [P1] 正式会员续费折扣与多孩优惠未说明是否叠加
- **位置**：`backend/domain/order/service.py:144-171`
- **现状**：`_apply_discount` 先判断 EXPIRED 续费折扣，再判断多孩优惠，二者互斥。
- **问题**：PRD 附录 B 同时列出“多孩折扣 0.9”和“缓冲期续费 0.9”，但未说明是否叠加。当前实现只取其一，若业务需要叠加则计费错误。
- **影响**：计费策略与产品预期可能不一致。
- **修复建议**：产品侧明确规则；若可叠加，应顺序应用两个折扣；若互斥，应在订单响应中显式标记使用了哪种折扣。
- **优先级**：P1

#### [P2] 观察期报告自动生成未实现
- **位置**：`backend/domain/admin/routers/admin_reports_router.py:168-175`、`backend/tasks/scheduler.py:856-907`
- **现状**：管理端 `/admin/api/reports/observation/generate` 返回 stub `{success: False, message: "报告自动生成功能暂未实现"}`；定时任务 `check_observation_expiry` 调用 `report_svc.generate_due_reports()`，但未验证其完整性。
- **问题**：PRD 13 要求观察期到期后自动生成报告。当前管理端无法手动触发，且生成逻辑可能不完整。
- **影响**：观察期到期后家长无法查看报告，影响转化率。
- **修复建议**：移除 stub，实现 `ReportService.generate_due_reports` 的完整统计逻辑（阅读本数、词数、时长、测验次数、老师评语）。
- **优先级**：P2

#### [P2] 押金退款与借书操作存在跨事务竞态
- **位置**：`backend/domain/deposit/service.py:76-118`、`backend/domain/borrow/service.py:45-123`
- **现状**：`refund_deposit` 对 DepositRecord、BorrowRecord、Child 加行锁，但借书 `borrow_book` 仅更新 `Book.available_stock` 原子操作，未对 Child/BorrowRecord 加锁。两个事务并发时：退款事务检查无活跃借阅后，借书事务可能同时创建借阅记录。
- **问题**：虽然概率低，但退款批准后孩子仍有未还书，违反 PRD 7.2 退款条件。
- **影响**：资金与实物不一致，可能导致退款后无法追回图书。
- **修复建议**：在 `borrow_book` 中创建借阅记录前，对 `Child` 行加 `with_for_update()`，并检查 `deposit_status` 为 PAID；`refund_deposit` 已获得 Child 行锁，可阻塞并发借书。
- **优先级**：P2

#### [P2] 微信退款失败时回滚消息发送无审计
- **位置**：`backend/domain/refund/service.py:94-141`
- **现状**：`_execute_wechat_refund_async` 捕获异常后尝试更新订单状态并发送站内消息，但若这些操作也失败则静默忽略。
- **问题**：退款失败是资损事件，静默忽略会导致运营无法感知。
- **影响**：退款失败无告警、无操作日志，问题发现滞后。
- **修复建议**：所有退款失败必须写入 `operation_log` 并发送高优先级告警（企业微信/短信）；站内消息发送失败时至少保证日志记录。
- **优先级**：P2

---

## 维度 4：数据库与模型审查

**维度结论：有条件通过**

模型基类 `BaseModel` 统一了审计字段与软删除，45 张表结构基本完整，金额字段统一使用 `Numeric(10,2)`，符合财务规范。但存在多处关键索引缺失、唯一约束不足、软删除过滤不一致、`extend_existing=True` 滥用、库存/计数字段无数据库级一致性保障等问题，需在生产上线前补齐。

### 发现的问题

#### [P0] 关键业务表缺少防止并发冲突的唯一约束
- **位置**：
  - `backend/domain/borrow/models.py:26-61`：无 `UNIQUE(child_id, book_id, active_status)`
  - `backend/domain/advancement/models.py:118-145`（Quiz）：无 `UNIQUE(child_id, book_id, passed)` 或计数标记
  - `backend/domain/advancement/models.py:182-199`（ChildAchievement）：无 `UNIQUE(child_id, achievement_id)`
  - `backend/domain/advancement/models.py:72-95`（ReadingSubmission）：无 `UNIQUE(child_id, book_id)`
- **现状**：上述“同一 X 只能一条活跃/成功记录”的业务规则完全依赖应用层先查后插。
- **问题**：高并发下先查后插无法避免重复记录；例如同一 child+book 可能同时产生两条 BORROWING 记录、两次积分计数、两条 approved submission。
- **影响**：库存、积分、成就、晋级统计全部可能重复，数据无法修复。
- **修复建议**：
  - 增加部分唯一索引（含 `is_deleted` 过滤或软删除唯一策略），例如 `UNIQUE(child_id, book_id, status IN (0,2))` 在 MySQL 中可通过函数索引或应用层状态过滤实现；
  - 对 Quiz 增加 `UNIQUE(child_id, book_id, word_counted)` 并在 `word_counted=1` 时保证唯一；
  - 对 ReadingSubmission 增加 `UNIQUE(child_id, book_id, is_deleted)`（软删除后允许重新提交）。
- **优先级**：P0

#### [P0] 多处高频查询外键/过滤字段缺少索引
- **位置**：
  - `backend/domain/borrow/models.py:38-40`：`book_copy_id` 无索引（扫码还书按条码查 copy 后再按 copy_id 查 BorrowRecord）
  - `backend/domain/advancement/models.py:86`：`ReadingSubmission.book_id` 无索引
  - `backend/domain/advancement/models.py:131-135`：`Quiz.book_id`、`Quiz.submission_id` 无索引
  - `backend/domain/activity/models.py:59-63`：`ActivityEnrollments` 已有单列索引，但缺少 `(activity_id, status)` 联合索引
  - `backend/domain/order/models.py:35-55`：`Order` 已有 user_id/child_id 单列索引，但缺少 `(user_id, pay_status)`、`(child_id, type, pay_status)` 联合索引
- **现状**：查询使用 `.filter(...).first()`，依赖全表扫描或单列索引，随着数据增长性能下降。
- **影响**：借书、还书、测评、活动签到、订单查询等高频操作变慢；N+1 或全表扫描风险。
- **修复建议**：为上述外键及高频组合查询增加单列/联合索引；使用 Alembic 生成迁移脚本，并在 MySQL 中 `EXPLAIN` 验证。
- **优先级**：P0

#### [P1] `extend_existing=True` 在大多数模型中不必要且会掩盖冲突
- **位置**：`backend/domain/*/models.py` 中几乎所有模型均设置 `__table_args__ = {"extend_existing": True}`
- **现状**：每个模型仅在单一文件定义，不存在多文件定义同表的需求。
- **问题**：`extend_existing=True` 会让 SQLAlchemy 在表结构变化时不报错而静默覆盖，容易在模型与迁移脚本不一致时隐藏问题。
- **影响**：数据库模型与 Alembic 迁移可能 divergence，导致生产数据不一致。
- **修复建议**：移除所有非必要的 `extend_existing=True`；仅在确实存在多文件继承或动态扩展的表保留。
- **优先级**：P1

#### [P1] 软删除过滤不一致，部分查询未带 `is_deleted == 0`
- **位置**：
  - `backend/middleware/ownership.py:227` `GetOwnedOrder`：`db.query(Order).filter(Order.id == int(order_id)).first()` 未过滤软删除
  - `backend/middleware/ownership.py:253` `GetOwnedRefund`：未过滤软删除
  - `backend/domain/order/service.py:176-183` `handle_payment_callback`：按 order_no 查询未过滤软删除
  - `backend/domain/refund/service.py:30-34` `apply_refund`：`order_repo.get_by_id_or_raise` 会过滤，但后续未再检查订单是否已软删除
- **现状**：大部分查询通过 `BaseRepository` 自动过滤软删除，但部分直接 `db.query(Model)` 的地方遗漏。
- **问题**：已删除订单/退款仍能被支付回调命中或越权查看；逻辑删除数据被误操作。
- **影响**：数据一致性、安全性风险。
- **修复建议**：统一所有直接查询补充 `.filter(Model.is_deleted == 0)`；或封装通用查询工具，强制软删除过滤。
- **优先级**：P1

#### [P1] 库存字段缺乏数据库级一致性约束
- **位置**：`backend/domain/book/models.py:63-65`
- **现状**：`Book.total_stock`、`Book.available_stock` 为普通 Integer，无 CHECK 约束，也无触发器与 `BookCopy` 数量联动。
- **问题**：应用层并发或 Bug 可能导致 `available_stock < 0` 或 `available_stock > total_stock`；丢书后 `total_stock` 被减但 `BookCopy` 可能未同步标记为 SCRAPPED。
- **影响**：库存数据不可信，门店无法准确知道可借数量。
- **修复建议**：
  1. 增加数据库 CHECK 约束：`available_stock >= 0`、`available_stock <= total_stock`；
  2. 新增定时对账任务：每日对比 `Book.total_stock` 与 `BookCopy` 实际数量；
  3. 丢书时将对应 `BookCopy.status` 置为 SCRAPPED，而非仅修改 Book 表的计数。
- **优先级**：P1

#### [P1] `Child.outstanding_fines` 是缓存/聚合字段，无重建机制
- **位置**：`backend/domain/child/models.py:67`、`backend/tasks/scheduler.py:830-841`
- **现状**：`outstanding_fines` 由定时任务汇总 BorrowRecord 后覆盖写入，但丢书罚款在 `mark_book_lost` 中实时累加，来源混合。
- **问题**：字段含义不唯一，且没有重建/对账机制；若某条罚款记录被软删除或调整，`outstanding_fines` 不会自动修正。
- **影响**：押金退款校验可能基于错误罚款余额。
- **修复建议**：将 `outstanding_fines` 改为 `@property` 或视图查询（推荐），或增加 hourly 对账任务重新汇总 `BorrowRecord.fine_amount` 与 `DepositRecord.deduct_amount`。
- **优先级**：P1

#### [P2] `Child.current_level_id` 冗余字段与 ChildLevel.is_current 可能不一致
- **位置**：`backend/domain/child/models.py:68-70`、`backend/domain/advancement/models.py:52-70`
- **现状**：`Child` 表有 `current_level_id` 冗余，晋级时 AdvancementService 只更新 `ChildLevel` 的 `is_current`，未同步 `Child.current_level_id`。
- **问题**：两个来源的“当前级别”可能不一致，查询时用哪个取决于代码路径。
- **影响**：排行榜、名片、报告等依赖当前级别的功能可能显示错误级别。
- **修复建议**：要么在晋级事务中同步更新 `Child.current_level_id`，要么移除冗余字段，统一通过 `ChildLevel.is_current=True` 查询。
- **优先级**：P2

#### [P2] 状态字段使用裸整数，缺少数据库 CHECK/ENUM 约束
- **位置**：`backend/domain/borrow/models.py:46`、`backend/domain/deposit/models.py:38`、`backend/domain/order/models.py:50` 等
- **现状**：状态字段为 `SmallInteger` 或 `Integer`，无数据库级枚举约束。
- **问题**：应用层 Bug 或手工改库时可写入非法状态值。
- **影响**：数据完整性受损，异常状态可能导致业务流程错误。
- **修复建议**：使用 MySQL ENUM 类型，或增加 CHECK 约束（如 `status IN (0,1,2,3)`）；在模型层继续保留 IntEnum。
- **优先级**：P2

#### [P2] `ReadingSession.duration_seconds` 等时间字段未建索引，定时任务范围查询慢
- **位置**：`backend/domain/reading/models.py`（需确认，但 scheduler.py 大量按 `create_time/start_time` 过滤）
- **现状**：scheduler 中 `generate_monthly_reports`、`get_reading_stats` 等均按时间范围全表扫描 ReadingSession。
- **问题**：随着阅读会话数据增长，月度统计/周报生成会越来越慢。
- **影响**：定时任务执行时间延长，可能阻塞后续任务。
- **修复建议**：为 `ReadingSession.create_time`、`BorrowRecord.create_time`、`Order.create_time` 等增加索引；大表统计可考虑按日期分区或预聚合日报表。
- **优先级**：P2

#### [P3] 部分文本字段使用 `String(255)` 可能不足
- **位置**：`backend/domain/admin/models.py:71`、`backend/domain/book/models.py:69` 等
- **现状**：`SystemConfig.config_value`、`Book.audio_timeline` 使用 `String(255)` 或 `Text`。
- **问题**：`config_value` 若存放 JSON 列表（如 `due_remind_days`）255 字符可能不足；`audio_timeline` 已用 Text 没问题。
- **影响**：长配置值无法保存。
- **修复建议**：`SystemConfig.config_value` 改为 `Text`；或拆分 JSON 类型单独表。
- **优先级**：P3

---

## 维度 7：性能审查

**维度结论：有条件通过**

项目已采用批量查询避免大部分 N+1，阅读统计使用 SQL 聚合，分页统一格式。但仍有活动报名列表等 N+1 查询、全表 OFFSET 分页、定时任务范围查询缺少索引、ConfigService 进程内缓存无法跨 worker 共享、连接池配置未针对异步优化等问题，需在数据量增长前处理。

### 发现的问题

#### [P1] 活动报名列表存在 N+1 查询
- **位置**：`backend/domain/activity/service.py:147-177`
- **现状**：`get_enrollments` 先查询所有 `ActivityEnrollment`，再循环 `self.db.query(Child).filter(Child.id == e.child_id).first()`。
- **问题**：每个报名记录触发一次 Child 查询，活动 100 人即 100 次查询。
- **影响**：活动详情页加载慢，并发时数据库压力大。
- **修复建议**：批量查询 Child：`child_ids = list(set(e.child_id for e in enrollments))`，一次性 `filter(Child.id.in_(child_ids))` 构建 dict 映射。
- **优先级**：P1

#### [P1] 所有分页使用 OFFSET，大表深分页性能差
- **位置**：`backend/common/base_repo.py:86-93`、`backend/domain/admin/routers/*.py` 各列表接口
- **现状**：分页实现为 `OFFSET (page-1)*page_size LIMIT page_size`，并配合 `COUNT(*)` 计算 total。
- **问题**：当表数据量达到数十万行时，深分页 OFFSET 会扫描大量行；COUNT(*) 也会越来越慢。
- **影响**：管理后台订单/用户/阅读记录翻页变慢，严重时导致数据库 CPU 飙升。
- **修复建议**：
  - 管理后台列表保留 OFFSET 但设置最大页码/限制导出时走后台任务；
  - 对关键业务流（如消息 feed、活动列表）引入游标分页（cursor / keyset pagination）按 `id` 或 `create_time` 排序；
  - COUNT 使用近似值或缓存（如 Redis 缓存 total 5 分钟）。
- **优先级**：P1

#### [P1] `check_due_date_reminders` 循环内重复全表扫描
- **位置**：`backend/tasks/scheduler.py:672-731`
- **现状**：对 `[5,3,1,0]` 每一天，先 `JOIN` 查询所有 BORROWING 记录，再内存中按 `due_date.date()` 过滤。
- **问题**：JOIN 结果被重复加载 4 次；且未对 `due_date` 加索引时全表扫描 BorrowRecord。
- **影响**：借阅记录增多后，每日凌晨 1 点的任务变慢，可能超时。
- **修复建议**：
  1. 单次查询 `due_date BETWEEN today + min(days) AND today + max(days)`；
  2. 按 `due_date.date()` 内存分组后批量写入消息；
  3. 为 `BorrowRecord.due_date` 添加索引。
- **优先级**：P1

#### [P1] `ConfigService` 进程内缓存无法在多 worker 间共享
- **位置**：`backend/common/config_service.py:24-56`
- **现状**：使用类变量 `_cache: dict` 做 5 分钟 TTL 缓存，仅在当前进程生效。
- **问题**：生产环境通常运行多个 uvicorn worker，配置变更后只有部分 worker 缓存失效，导致同一配置在不同请求中看到不同值。
- **影响**：价格、借书上限、活动取消时间等配置在 worker 间不一致，可能引发计费/规则混乱。
- **修复建议**：引入 Redis 作为配置缓存层，或在配置更新时通过消息广播让所有 worker 失效；简单方案是将 TTL 缩短至 30 秒并文档化风险。
- **优先级**：P1

#### [P2] `generate_monthly_reports` 遍历全量会员孩子逐一生成报告
- **位置**：`backend/tasks/scheduler.py:449-471`
- **现状**：每月 1 日查询所有 OBSERVATION/OFFICIAL 状态的孩子，逐个生成月报，任一孩子失败只记录日志不影响后续。
- **问题**：随着用户规模增长，串行生成数千份报告耗时极长；任务在单线程 APScheduler 中运行，可能跨时段仍未完成。
- **影响**：月报生成延迟；任务执行期间占用大量数据库连接。
- **修复建议**：
  1. 按 child_id 分批并行生成（限制并发数）；
  2. 或使用消息队列/后台任务拆分；
  3. 对无阅读记录的孩子跳过生成，减少无效计算。
- **优先级**：P2

#### [P2] `get_upgrade_options` 未使用索引优化
- **位置**：`backend/domain/order/service.py:226-292`
- **现状**：按 `child_id`、`type.in_([...])`、`pay_status=PAID` 查询订单，然后 `order_by(pay_time.desc()).first()`。
- **问题**：缺少 `(child_id, type, pay_status, pay_time)` 联合索引时，需要扫描该 child 的所有订单再排序。
- **影响**：升级选项查询随订单量增长变慢。
- **修复建议**：增加上述联合索引；或在 `Child` 表中冗余 `last_order_id`/`last_membership_order_id` 字段。
- **优先级**：P2

#### [P2] `BookRepository.search` 等搜索未查看实现，存在模糊查询索引失效风险
- **位置**：`backend/domain/book/repository.py`（未直接阅读，但 `admin_books_router.py:25` 调用 `service.search_books`）
- **现状**：若使用 `Book.title.contains(keyword)` 且 title 字段为普通索引，MySQL 无法使用索引（前缀模糊）或只能全表扫描。
- **问题**：图书搜索、孩子搜索等管理后台功能在书/用户量大时变慢。
- **影响**：管理端搜索体验差。
- **修复建议**：引入 MySQL 全文索引（FULLTEXT）或专用搜索（如 Meilisearch/Elasticsearch）；短期可限制关键词最小长度并增加 `LIMIT`。
- **优先级**：P2

#### [P2] 同步 SQLAlchemy Session 与 FastAPI 异步混用
- **位置**：`backend/database.py:35-42`、`backend/domain/*/router.py` 大量 `async def` 与 `def` 混合
- **现状**：数据库引擎为同步 `create_engine`，依赖注入 `get_db` 使用同步 Session。但部分 router 使用 `async def`（如 `order/router.py:60 payment_callback`），直接调用同步 Service/DB 操作。
- **问题**：在 `async def` 中调用同步 SQLAlchemy 会阻塞事件循环，降低并发能力，极端情况导致其他请求延迟。
- **影响**：支付回调等关键路径在高并发下响应变慢。
- **修复建议**：统一使用 `def` 路由让 FastAPI 自动放入线程池；或迁移到 SQLAlchemy async（需要较大改造，当前阶段推荐前者）。
- **优先级**：P2

#### [P3] 健康检查端点未包含数据库/Redis 连通性探测
- **位置**：`backend/main.py:229-232`
- **现状**：`/health` 仅返回固定 JSON，未检查数据库连接、Redis、微信证书等依赖。
- **问题**：负载均衡器可能将请求路由到“活着但依赖故障”的实例。
- **影响**：故障发现延迟，影响高可用。
- **修复建议**：健康检查增加轻量级数据库 `SELECT 1` 与 Redis ping；微信证书状态可设为可选探测。
- **优先级**：P3

#### [P3] 定时任务缺少运行监控与死信补偿
- **位置**：`backend/tasks/scheduler.py`
- **现状**：各定时任务仅记录日志，无集中监控/告警，也没有记录失败重试状态。
- **问题**：任务失败时若日志被清理则无法追溯；部分任务（如预约过期、逾期检测）若长时间失败会造成业务损失。
- **影响**：运维排查困难，关键业务任务中断无感知。
- **修复建议**：
  1. 为每个任务增加 `@scheduler.scheduled_job` 级别的异常捕获与指标（成功/失败计数）；
  2. 关键任务失败时发送告警；
  3. 对事件处理器失败写入的 `DeadLetterEvent` 增加监控与补偿接口。
- **优先级**：P3

---

## 总体结论

- **整体评级**：C（及格线以下，需重大修复后方可上线）
- **关键风险项**：
  1. 多孩优惠逻辑错误（P0）—— 直接资损与客诉；
  2. 观察期/正式会员前置条件未校验（P0）—— 商业 funnel 失效；
  3. 测验积分去重条件错误（P0）—— 核心学习数据错误；
  4. 阅读提交审核不触发晋级统计（P0）—— 晋级体系不可用；
  5. 关键表缺少唯一约束（P0）—— 高并发数据污染；
  6. `/admin/api/oplogs` 未认证（P0）—— 安全漏洞。
- **建议的修复优先级**：
  - **第一优先级（1-2 周内）**：P0 全部修复，P1 中的押金状态机、丢书扣款、预约取书绑定副本、用户端取消预约释放库存；
  - **第二优先级（3-4 周内）**：P1 中的索引/唯一约束、软删除过滤、库存约束、金额 Schema；
  - **第三优先级（上线后 1 个月内）**：P2 性能优化、P3 可观测性增强。
- **下一步行动项**：
  1. 召开产品-技术对齐会，确认多孩优惠、续费折扣、观察期前置条件等 PRD 细节；
  2. 制定 Alembic 迁移计划，补齐索引与唯一约束；
  3. 为 P0/P1 问题编写回归测试，补充并发场景测试；
  4. 完成修复后重新进行维度 2/3/4/7 复审。
