# MegaWords（librio）企业级审查报告 — 维度 1 & 12

## 审查概要

- **审查日期**：2026-07-03
- **审查维度**：维度 1（需求覆盖度）、维度 12（PRD 与 Feature 文件审查）
- **审查范围**：`PRD/MegaWords_V3.5需求文档.md`、`features/`、`backend/domain/` 22 个业务模块
- **发现问题总数**：24 项
  - 致命（P0）：5 项
  - 严重（P1）：9 项
  - 一般（P2）：8 项
  - 建议（P3）：2 项

> 注：本报告聚焦 PRD 与代码实现、BDD 场景之间的覆盖与一致性，不重复 `AUDIT_REPORT.md` 中已记录的通用 CRUD/Schema/接口修复项。

---

## 维度 1：需求覆盖度审查

### 1.1 PRD 需求覆盖总表

| PRD 章节 | 需求点 | 实现模块 | 状态 | 差异说明 |
|----------|--------|---------|------|----------|
| 1.1 亲子课程报名 | 选择场馆/时间、填写信息、支付 99 元、生成订单与电子凭证 | `order`, `parent_course_time`, `child` | ⚠️ 部分实现 | 支付与订单已覆盖，但课程完成状态未作为观察期报名前置条件校验 |
| 1.2 观察期报名 | 完成亲子课+测评报告、支付 500 元、30 天有效期、分配老师、到期提醒 | `order`, `child` | ⚠️ 部分实现 | 未校验亲子课完成与测评报告；支付后未分配 teacher_id |
| 1.3 正式会员报名 | 观察期评估通过、多孩优惠、365 天有效期 | `order`, `child` | ⚠️ 部分实现 | 未校验观察期评估通过；多孩优惠基于同类型订单而非孩子状态 |
| 1.3a 季度/半年会员 | 90/180 天会员、status=2、动态价格、续费折扣 | `order`, `child` | ✅ 已实现 | OrderType 与价格配置已覆盖 |
| 1.3b 会员升级 | 季度→半年→年费、差价计算、升级订单 | `order` | ✅ 已实现 | API 与差价计算已覆盖 |
| 2.1 活动浏览 | 即将举办/往期回顾、活动列表 | `activity` | ✅ 已实现 | 列表与状态过滤已覆盖 |
| 2.2 活动报名 | 免费自动通过、收费待支付、名额控制、电子门票 | `activity` | ⚠️ 部分实现 | 并发名额控制已实现；收费活动支付回调未与活动报名强关联 |
| 2.3 活动取消报名 | 24 小时规则、免费直接取消、收费创建退款申请 | `activity` | ❌ 未实现 | 收费活动取消后未创建退款申请 |
| 2.4 活动签到 | 二维码签到、状态变为已签到 | `activity` | ✅ 已实现 | 签到状态与已签到标识已覆盖 |
| 2.5 活动提醒 | 开始前 3 天提醒、微信订阅消息 | `tasks/scheduler` | ⚠️ 部分实现 | 定时提醒已实现，但消息优先级为 0（低），PRD 要求“中” |
| 3.1 权益转让 | 源孩子观察期/正式会员、无未还书、目标非正式会员、管理员审核 | `child` | ⚠️ 部分实现 | 未校验目标孩子是否已是观察期/正式会员 |
| 3.2 失败场景 | 未还书/目标已是正式会员/状态不允许 | `child` | ⚠️ 部分实现 | “目标已是正式会员”未校验 |
| 4.1 图书浏览 | AR/主题/年龄筛选、详情页、库存状态 | `book` | ✅ 已实现 | 搜索与筛选已覆盖 |
| 4.2 音频伴读 | 播放/暂停/倍速、锁屏、进度条、中断恢复、逾期锁定 | `reading`, `audio` | ⚠️ 部分实现 | 播放控制为前端；后端未强制逾期锁定音频 |
| 4.3 听读中查词 | 点击单词查词、弹窗显示、不中断播放 | `vocabulary`, `dictionary` | ⚠️ 部分实现 | 本地查词已覆盖，缺少 Free Dictionary API 兜底 |
| 4.4 阅读时长与打卡 | 10 分钟自动打卡、读完图书打卡、每天最多 1 次 | `reading` | ✅ 已实现 | 打卡逻辑已覆盖，可配置最低分钟数与最低词数 |
| 5.1-5.4 书架 | 想读清单、无限量、去重、移除、浏览进度 | `bookshelf` | ⚠️ 部分实现 | 收藏夹（Favorites）与想读清单并存；容量限制可配置 |
| 5.5 从书架预约借书 | 选择书籍、押金+库存校验、创建预约 | `reservation`, `bookshelf` | ❌ 未实现 | 书架无直接发起预约的接口 |
| 6.1 扫码借书 | 已有条码/首次扫码/同 ISBN 新条码、权限校验 | `borrow`, `book` | ⚠️ 部分实现 | 未校验 BookCopy 是否可用；借书允许 REFUNDING 押金 |
| 6.2 还书 | 正常/逾期/丢失、罚款计算、库存释放 | `borrow`, `deposit`, `book` | ✅ 已实现 | 逾期罚款与丢书罚款已覆盖 |
| 6.3 逾期检测 | 每日凌晨 2 点标记 OVERDUE、锁定音频 | `tasks/scheduler`, `borrow` | ⚠️ 部分实现 | 逾期标记与罚款已覆盖，但音频锁定未实现 |
| 6.4 到期提醒 | 5/3/1/当天提醒 | `tasks/scheduler` | ✅ 已实现 | 可配置提醒天数已覆盖 |
| 7.1 缴纳押金 | 微信支付、1200 元、状态 PAID | `deposit`, `child` | ✅ 已实现 | 金额可配置 |
| 7.2 押金退款 | 无活跃借阅+无未缴罚款、退款申请、管理员审核 | `deposit` | ✅ 已实现 | 校验条件已覆盖 |
| 7.3 押金扣除 | 丢书/逾期罚款扣除、更新 outstanding_fines | `deposit`, `borrow`, `child` | ✅ 已实现 | 罚款计算已覆盖 |
| 7.4 押金查询 | 状态/余额/未结罚款 | `deposit` | ✅ 已实现 | 查询已覆盖 |
| 8.1 预约流程 | 已缴纳押金+库存>0、72 小时过期 | `reservation` | ❌ 未实现 | 未校验押金状态；预约取消后未释放库存 |
| 8.2 预约取书 | 扫码匹配预约、创建借阅、状态 FULFILLED | `reservation`, `borrow` | ✅ 已实现 | 事件驱动创建借阅已覆盖 |
| 8.3 预约过期 | 每 30 分钟检查、释放库存 | `tasks/scheduler`, `reservation` | ⚠️ 部分实现 | 过期检查已覆盖；取消预约未释放库存 |
| 8.4 预约查询 | 有效预约列表、剩余取书时间 | `reservation` | ✅ 已实现 | 查询已覆盖 |
| 9.1 查词 | 本地 ECDICT 优先、Free Dictionary API 兜底、未收录提示 | `vocabulary`, `dictionary` | ❌ 未实现 | 仅本地查词，无兜底 API |
| 9.2 生词本 | 加入/去重/列表/复习/掌握/统计/高亮 | `vocabulary` | ✅ 已实现 | 生词本与状态管理已覆盖 |
| 10.1 阅读打卡 | 自动打卡、打卡日历、连续天数 | `reading`, `child` | ✅ 已实现 | 事件驱动更新连续天数 |
| 10.2 阅读统计 | 今日/累计统计、趋势图表 | `report` | ⚠️ 部分实现 | 语音朗读次数未统计（固定为 0） |
| 10.3 学习报告 | 周报/月报、阅读建议、分享图片 | `report` | ⚠️ 部分实现 | 周报/月报已生成，但缺少“日均阅读分钟”等字段 |
| 10.4 家长查看 | 阅读时长/词数/图书数、最近记录、报告列表 | `report` | ✅ 已实现 | 聚合查询已覆盖 |
| 11.1 级别管理 | A-Z 26 级、徽章、默认 5 本、通过率 80% | `advancement` | ✅ 已实现 | 级别 CRUD 已覆盖 |
| 11.2 阅读提交 | 读完自动创建提交、老师审核、通过/打回 | `advancement`, `reading` | ❌ 未实现 | 读完未自动创建 ReadingSubmission |
| 11.3 测验 | 题库≥5 题、老师出卷、答题评分 | `advancement` | ✅ 已实现 | 题库与测验已覆盖 |
| 11.4 测验结果 | 通过≥80%、借阅记录 PASSED、可重考、词数去重 | `advancement`, `borrow` | ⚠️ 部分实现 | 通过状态与去重已覆盖；但 QuizPassed 事件错误地增加 books_read |
| 11.5 晋级 | 本级读完书数+至少 1 次测验通过、自动晋级 | `advancement` | ⚠️ 部分实现 | 晋级检测使用全局 quiz_pass_count=5，与 PRD “至少 1 次”不符 |
| 11.6 成就系统 | 晋级/里程碑/连续打卡/满分、排行榜 | `advancement` | ✅ 已实现 | 成就 CRUD 与排行榜已覆盖 |
| 12.1 证书生成 | 晋级自动生成、证书编号、PDF 导出 | `certificate` | ✅ 已实现 | 证书生成已覆盖 |
| 12.2 证书查询 | 列表、详情、空列表 | `certificate` | ✅ 已实现 | 查询已覆盖 |
| 13.1 报告生成 | 观察期满 30 天、自动生成、未生成过 | `report`, `tasks/scheduler` | ✅ 已实现 | 观察期到期检查与报告生成已覆盖 |
| 13.2 报告内容 | 阅读本数/词数、测验、老师评语、日均阅读分钟 | `report` | ⚠️ 部分实现 | 缺少“日均阅读分钟”字段 |
| 13.3 报告查询 | 家长查看详情、空结果 | `report` | ✅ 已实现 | 查询已覆盖 |
| 14.1 名片生成 | 姓名、阅读数据、级别、成就、分享 | `profile` | ✅ 已实现 | 名片聚合已覆盖 |
| 15.1 退款规则 | 亲子课/观察期/正式会员差异化退款、按实付金额 | `refund`, `order` | ⚠️ 部分实现 | 观察期/正式会员已覆盖；亲子课未按课程开始时间区分 |
| 15.2 退款审核 | 通过/拒绝、通知 | `refund` | ✅ 已实现 | 审核流程已覆盖 |
| 15.3 会员到期提醒 | 30/15/7/3/2/1/当天提醒 | `tasks/scheduler` | ✅ 已实现 | 可配置提醒天数已覆盖 |
| 16.1 语音录制 | 录制、保存云端、回放 | `reading` | ✅ 已实现 | 录音保存与列表已覆盖 |
| 16.2 朗读记录 | 列表、时长、日期 | `reading` | ✅ 已实现 | 查询已覆盖 |
| 16.3 朗读与打卡联动 | 朗读完成自动打卡 | `reading` | ❌ 未实现 | save_recording 未触发打卡 |
| 16.4 语音评测（后续版本） | 发音评分、改进建议 | `reading` | 🔄 实现与需求不符 | 模型字段已存在，但 PRD 标注为规划中；当前无实际评测能力 |
| 附录 A 状态机 | 体验→观察→正式→过期→正式；已退出不可逆 | `child`, `events/order_handlers` | ⚠️ 部分实现 | 正式会员到期后未立即转 EXPIRED，依赖 15 天缓冲期调度 |
| 附录 B 价格体系 | 亲子课/观察期/年费/多孩折扣/缓冲期折扣/押金/罚款 | `order`, `deposit`, `borrow` | ✅ 已实现 | 价格与罚款计算已覆盖 |
| 附录 C API 端点索引 | ~93 个端点 | 22 个 domain | ✅ 已实现 | 端点数量与模块分布基本一致 |

