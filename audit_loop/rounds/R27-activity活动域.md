# R27 第二十七轮 activity 活动域 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-075 起 / C-120 起。

## 范围

R27 activity 活动域（此前仅 F-046 涉 migrate_activity_status）。本轮：报名（enroll）、取消
（cancel_enrollment）、签到（sign_in/sign_in_by_ticket_code/batch_checkin）、状态机
（PENDING/APPROVED/REJECTED/CANCELLED/SIGNED_IN）、名额控制。

## 结果

- **发现 1 项**：F-075（P3）enroll 并发双报名（先查后插无唯一约束，同一孩子重复占名额）
- **clean 1 项**：C-120 活动域其余面正常（原子递增防超卖/取消行锁/签到/状态机）

---

## [F-20260808-075] enroll 防重无唯一约束——并发双报名（同一孩子重复占名额 + 双 ticket） — P3

- **级别**: P3（观察项；需 MySQL 并发实证；人数原子递增防超卖，但重复占名额）
- **维度**: R4 并发补面（先查后插无唯一约束模式，F-066 同类）
- **文件**: `backend/domain/activity/service.py:84-143`（enroll）/ `backend/domain/activity/models.py:71-95`（ActivityEnrollment 无唯一约束）
- **事实**:
  - enroll（service.py:92-101）防重：查 `ActivityEnrollment(child_id, activity_id, is_deleted==0)` 无锁 first() → 无则创建（L110-125）——**先查后插无 DB 唯一约束兜底**（models.py:75 __table_args__ 空）
  - 并发场景：同一孩子同时提交两次报名（双端/重试）→ 两事务同时查无 existing → 都通过 → 各自原子递增人数（L103-121，`current < max` 条件 UPDATE 防超卖，两次都成功）→ **创建两条报名记录**（两个 ticket_code，免费活动双 APPROVED）
  - 人数不超卖（原子递增条件 UPDATE 正确），但**同一孩子占两个名额 + 双报名记录**
  - cancel_enrollment 释放名额也是原子递减（L176-180，current>0 条件）✓
- **证据**: ① service.py:92-125 先查后插；② models.py:75 无 UniqueConstraint；③ 排重 grep：findings 无"重复报名/双报名/enroll 并发"命中；F-066（pay_fines 双单）为同类先查后插模式（不同域）
- **触发**: 同一孩子的两个并发报名请求（家长双端点击/网络重试）→ MySQL 下双事务同时通过防重 → 双报名
- **影响**: 同一孩子双报名（占两个名额 + 双 ticket_code，免费活动可双签到）；名额被重复占用导致其他孩子少一个名额（人数不超卖但浪费名额）。无资金/安全。窗口极窄（MySQL 并发 + 双端操作）
- **建议**: ① ActivityEnrollment 加唯一约束 `(child_id, activity_id)`（DB 兜底，与 enroll 的 already_enrolled 逻辑配合——需处理 CANCELLED 复用）；② 或 enroll 的 existing 查询加 `with_for_update()`（锁 existing 行防并发）；③ 或原子递增人数后校验 affected==1 且为首次（enrollment 插入用条件）
- **排重**: 已 grep 确认不在 F-001~074 / C-001~119 中；F-066（pay_fines）同类模式不同域；F-046（migrate_activity_status 状态写）不同面

---

## [C-20260808-120] 活动域其余面（原子递增/取消/签到/状态机） — clean

- **方法**: R27 定向纵深。读 activity/service.py 全（list_activities/enroll/cancel_enrollment/sign_in/sign_in_by_ticket_code/get_enrollments/batch_checkin/confirm_paid_enrollment/cancel_activity/create/update/delete）+ router.py（权限/归属）+ models.py + 排重
- **证据**:
  - **名额原子递增防超卖**：enroll 条件 UPDATE `current_participants < max_participants` 才 +1（L103-109）✓；cancel 原子递减 current>0（L176-180）✓
  - **取消**：with_for_update 行锁（L153）+ 已取消守卫（L157）+ 开始前 N 小时校验（activity_cancel_hours）✓
  - **签到**：sign_in 状态守卫（仅 APPROVED 可签）+ SIGNED_IN 防重 ✓；sign_in_by_ticket_code 票码校验 ✓；batch_checkin 管理端批量 ✓
  - **归属**：enroll 用 GetOwnedChildFromBody（router.py:45）✓；cancel/sign_in 用 GetOwnedEnrollment ✓
  - **权限**：管理端端点 require_perm（activity.create/edit/delete/checkin）✓
  - **状态机**：PENDING/APPROVED/REJECTED/CANCELLED/SIGNED_IN 转移（免费自动 APPROVED / 收费待审核 / cancel 守卫）✓；F-046（migrate_activity_status 任务态迁移）已报排重
  - **免费/收费双模式**：is_free/is_light 自动通过（E4）✓
- **排重**: R27 本轮活动域 clean 侧（F-075 并发双报名为唯一缺口）；F-046 已报不重

---

## R27 完结汇总

- **范围**: activity 活动域（报名/取消/签到/名额/状态机）
- **结果**: 发现 1 项（F-075 P3 enroll 并发双报名）+ clean 1 项（C-120）
- **关键结论**:
  - 活动域工程正常：名额原子递增防超卖（条件 UPDATE）、取消行锁、签到状态守卫、免费/收费双模式
  - 唯一缺口：enroll 先查后插无唯一约束（ActivityEnrollment）——并发双报名占双名额；与 F-066（pay_fines）同类"先查后插无唯一约束"模式（第 2 处）
  - 修复成本低（加唯一约束或 existing 查询加锁）
- **累计**: 74 发现（P0:0 / P1:0 / P2:10 / P3:64）+ 117 clean 记录
- **提交**: 见 git log（本轮 rounds/R27 文件 + progress 索引同步更新）
- **R27 收尾结论**: 二十七轮共 74 项发现无 P0/P1；10 项 P2 全部未修。R28 候选：书架域（bookshelf_limit=100 想读上限）或剩余小域（bookshelf/order 补面）。
