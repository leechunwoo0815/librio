# R41 第四十一轮 benefit_transfer 审核链 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-078 起 / C-134 起。

## 范围

R41 benefit_transfer 管理端审核链（R35 已审 child 域 transfer 本体，本轮管理端）。get_list/approve/reject
——审核并发、状态守卫、双执行防护。

## 结果

- **发现 1 项**：F-078（P3）approve/reject 无锁读-改-写（app.status 守卫无 with_for_update，双审核依赖 transfer 二次校验兜底）
- **clean 1 项**：C-134 审核链其余面正常（状态守卫 + transfer 校验兜底 + 权限）

---

## [F-20260808-078] benefit_transfer approve/reject 无锁读-改-写——app.status 守卫无 with_for_update（双审核被 transfer 二次校验兜底） — P3

- **级别**: P3（观察项；实际被 transfer_benefit 二次校验拦截，无数据危害；模式 ① 先查后改无锁第 N 处）
- **维度**: R4 并发补面（先查后改无锁模式，F-053 同类）
- **文件**: `backend/domain/admin/services/benefit_transfer_service.py:77-130`（approve L77-105/reject L106-130）
- **事实**:
  - approve（L80-86）：`query(BenefitTransferApplication).filter(id, is_deleted==0).first()`——**无 with_for_update**
  - `if app.status != 0: raise "申请已处理"`（L87-89）——无锁状态守卫（先查后改）
  - 并发双审核：两审核员同时读 app.status=0 → 都过守卫 → 都调 `transfer_benefit`（L91，child 域带锁）→ 第二次 transfer_benefit 的 `_validate_transfer`（R35 已核：source 已 EXPIRED → "源孩子状态不允许转让" ValidationError）→ **第二个事务抛异常回滚** → 数据一致
  - **依赖 transfer_benefit 的二次校验兜底**（间接防护）；app 层自身无锁（若 transfer 校验不拦截则双执行双提交——当前校验链完整故安全）
  - reject（L106-130）同构（无锁 + status 守卫）
- **证据**: ① benefit_transfer_service.py:80-89 approve 无锁；② R35 已核 _validate_transfer 拦截（source EXPIRED）；③ 排重 grep：findings 无 benefit_transfer 审核并发命中；F-053（cancel_order 无锁）为同模式先例
- **触发**: 两名审核员并发审核同一权益转移申请（管理端双端操作）→ 第二个 transfer 校验拦截回滚
- **影响**: 无实际数据危害（transfer_benefit 二次校验兜底）；并发双审核时第二个请求报错（"源孩子状态不允许转让"——错误信息对审核员不直观）。P3 观察
- **建议**: ① approve/reject 的 app 查询加 `with_for_update()`（对齐 F-053 修复模式——行锁串行化，第二个等待后看到 status=1 拒绝）；② 或条件 UPDATE `WHERE id AND status=0` 按 affected==1 判定
- **排重**: 已 grep 确认不在 F-001~077 / C-001~133 中；F-053（cancel_order 无锁）为同模式先例；R35（transfer 校验链）为本项兜底依赖

---

## [C-20260808-134] 审核链其余面（状态守卫/权限/记录） — clean

- **方法**: R41 定向纵深。读 benefit_transfer_service.py 全（get_list/approve/reject）+ admin_benefit_transfer_router（权限）+ ChildService.transfer_benefit（R35 已核）+ 排重
- **证据**:
  - **状态守卫**：app.status != 0 → "申请已处理"（防重复审核）✓（F-078 为无锁版本，被 transfer 兜底）
  - **transfer 二次校验**：approve 调 ChildService.transfer_benefit（R35 已核 _validate_transfer 全维校验）——双执行被拦截 ✓
  - **权限**：admin_benefit_transfer_router require_perm（benefit_transfer.approve/reject，R11 已核 152 端点）✓
  - **审核留痕**：reviewer_id/review_remark/reviewed_at 落库 ✓
  - **状态语义**：0=PENDING/1=APPROVED/2=REJECTED ✓
- **排重**: R41 本轮审核链 clean 侧（F-078 无锁为唯一缺口）；R35（transfer 校验链）互补

---

## R41 完结汇总

- **范围**: benefit_transfer 管理端审核链（approve/reject/状态守卫/权限）
- **结果**: 发现 1 项（F-078 P3 无锁读-改-写）+ clean 1 项（C-134）
- **关键结论**:
  - 审核链工程正常（状态守卫/权限/留痕/transfer 二次校验兜底）
  - 唯一缺口：approve/reject 无 with_for_update（先查后改无锁，F-053 同模式）——实际被 transfer 校验兜底，无数据危害；修复成本低（app 加行锁）
  - 模式 ①（先查后改无锁）第 N 处：F-053/F-058/F-066/F-075/F-076/F-078 已识别
- **累计**: 77 发现（P0:0 / P1:0 / P2:11 / P3:66）+ 131 clean 记录
- **提交**: 见 git log（本轮 rounds/R41 文件 + progress 索引同步更新）
- **R41 收尾结论**: 四十一轮共 77 项发现无 P0/P1；11 项 P2（含 F-077）。R42 候选：继续轮转新面。