### 1.2 发现的问题

#### [P0] 阅读提交（ReadingSubmission）不会自动创建
- **位置**：`backend/domain/reading/service.py:104-109`
- **现状**：`save_progress` 在 `current_page >= total_pages` 时仅设置 `ReadingProgress.is_finished=1` 并记录 `finish_time`，没有创建 `ReadingSubmission`。
- **问题**：PRD 11.2 明确要求“孩子完成听读（读完最后一页）→ 自动创建阅读提交记录（ReadingSubmission），状态为待审核”。缺少该记录，老师审核流程与观察期报告的“阅读本数”统计失去来源。
- **影响**：晋级体系中的“已读完书数”和观察期报告数据不完整，老师无法收到待审核通知。
- **建议**：在 `save_progress` 检测到读完时，自动创建 `ReadingSubmission(child_id, book_id, status=PENDING)`。
- **优先级**：P0

#### [P0] 测验通过事件错误地增加“已读书数”
- **位置**：`backend/events/quiz_handlers.py:11-18`
- **现状**：`handle_quiz_passed_for_advancement` 同时调用 `increment_quizzes_passed` 和 `increment_books_read`。
- **问题**：PRD 11.4/11.5 规定“已读书数”来自老师审核通过的阅读提交，而“测验通过数”才来自测验。当前实现导致孩子仅通过测验即可增加已读书数，破坏晋级条件。
- **影响**：孩子未真正读完书即可满足晋级条件，业务规则失效。
- **建议**：移除 `increment_books_read` 调用；仅在 `ReadingSubmission` 审核通过时增加 `books_read_at_level`。
- **优先级**：P0

