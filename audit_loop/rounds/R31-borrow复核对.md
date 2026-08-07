# R31 第三十一轮 borrow 全链复核对 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：C-124 起（本轮零发现）。

## 范围

R31 borrow 全链复核对（R4 C-099 并发面 / R5 罚款公式 / R6 预约候补已审）。本轮换面（深度递增）：
borrow_book（借阅上限/副本/库存）/ return_book（还书守卫/罚款）/ scan_and_return（条码防重）/
scan_and_borrow / borrow_from_reservation 的锁覆盖与状态守卫复核对。

## 结果

- **发现 0 项**
- **clean 1 项**：C-124 borrow 全链复核对整体安全（上限锁/副本锁/原子库存/还书守卫/条码防重）

---

## [C-20260808-124] borrow 全链复核对（上限/副本/库存/还书/条码） — clean

- **方法**: R31 定向纵深。读 borrow/service.py 全（borrow_book L59-196/scan_and_return L197-222/return_book L223-280/mark_quiz_passed/scan_and_borrow L298-382/borrow_from_reservation L383-509/get_child_borrows L510+）+ 排重对照
- **证据**:
  - **借阅上限**：borrow_book 查活跃记录（BORROWING+OVERDUE）带 with_for_update（L82-91）串行化——并发借书不会双双超限（C-099 已确认权威校验）✓
  - **防重复借同书**：BORROWING/OVERDUE 双状态查重（L94-102）——同书未还不可再借 ✓
  - **副本状态**：with_for_update 行锁（F69）+ 非 AVAILABLE 时友好提示（BORROWED 显示预计归还日）✓
  - **后扣库存**：SQL 原子更新 `available_stock > 0` 条件（L118-125）防并发超卖 ✓
  - **还书守卫**：return_book 状态守卫（仅 BORROWING/OVERDUE 可还，L235-237）+ with_for_update ✓；重复还书被守卫拦截（已 RETURNED → ConflictError）✓
  - **条码防重**：scan_and_return 查活跃借阅（BORROWING/OVERDUE）→ 重复扫描已还 → "无活跃借阅记录"（L215-217）✓ 双防（return_book 守卫 + scan 活跃查询）
  - **罚款链**：apply_fine + sync_outstanding_fine（F36 差额增量防双计）+ child with_for_update（L255-262）——R5/F-047 已审公式与首次免罚竞态 ✓
  - **预约取书**：borrow_from_reservation 上限权威校验（C-099 已审）✓
  - **事件**：BookBorrowed/ReturnedEvent 发布（C-109 已审重放幂等）✓
  - **异常处理**：SQLAlchemyError rollback（L192-195）✓
- **排重**: R31 本轮 borrow 全链 clean 侧（零新缺陷）；C-099（R6 并发锁分层）/F-047（R5 免罚竞态）/F-056（候补）已报不重

---

## R31 完结汇总

- **范围**: borrow 全链复核对（借阅上限/副本/库存/还书/条码）
- **结果**: 发现 0 项 + clean 1 项（C-124）
- **关键结论**:
  - borrow 全链工程质量高：上限行锁串行化、副本 F69 锁、原子扣库存、还书状态守卫、条码双防重、罚款差额增量
  - 经 R4（C-099）/R5（F-047）/R6（F-056）/R31（复核对）四轮核查，borrow 面彻底
  - 本轮为合法零发现（铁律 3）
- **累计**: 75 发现（P0:0 / P1:0 / P2:10 / P3:65）+ 121 clean 记录
- **提交**: 见 git log（本轮 rounds/R31 文件 + progress 索引同步更新）
- **R31 收尾结论**: 三十一轮共 75 项发现无 P0/P1；10 项 P2 全部未修。R32 候选：refund 域补面（退款申请/审核/执行链）或综合异常路径（500 处理/全局异常）。
