# R46 第四十六轮 damage 损坏报告域 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-080 起 / C-139 起。

## 范围

R46 damage 损坏报告域（此前仅 F-001/004 库存无锁/F-038 月报查询涉 damage）。本轮换面：定责/赔偿资金链
（create_report/confirm_report/reject_report/review/appeal/mark_book_found/replace_with_new_copy/
confirm_expired）——状态守卫、锁覆盖、财务效应、双人复核。

## 结果

- **发现 1 项**：F-080（P2）confirm/reject/review 先查后改无锁（_get_report_or_raise 无 with_for_update）——并发双确认双计罚款
- **clean 1 项**：C-139 damage 域其余面正常（双人复核/物理回滚/资金锁）

---

## [F-20260808-080] damage confirm/reject/review 先查后改无锁——并发双确认双计罚款（F-053/F-058 同模式） — P2

- **级别**: P2（资金面——多收罚款；需 MySQL 并发实证；F-053/F-058 同模式定级先例）
- **维度**: R4 并发×资金补面（先查后改无锁模式）
- **文件**: `backend/domain/admin/services/damage_admin_service.py:673-682`（_get_report_or_raise 无锁）/ `:180-207`（confirm_report）/ `:208-231`（reject_report）/ `:502-634`（review）
- **事实**:
  - `_get_report_or_raise`（L673-682）：`query(BookDamageReport).filter(id, is_deleted==0).first()`——**无 with_for_update**
  - `confirm_report`（L180-207）：读 report（无锁）→ `if status != PENDING_REVIEW: 拒绝`（L184-185 无锁守卫）→ `child.outstanding_fines += fine`（L193-195，child 带锁）→ status=PENDING
  - **并发双确认**：两管理员同时确认同一报告（T1/T2）→ 都读 report.status=PENDING_REVIEW（T1 未提交）→ 都过守卫 → 各自锁 child → **T1 +fine 提交后 T2 又 +fine**（T2 的 report 是旧快照 PENDING_REVIEW，因 report 查询无锁）→ **罚款双计**
  - reject（L208-231）/review（L502-634）同构（无锁 status 守卫 + 状态变更）
  - 与 F-053（cancel_order 无锁覆盖 PAID）/F-058（review_submission 无锁读-改-写）**同模式**（先查后改无锁）
- **证据**: ① damage_admin_service.py:673-682 无锁；② confirm_report L184-195 状态守卫 + child 锁（report 无锁）；③ 排重 grep：findings 无"damage 并发双确认/双计罚款"命中（F-001/004 为 book 库存无锁，F-038 为月报查询，不同面）；F-053/F-058 同模式先例
- **触发**: 两名管理员几乎同时确认同一损坏报告（B9 双人复核流程中并发）→ 双计罚款入 child.outstanding_fines
- **影响**: 用户被多收罚款（双计）——资金面错误，需人工冲正；无系统资金损失（罚款在账上，多收部分需退）。低频（双人复核 + 并发窗口极窄），P2（资金面 + F-053/F-058 同模式先例）
- **建议**: ① _get_report_or_raise 加 with_for_update（或 confirm/reject/review 单独行锁查询）；② 状态变更改条件 UPDATE `WHERE id AND status=PENDING_REVIEW` 按 affected==1 判定（F-053 修复模式）；③ 或 confirm 时二次校验 report.status（锁内重取）
- **排重**: 已 grep 确认不在 F-001~079 / C-001~138 中；F-053（cancel_order）/F-058（review_submission）为同模式先例；F-001/004（book 库存无锁）不同面

---

## [C-20260808-139] damage 域其余面（双人复核/物理回滚/资金锁） — clean

- **方法**: R46 定向纵深。读 damage_admin_service.py 全（create_report/confirm_report/reject_report/
  mark_book_found/replace_with_new_copy/_rollback_lost_physical/get_list/appeal/review/confirm_expired/
  batch_confirm_expired/_send_damage_notification）+ 排重
- **证据**:
  - **双人复核（B9）**：confirm/reject 校验 `admin_id != 本人`（L186-188/214-216）✓
  - **物理回滚**：reject 时 damage_level==3 → _rollback_lost_physical（L221-223）✓；mark_book_found 找回（B10 寻找期）✓
  - **资金锁**：confirm 时 child with_for_update（L186-190）——罚款计入 child 行锁串行 ✓（F-080 为 report 状态层无锁）
  - **状态机**：PENDING_REVIEW→PENDING（申诉期）→DISPUTED→APPROVED/OVERRIDE（review）；confirm_expired（7 天申诉期过）✓
  - **通知**：_send_damage_notification/_send_review_pending_notification（消息域 R22/R44 已审）✓
  - **操作日志**：_log_operation ✓
  - **权限**：R11 已核 152 端点（damage.*）✓
- **排重**: R46 本轮 damage 域 clean 侧（F-080 状态层无锁为唯一缺口）；F-001/004/038 已报不重

---

## R46 完结汇总

- **范围**: damage 损坏报告域（定责/赔偿/审核/申诉/找回）
- **结果**: 发现 1 项（**F-080 P2 并发双计罚款**）+ clean 1 项（C-139）
- **关键结论**:
  - **F-080 是第二个 P2（资金面）**：confirm/reject/review 先查后改无锁（_get_report_or_raise 无 with_for_update）——并发双确认双计罚款；F-053/F-058 同模式（先查后改无锁家族再添一例，共 7 处：F-053/058/066/075/076/078/080）
  - damage 域其余面工程正常（双人复核/物理回滚/child 锁/状态机）
  - 修复成本低（_get_report_or_raise 加锁或条件 UPDATE）
- **累计**: 79 发现（P0:0 / P1:0 / **P2:12** / P3:67）+ 136 clean 记录
- **提交**: 见 git log（本轮 rounds/R46 文件 + progress 索引同步更新）
- **R46 收尾结论**: 四十六轮共 79 项发现无 P0/P1；**12 项 P2**（F-080 新增资金面，含 F-077 账号接管）。R47 候选：继续轮转新面。