#### [P0] 观察期/正式会员报名前置条件未校验
- **位置**：`backend/domain/order/service.py:88-105`
- **现状**：观察期仅校验 `child.status == TRIAL`；正式会员仅校验 `child.status in (OBSERVATION, OFFICIAL, EXPIRED)`。
- **问题**：PRD 1.2 要求“孩子已完成亲子课程并获得测评报告”；PRD 1.3 要求“观察期评估结果为通过”。当前实现只校验当前状态，未校验评估结果。
- **影响**：可能跳过必要评估环节，导致不满足条件的孩子进入下一阶段。
- **建议**：观察期报名前检查 `Assessment`（亲子课测评）完成；正式会员报名前检查 `ObservationEvaluation` 或观察期报告状态为通过。
- **优先级**：P0

#### [P0] 权益转让目标孩子状态校验不足
- **位置**：`backend/domain/child/service.py:112-125`
- **现状**：`transfer_benefit` 仅拒绝 `target.status == EXITED`，未拒绝已是观察期/正式会员的孩子。
- **问题**：PRD 3.1 明确“目标孩子不能已经是正式会员（否则无意义）”。当前目标孩子是 OBSERVATION 或 OFFICIAL 时仍可接收转让，会覆盖其现有权益。
- **影响**：破坏目标孩子的会员状态与有效期，造成数据不一致。
- **建议**：拒绝 `target.status in (OBSERVATION, OFFICIAL, EXPIRED)` 的转让请求（TRIAL 除外）。
- **优先级**：P0

