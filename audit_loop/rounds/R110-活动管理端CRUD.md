# R110 第一百一十轮 活动管理端 CRUD — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-096/F-097 起，C-203 起。

## 范围

R110 活动管理端 CRUD（activity/service.py：create/update/delete/cancel + admin_activities_router +
Activity/ActivityEnrollment 模型 + CreateActivityRequest/UpdateActivityRequest schema + base_repo
get_by_id_or_raise 过滤链）。R27（F-075 并发双报名/C-120 状态机）覆盖报名链，本轮定向纵深管理端 CRUD 面。

## 结果

- **发现 2 项**（P3×2）：F-096 delete_activity 绕过 cancel 完整保障（无退款/无通知/报名悬空）；F-097
  create/update 无 start<end 时间校验（F-069/F-073 同类模式，活动域漏改）
- **clean 1 项**：C-203 enroll 过滤链 + cancel 锁分层（排重 R27，复核确认）

---

## [F-20260808-096] delete_activity 绕过 cancel_activity 保障链——已报名活动被删，付费无退款/报名者无通知（P3）

- **级别**: P3（低-中：业务保障缺失，付费退款链断裂；触发依赖管理端误删已报名活动）
- **位置**: backend/domain/activity/service.py:469-478（delete_activity）；对照 :332-446（cancel_activity）
- **类别**: 状态守卫缺失（模式⑤ 家族）+ 业务规则绕过（模式③ 家族）
- **事实**: delete_activity 仅 `activity.is_deleted = 1` + commit——**不检查报名数、不通知报名者、不触发付费退款**；而 cancel_activity 是完整保障链：with_for_update 锁 + 状态守卫 + 逐报名者取消 + 付费用户写 RefundApplication（E5 自动退款）+ SystemMessage 通知（L332-446）
- **证据**:
  - service.py:469-478 delete 无任何 enrollment 查询/状态校验/通知/退款逻辑
  - service.py:332-446 cancel 完整实现（对照）：状态守卫（CANCELLED/FINISHED 拦截）+ with_for_update + 报名批量取消 + RefundApplication（F53 转人工队列）+ 家长端 SystemMessage
  - 报名记录影响：ActivityEnrollment.is_deleted 仍 0（service.py:51/97/152/251/297 均不过滤已删活动）→ 家长端 my enrollments 显示报名成功但活动已删 → ticket 作废无提示
  - 付费链：activity.is_free=0 且 price>0 时 cancel 会写退款申请，delete 完全跳过 → 已付款家庭钱票两空（需人工发现）
- **触发**: 管理端对已有 PENDING/APPROVED 报名的活动（尤其收费活动）执行删除而非取消
- **影响**: ① 收费活动已付款报名者无退款流程（cancel 有，delete 无——保障不对称）；② 报名者无通知，到现场扑空；③ enrollment 记录悬空，签到/统计异常
- **建议**: delete_activity 前置检查：存在非 CANCELLED 有效报名（status IN PENDING/APPROVED）时拒绝删除，引导走 cancel_activity；或 delete 内部复用 cancel 的报名清理+退款+通知链
- **排重**: grep 无"绕过 cancel/删除活动"历史；R27 C-120（cancel 状态机）已核 cancel 侧正确，delete 侧为本轮新发现；F-092（venue 假成功）为存在性面，不同

---

## [F-20260808-097] create_activity/update_activity 无 start<end 时间校验（F-069/F-073 同类模式活动域漏改）（P3）

- **级别**: P3（观察项；管理端输入校验缺失，数据质量；与 R20 F-069 / R25 F-073 同类模式）
- **位置**: backend/domain/activity/service.py:447-467（create/update）；backend/domain/admin/admin_schemas.py:426-460（CreateActivityRequest/UpdateActivityRequest）
- **类别**: 管理端 schema 校验缺失（模式② 家族；F-069/F-073 同类，活动域漏改）
- **事实**: create_activity `Activity(**data.model_dump())` 直接入库（L447-452），update_activity exclude_unset 直接 setattr（L454-467）——**均无 start_time < end_time 校验、无 enroll_deadline 合理性校验**；schema start_time/end_time 为裸 str（admin_schemas.py:438-439 无格式/先后校验）
- **证据**:
  - admin_schemas.py:426-442 CreateActivityRequest：start_time/end_time 裸 str，无 Pydantic 校验；service create 直接入库
  - 对照已报同类：F-069（R20 parent_course_time end<start）、F-073（R25 BookCreate age 倒挂）、R26 建议 schedule 同修——**活动域是同类模式又一漏改点**（模式 1 防复发红线）
  - update_activity（L460-467）：可把 end_time 改早于 start_time、把 FINISHED 活动改回 ENROLLING（status ge=0 le=5 只挡范围不挡状态机转移）
- **触发**: 管理端创建 start>end 的活动 / 更新把时间改倒挂
- **影响**: 用户端展示倒挂时段（产品体验差）；enroll 守卫仅 status==ENROLLING 不校验时间——倒挂活动可正常报名；状态机可回退（FINISHED→ENROLLING 复活已结束活动）。无资金/安全。管理端低频 + 运营规范输入则不影响
- **建议**: ① CreateActivityRequest start_time/end_time 加格式 + 先后校验（datetime 类型而非 str）；② update 时校验 end>start；③ status 转移用允许矩阵（参照 R27 C-120 状态机，管理模式⑤）
- **排重**: 已 grep 确认不在 F-001~095 / C-001~202 中；F-069（课程时段）/F-073（BookCreate）为同类不同实体；F-075（活动报名并发）不同面

---

## [C-20260808-203] enroll 过滤链 + cancel 锁分层（复核） — clean

- **方法**: R110 定向纵深。读 activity/service.py 全 + admin_activities_router.py + Activity/Enrollment 模型 + base_repo get_by_id + R27 对照
- **证据**:
  - **enroll 过滤链**：get_by_id_or_raise 自动过滤 is_deleted（base_repo.py:53-71）✓ + 状态守卫 ENROLLING（L87-89）✓ + 防重查重（L93-100）✓ + 原子递增（L109-120）✓ —— F-075（并发双报名）已报，本条不重
  - **cancel_activity**：with_for_update 行锁 + 状态守卫 + 退款申请 + 通知（L332-446）✓ —— R27 C-120 已核，复核确认
  - **list/get**：repo.get_by_id 过滤软删 ✓（删除后家长端不再展示已删活动）
  - **权限**：activity.create/delete/list require_perm（router）✓
- **排重**: R27（F-075/C-120）报名链、R13（F-046 定时任务活动状态）、R45（接口覆盖）互补；本条为复核 clean

---

## R110 完结汇总

- **范围**: 活动管理端 CRUD（create/update/delete/cancel + schema + 过滤链）
- **结果**: 发现 2 项（F-096/F-097 均 P3）+ clean 1 项（C-203）
- **关键结论**:
  - delete_activity 与 cancel_activity 保障不对称：删已报名（尤其收费）活动 → 无退款无通知报名悬空
  - create/update 无 start<end 校验——F-069/F-073 同类模式活动域漏改（防复发红线 1：修复时三域同改）
  - enroll 过滤链与 cancel 锁分层工程正确（R27 复核）
- **累计**: 96 发现（P0:0 / P1:0 / P2:14 / P3:82）+ 200 clean 记录
- **提交**: 见 git log（本轮 rounds/R110 文件 + progress 索引同步更新）
- **R110 收尾结论**: 一百一十轮共 96 项发现无 P0/P1；14 项 P2。R111 候选：继续轮转新面（如 certificate 管理端、message 管理端、guardian 管理端）。
