# R36 第三十六轮 borrow 管理端补面 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：C-129 起（本轮零发现）。

## 范围

R36 borrow 管理端补面（用户域 R31 已核，本轮管理端）。admin borrow service（clear_child_fines/
save_checkout_photos/list_borrows/list_deposits/list_reservations）+ admin_borrow_router（借还/罚款清零/
逾期提醒/押金操作/预约）——管理端操作的资金面与权限。

## 结果

- **发现 0 项**
- **clean 1 项**：C-129 borrow 管理端整体安全（clear_fines 行锁 + 复用用户域校验 + 操作日志）

---

## [C-20260808-129] borrow 管理端（罚款清零/借还/操作日志） — clean

- **方法**: R36 定向纵深。读 admin/services/borrow_service.py 全（clear_child_fines L23-39/save_checkout_photos
  L40-58/list_borrows L59-129/list_deposits L130-198/list_reservations L199-273/_batch_borrow_counts
  L288-304/list_children/search_children）+ admin_borrow_router 全（25 端点）+ 排重
- **证据**:
  - **clear_child_fines**（L23-39）：child with_for_update 行锁（防并发罚款计入 lost update，P0-3 审查点）+ outstanding_fines 清零 + cleared_amount 留痕 ✓ 资金面锁覆盖正确
  - **管理端借还**（admin_borrow_router.py:108-151）：require_perm("borrow.create"/"borrow.return") + **复用用户域 BorrowService.borrow_book/return_book**（R31 已核校验链：上限/副本/库存/还书守卫）✓
  - **操作日志**：借/还/逾期提醒/罚款清零均 write_operation_log（admin_id 留痕）✓
  - **预约管理**：fulfill/cancel/创建均 require_perm（borrow.fulfill 等）+ 用户域 ReservationService 校验（R6 C-099 已核锁分层）✓
  - **押金操作**：audit-refund/refund/pay/deduct/mark-refunded 均 require_perm（deposit.*）+ 用户域 DepositService（R17 已核）✓
  - **列表查询**：_batch_borrow_counts 批量 in_ 预取（L288-304，无 N+1）✓
  - **权限码**：R11 已核 152 端点全覆盖 ✓
- **排重**: R36 本轮管理端 clean 侧（零新缺陷）；R31（用户域）/C-099（预约锁）/R17（deposit）/R11（权限码）互补

---

## R36 完结汇总

- **范围**: borrow 管理端补面（罚款清零/借还/预约/押金/操作日志）
- **结果**: 发现 0 项 + clean 1 项（C-129）
- **关键结论**:
  - 管理端操作工程质量高：clear_fines 行锁、复用用户域校验链（避免双套逻辑分叉）、操作日志全覆盖
  - 管理端与用户域共用 service 是良好架构（校验单点）
  - 本轮为合法零发现（铁律 3）
- **累计**: 76 发现（P0:0 / P1:0 / P2:11 / P3:65）+ 126 clean 记录
- **提交**: 见 git log（本轮 rounds/R36 文件 + progress 索引同步更新）
- **R36 收尾结论**: 三十六轮共 76 项发现无 P0/P1；11 项 P2（含 F-077 账号接管）。R37 候选：继续轮转新面。