#### [P0] 亲子课退款规则未实现
- **位置**：`backend/domain/refund/service.py:29-68`
- **现状**：`apply_refund` 对所有已支付订单都使用 `_calculate(order, used_days)` 计算退款，未区分订单类型。
- **问题**：PRD 15.1 规定“亲子课课程开始前全额退款 99 元；课程开始后不可退款”。当前实现允许课程开始后的亲子课退款。
- **影响**：财务损失，违反退款业务规则。
- **建议**：对 `OrderType.PARENT_COURSE` 检查课程开始时间（`ParentCourseTime`），已开始则拒绝退款。
- **优先级**：P0

#### [P1] 预约借书缺少押金校验
- **位置**：`backend/domain/reservation/service.py:46-97`
- **现状**：`create_reservation` 仅检查 `offline_available` 和 `available_stock`，未检查 `child.deposit_status`。
- **问题**：PRD 8.1 明确前置条件“已缴纳押金 + 库存 > 0”。
- **影响**：未缴纳押金的孩子可成功预约，到店取书时才发现无法借阅，影响用户体验。
- **建议**：在创建预约前增加 `child.deposit_status == DepositStatus.PAID` 校验。
- **优先级**：P1

#### [P1] 收费活动取消后未自动创建退款申请
- **位置**：`backend/domain/activity/service.py:90-122`
- **现状**：`cancel_enrollment` 只更新报名状态为 CANCELLED 并释放名额，未处理付费活动退款。
- **问题**：PRD 2.3 规定“收费活动取消：取消成功后自动申请全额退款，退款需管理员审核”。
- **影响**：用户已付款但无法申请退款，资金流与业务规则不一致。
- **建议**：当 `activity.is_free == False` 时，取消报名后创建 `RefundApplication`（关联活动订单或记录活动退款）。
- **优先级**：P1

#### [P1] 查词功能未实现 Free Dictionary API 兜底
- **位置**：`backend/domain/vocabulary/service.py:23-36`
- **现状**：`lookup_word` 仅查询本地 `dictionary_word` 表，未命中时返回 `None`。
- **问题**：PRD 9.1 明确“本地 ECDICT 优先；本地未命中 → 调用 Free Dictionary API 兜底；两个来源都未收录 → 显示‘单词未收录，已记录，将尽快补充’”。
- **影响**：大量本地未收录的常见单词无法查询，影响阅读体验。
- **建议**：实现 Free Dictionary API 调用；未命中时记录到待补充词表并返回友好提示。
- **优先级**：P1

#### [P1] 观察期支付后未自动分配指导老师
- **位置**：`backend/events/order_handlers.py:66-78`
- **现状**：处理 `OBSERVATION` 订单时只更新状态、会员开始/结束时间，未设置 `child.teacher_id`。
- **问题**：PRD 1.2 要求“自动分配一对一指导老师（teacher_id）”。
- **影响**：老师无法关联到观察期孩子，后续指导记录与待审核通知无法触达。
- **建议**：根据 `child.venue_id` 或轮询策略自动分配一名老师，写入 `teacher_id`。
- **优先级**：P1

#### [P1] 正式会员到期后未立即转为 EXPIRED
- **位置**：`backend/tasks/scheduler.py:225-267`
- **现状**：`check_grace_period_shutdown` 在 `member_expire_time < now - 15 天` 时才将 OFFICIAL 转为 EXPIRED。
- **问题**：PRD 附录 A 状态机规定“观察期到期/会员到期后自动转为 EXPIRED(3)”；缓冲期仅用于续费折扣。
- **影响**：到期后 15 天内会员状态仍显示 OFFICIAL，影响续费折扣判断与权限控制。
- **建议**：新增定时任务，在到期当天将 OFFICIAL 转为 EXPIRED；缓冲期仅作为折扣计算依据。
- **优先级**：P1

#### [P1] 借阅允许 REFUNDING 状态押金
- **位置**：`backend/domain/borrow/service.py:58-59`
- **现状**：借书校验 `child.deposit_status in (PAID, REFUNDING)`。
- **问题**：PRD 6.1/7.1 要求“必须已缴纳押金（PAID）”。REFUNDING 表示退款流程中，不应允许新借阅。
- **影响**：押金已退还过程中仍可借书，存在资损风险。
- **建议**：仅允许 `DepositStatus.PAID`。
- **优先级**：P1

#### [P1] 借书时未校验 BookCopy 状态
- **位置**：`backend/domain/borrow/service.py:195-257`
- **现状**：`scan_and_borrow` 找到条码对应 `BookCopy` 后直接创建借阅，未检查 `copy.status`。
- **问题**：PRD 6.1 要求 BookCopy 状态正确流转（AVAILABLE → BORROWED）。当前可能借阅已借出、损坏或丢失的副本。
- **影响**：库存状态混乱，可能导致同一副本被重复借阅。
- **建议**：在 `scan_and_borrow` 和 `borrow_book` 中校验 `BookCopy.status == AVAILABLE`。
- **优先级**：P1

#### [P1] 预约取消后未释放库存
- **位置**：`backend/domain/reservation/service.py:167-178`
- **现状**：`cancel_reservation` 仅将状态设为 3（CANCELLED），未调用库存释放逻辑，也未发布 `ReservationExpiredEvent`。
- **问题**：与预约过期不同，主动取消的预约不会恢复 `available_stock`。
- **影响**：库存被永久锁定，导致可借数量减少。
- **建议**：取消预约时调用 `expire_reservation` 或发布 `ReservationExpiredEvent`，释放库存。
- **优先级**：P1

#### [P1] 逾期后音频伴读锁定未实现
- **位置**：`backend/events/borrow_handlers.py:69-74`，`backend/domain/reading/service.py:120-160`
- **现状**：`BookOverdueEvent` 处理器仅记录日志；`start_session` 不检查孩子是否有逾期借阅。
- **问题**：PRD 4.2 明确要求“逾期锁定：借阅超期后音频伴读功能锁死”。
- **影响**：逾期惩罚机制失效，逾期孩子仍可继续听读。
- **建议**：在 `start_session` 或音频播放接口中检查是否存在 `status == OVERDUE` 的 `BorrowRecord`，存在则拒绝。
- **优先级**：P1

#### [P1] 学习报告未统计语音朗读次数
- **位置**：`backend/domain/report/service.py:376`，`495`
- **现状**：`get_summary` 与 `generate_weekly_report` 中 `voice_practices` 固定为 0，并注释“VoiceRecording not yet in domain layer”。实际上 `VoiceRecording` 已在 `reading/models.py` 中定义。
- **问题**：PRD 10.2/10.3 要求累计与周报显示“语音朗读次数”。
- **影响**：学习报告与周报数据不完整。
- **建议**：查询 `VoiceRecording` 表，按 `child_id` 统计朗读次数。
- **优先级**：P1

#### [P2] 多孩优惠基于同类型订单而非孩子状态
- **位置**：`backend/domain/order/service.py:155-171`
- **现状**：`_apply_discount` 检查 `user_id` 下同类型已支付订单数。
- **问题**：PRD 1.3 要求“同一 user 下已有 1 个孩子是观察期或正式会员 → 第 2 个孩子起享 9 折”。当前逻辑可能因订单类型不同而不触发优惠。
- **影响**：多孩优惠可能不正确，例如第一个孩子是观察期，第二个孩子购买正式会员时无法享受优惠。
- **建议**：检查 `user` 下 `status in (OBSERVATION, OFFICIAL)` 的孩子数量，≥1 时触发折扣。
- **优先级**：P2

#### [P2] 活动提醒消息优先级与 PRD 不符
- **位置**：`backend/tasks/scheduler.py:1003`
- **现状**：`check_activity_reminders` 创建消息时 `priority=0`（低）。
- **问题**：PRD 2.5 要求“通知优先级‘中’”。
- **影响**：消息优先级不一致，运营侧可能无法正确识别重要通知。
- **建议**：将 `priority` 改为 1（中）。
- **优先级**：P2

#### [P2] 书架容量限制可配置，可能违反 PRD
- **位置**：`backend/domain/bookshelf/service.py:49-54`
- **现状**：`bookshelf_limit` 配置默认 0（无限制），但可通过配置改为有限值。
- **问题**：PRD 5.1 明确“书架从‘借阅书架’改为‘想读清单/收藏夹’……不需要押金，没有数量限制；V3.5 取消 20 本限制”。
- **影响**：若运营误配置有限值，将违反产品定义。
- **建议**：移除 `bookshelf_limit` 配置，强制无限制；或至少将上限设为 0 并添加注释说明不可更改。
- **优先级**：P2

#### [P2] 查词限制基于 user_id 而非当前孩子状态
- **位置**：`backend/domain/vocabulary/service.py:144-153`
- **现状**：`check_lookup_allowed` 按 `user_id` 查询第一个孩子判断是否为 TRIAL。
- **问题**：一个用户可能有多个孩子，状态不同（如一个 TRIAL、一个 OFFICIAL），当前逻辑可能错误限制或放行。
- **影响**：查词限制不公平，可能误伤正式会员孩子或放过试读孩子。
- **建议**：将 `child_id` 传入查词接口，按当前孩子的 `status` 判断。
- **优先级**：P2

#### [P2] 观察期报告缺少“日均阅读分钟”
- **位置**：`backend/domain/report/service.py:226-238`，`ObservationReportDetailResponse`
- **现状**：观察期报告生成与详情返回均未包含“日均阅读分钟”。
- **问题**：PRD 13.2 明确要求报告内容包含“日均阅读分钟”。
- **影响**：报告字段不完整。
- **建议**：计算 `daily_avg_minutes = total_reading_minutes / observation_days` 并返回。
- **优先级**：P2

#### [P2] 朗读完成未自动触发阅读打卡
- **位置**：`backend/domain/reading/service.py:259-271`
- **现状**：`save_recording` 仅保存录音记录，未触发打卡。
- **问题**：PRD 16.3 要求“朗读完成后自动触发阅读打卡（如果今日未打卡）”。
- **影响**：朗读打卡联动缺失。
- **建议**：在 `save_recording` 中调用与 `end_session` 类似的打卡检查逻辑。
- **优先级**：P2

#### [P3] 语音评测字段超前于 PRD 规划
- **位置**：`backend/domain/reading/models.py:138-140`
- **现状**：`VoiceRecording` 已包含 `pronunciation_score`、`fluency_score`、`completeness_score`。
- **问题**：PRD 16.4 明确“语音评测（后续版本）”为规划中，当前无实际评测能力，但模型字段已存在。
- **影响**：轻度过度开发，可能误导前端实现未规划功能。
- **建议**：保留字段但添加注释说明为预留；或在实际接入语音评测服务前隐藏相关 API/字段。
- **优先级**：P3

#### [P3] 书架域存在 PRD 未定义的“收藏夹”功能
- **位置**：`backend/domain/bookshelf/service.py:104-151`
- **现状**：`BookshelfService` 除“想读清单”外，还实现了 `Favorites` 的增删改查。
- **问题**：PRD 第五章仅定义“想读清单”，未提及收藏夹。
- **影响**：轻度过度开发，可能与前端产品定义不一致。
- **建议**：确认产品是否需要独立收藏夹；如不需要，移除 Favorites 相关接口与模型。
- **优先级**：P3

### 1.3 维度 1 结论

- **维度结论**：**有条件通过**
- **关键改进项**：
  1. 修复阅读提交自动创建逻辑（P0）。
  2. 修正测验通过事件对 books_read 的误增（P0）。
  3. 补齐观察期/正式会员报名的评估前置校验（P0）。
  4. 完善权益转让的目标孩子状态校验（P0）。
  5. 实现亲子课退款的时间窗口规则（P0）。
  6. 补充预约押金校验、取消释放库存、逾期音频锁定等 P1 项。

---

## 维度 12：PRD 与 Feature 文件审查

### 12.1 审查结果

#### 12.1.1 Feature 文件与 PRD 对应关系

| Feature 文件 | 对应 PRD 章节 | 场景数 | 覆盖状态 | 主要差异 |
|--------------|--------------|--------|----------|----------|
| `user_enrollment.feature` | 一、用户报名流程 | 8 | ✅ 基本覆盖 | 多孩优惠场景未覆盖“观察期孩子作为第 1 孩”的边界 |
| `activity_enrollment.feature` | 二、活动报名流程 | 11 | ✅ 基本覆盖 | 缺少收费活动取消后退款的场景 |
| `benefit_transfer.feature` | 三、会员权益转让 | 6 | ✅ 基本覆盖 | 目标孩子是观察期/正式会员的场景未覆盖 |
| `bookshelf.feature` | 五、书架/想读清单 | 7 | ✅ 基本覆盖 | 缺少“从书架直接预约借书”的端到端场景 |
| `borrow_record.feature` | 六、实体书借阅 | 13 | ✅ 基本覆盖 | 状态名使用“BORROWED”而非 PRD 的“BORROWING” |
| `deposit.feature` | 七、押金管理 | 8 | ✅ 基本覆盖 | 无显著差异 |
| `reservation.feature` | 八、在线预约借书 | 6 | ⚠️ 部分覆盖 | 状态名使用“RESERVED/PICKED_UP”而非 PRD 的“PENDING/FULFILLED”；缺少取消后释放库存场景 |
| `vocabulary.feature` | 九、查词与生词本 | 10 | ✅ 基本覆盖 | 未覆盖 Free Dictionary API 兜底场景 |
| `reading_stats.feature` | 十、阅读打卡/统计/报告 | 11 | ✅ 基本覆盖 | 缺少语音朗读次数统计场景 |
| `advancement.feature` | 十一、晋级体系 | 15 | ✅ 基本覆盖 | 晋级条件使用“通过 5 次测验”示例，与 PRD “至少 1 次”存在偏差 |
| `level_certificate.feature` | 十二、晋级证书 | 5 | ✅ 基本覆盖 | 无显著差异 |
| `observation_report.feature` | 十三、观察期报告 | 7 | ✅ 基本覆盖 | 缺少“日均阅读分钟”字段验证 |
| `personal_profile.feature` | 十四、个人名片 | 3 | ✅ 基本覆盖 | 无显著差异 |
| `refund_application.feature` | 十五、退款申请流程 | 9 | ✅ 基本覆盖 | 缺少亲子课“课程开始前/后”的差异化退款场景 |
| `online_reading.feature` | 四、在线听读与阅读记录 | 9 | ⚠️ 部分覆盖 | 未覆盖逾期锁定音频场景；未覆盖读完自动创建阅读提交场景 |
| `voice_reading.feature` | 十六、语音朗读与练习 | 6 | ⚠️ 部分覆盖 | 缺少朗读后自动打卡场景；语音评测场景为后续版本，不应与当前实现混淆 |

### 12.2 发现的问题

#### [P2] 借阅 Feature 状态名与 PRD 不一致
- **位置**：`features/borrow_record.feature:18-19`
- **现状**：场景描述借阅状态为“BORROWED”。
- **问题**：PRD 6.1/6.2 定义状态为“BORROWING”，附录状态转换也为 `BORROWING/OVERDUE → LOST(3)`。
- **影响**：BDD 场景与 PRD 术语不一致，可能误导实现或测试断言。
- **建议**：将 Feature 文件中的“BORROWED”统一改为“BORROWING”。
- **优先级**：P2

#### [P2] 预约 Feature 状态名与 PRD 不一致
- **位置**：`features/reservation.feature:17-18`，`42-43`
- **现状**：场景描述预约状态为“RESERVED”和“PICKED_UP”。
- **问题**：PRD 8.1/8.2 定义状态为“PENDING”和“FULFILLED”。
- **影响**：实现代码中实际使用 PENDING/FULFILLED，Feature 文件与代码不一致。
- **建议**：统一使用 PRD 定义的状态名“PENDING”和“FULFILLED”。
- **优先级**：P2

#### [P2] Feature 文件缺少关键负面场景
- **位置**：`features/reservation.feature`、`features/activity_enrollment.feature`、`features/borrow_record.feature`
- **现状**：缺少以下场景：
  - 预约借书时未缴纳押金；
  - 用户主动取消预约后库存释放；
  - 活动名额已满并发报名；
  - 丢书罚款超过押金余额；
  - 借阅同一本书重复借书冲突。
- **问题**：负面/边界场景覆盖不足，容易遗漏并发与资损类 bug。
- **影响**：测试无法验证异常路径，生产环境可能出现问题。
- **建议**：按 PRD 失败场景补充负面用例，并确保 BDD Step 定义可复用。
- **优先级**：P2

#### [P2] 多孩优惠 Feature 未覆盖观察期触发条件
- **位置**：`features/user_enrollment.feature:68-73`
- **现状**：只测试“用户已有 1 个孩子是正式会员”时享受多孩优惠。
- **问题**：PRD 1.3 明确“同一 user 下已有 1 个孩子是观察期或正式会员”即可触发优惠。
- **影响**：当第一个孩子是观察期、第二个孩子报名时，可能未覆盖测试。
- **建议**：补充“第一个孩子为观察期，第二个孩子购买正式会员享受 9 折”的场景。
- **优先级**：P2

#### [P2] PRD 对季度/半年会员的边界规则描述不完整
- **位置**：`PRD/MegaWords_V3.5需求文档.md` 1.3a
- **现状**：仅说明“三种会员类型均映射到 status=2（OFFICIAL），通过 Order.type 区分”和“同正式会员权益”。
- **问题**：未明确季度/半年会员在退款、权益转让、升级时的规则是否与年费完全一致（如按 90/180 天计算）。
- **影响**：实现时可能产生歧义，例如季度会员退款是否按 90 天比例。
- **建议**：补充季度/半年会员的退款、转让、升级细则。
- **优先级**：P2

#### [P2] 状态机未明确 EXPIRED 用户是否可以重新购买亲子课
- **位置**：`PRD/MegaWords_V3.5需求文档.md` 附录 A
- **现状**：状态机显示 `EXPIRED → OFFICIAL`，但未说明 EXPIRED 是否可回到 TRIAL 或购买亲子课。
- **问题**：业务规则模糊，可能导致一个已过期孩子无法再次体验。
- **建议**：在附录 A 中补充 EXPIRED 状态下可购买的订单类型。
- **优先级**：P2

#### [P2] PRD 与 Feature 对“读完自动创建阅读提交”均未明确覆盖
- **位置**：`PRD/MegaWords_V3.5需求文档.md` 11.2；`features/online_reading.feature:67-73`
- **现状**：PRD 要求“读完最后一页自动创建阅读提交记录”，但 `online_reading.feature` 只验证“自动触发阅读打卡”，未验证阅读提交创建。
- **问题**：需求与测试都未明确覆盖关键 P0 功能点。
- **影响**：开发过程中容易遗漏 ReadingSubmission 的自动创建。
- **建议**：在 PRD 中增加更明确的流程图，并在 `online_reading.feature` 或 `advancement.feature` 中补充“读完自动创建待审核提交”的场景。
- **优先级**：P2

#### [P3] PRD 缺少版本变更日志
- **位置**：`PRD/MegaWords_V3.5需求文档.md` 全文
- **现状**：仅包含版本 V3.5 和日期，无历史变更记录。
- **问题**：无法追溯需求从 V3.0/V3.1 到 V3.5 的变更（如书架语义从“借阅书架”改为“想读清单”）。
- **影响**：新成员难以快速理解需求演进，容易产生实现偏差。
- **建议**：在 PRD 末尾增加“版本变更日志”章节，记录关键变更点、原因和日期。
- **优先级**：P3

#### [P3] 语音评测 Feature 与 PRD 规划阶段不一致
- **位置**：`features/voice_reading.feature:36-47`
- **现状**：`voice_reading.feature` 包含“获取发音评分”和“发音改进建议”场景。
- **问题**：PRD 16.4 明确标注“语音评测（后续版本）”为规划中，当前版本不应实现。
- **影响**：Feature 文件与 PRD 规划不一致，可能引导开发实现未规划功能。
- **建议**：将语音评测相关场景标记为 `@future` 或移除到单独的 `voice_reading_future.feature` 文件中。
- **优先级**：P3

### 12.3 维度 12 结论

- **维度结论**：**有条件通过**
- **关键改进项**：
  1. 统一 Feature 文件与 PRD 的状态术语（BORROWING/BORROWED、PENDING/RESERVED 等）。
  2. 补充关键负面场景（押金校验、库存释放、并发名额、重复借书等）。
  3. 补充多孩优惠的观察期触发条件场景。
  4. 在 PRD 中补充季度/半年会员边界规则、EXPIRED 状态可购买类型、版本变更日志。
  5. 将语音评测场景与当前版本规划对齐。

---

## 总体结论

- **整体评级**：**C**（需求覆盖度与文档一致性存在多项 P0/P1 问题，需修复后才能进入生产环境）
- **关键风险项**：
  1. 阅读提交未自动创建，直接影响晋级与观察期报告数据链（P0）。
  2. 测验通过错误增加已读书数，导致晋级条件失真（P0）。
  3. 报名前置条件缺失，可能让未完成必要评估的孩子进入下一阶段（P0）。
  4. 权益转让目标状态校验不足，可能覆盖现有会员权益（P0）。
  5. 亲子课退款规则缺失，存在财务风险（P0）。
- **建议的修复优先级**：
  - 立即修复（P0）：阅读提交、测验事件、报名前置条件、权益转让校验、亲子课退款。
  - 本迭代内修复（P1）：预约押金、活动取消退款、Free Dictionary API 兜底、teacher_id 分配、到期状态转换、借阅押金/BookCopy 校验、预约取消库存、逾期音频锁定、语音朗读统计。
  - 下迭代优化（P2/P3）：Feature 术语统一、负面场景补充、PRD 边界规则补充、版本变更日志。
- **下一步行动项**：
  1. 由后端团队修复 P0/P1 业务逻辑问题，并补充对应单元测试。
  2. 由产品经理澄清 PRD 中季度/半年会员、EXPIRED 可购买类型、日均阅读分钟等边界规则。
  3. 由测试团队更新 Feature 文件状态术语并补充负面场景。
  4. 重新运行 BDD 与单元测试，验证修复后覆盖度。

---

*报告生成时间：2026-07-03*  
*审查人：Alice（产品经理）*  
*依据文件：`PRD/MegaWords_V3.5需求文档.md`、`features/`、`backend/domain/`、AUDIT_REPORT.md*
