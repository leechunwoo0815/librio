# R60 第六十轮 mark_overdue_books 任务复核对 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：C-153 起（本轮零发现）。

## 范围

R60 mark_overdue_books 任务复核对（R5 F-047/055 公式面已审）。本轮：任务状态机（BORROWING→OVERDUE）、
F58 锁守卫在位性、按日累计、与还书并发。

## 结果

- **发现 0 项**
- **clean 1 项**：C-153 mark_overdue_books 复核对安全（F58 守卫在位 + 公式统一）

---

## [C-20260808-153] mark_overdue_books（F58 锁守卫/状态机/累计） — clean

- **方法**: R60 定向纵深。读 scheduler.py:1538-1651（mark_overdue_books 全——新逾期/已逾期两段）+ fine_policy
  对照（R5 已审）+ 排重
- **证据**:
  - **F58 守卫在位**：新逾期（L1562-1574）与已逾期（L1600-1610）均逐条 with_for_update 重取 + 状态守卫
    （防还书并发把 RETURNED 覆盖回 OVERDUE）✓
  - **状态机**：BORROWING→OVERDUE（新逾期）+ OVERDUE 按日累计 ✓
  - **公式统一**：apply_fine/calc_overdue_days/get_overdue_policy（fine_policy 单一实现，R5 已审公式/首次免罚/
    上限/宽限）✓
  - **分布式锁**：@distributed_lock("job:mark_overdue_books", timeout=600) ✓
  - **F-047（is_first_overdue 免罚竞态）**：R5 已报（任务×还书跨事务）排重 ✓
  - **F-055（宽限期零罚款消耗免罚额度）**：R5 已报排重 ✓
- **排重**: R60 本轮任务复核对 clean 侧（零新缺陷）；F-047/F-055 已报不重

---

## R60 完结汇总

- **范围**: mark_overdue_books 任务（状态机/F58 守卫/累计）
- **结果**: 发现 0 项 + clean 1 项（C-153）
- **关键结论**:
  - mark_overdue_books F58 锁守卫在位（防还书并发覆盖），状态机/公式/累计正确
  - R5 已充分覆盖公式面（F-047/F-055），本轮复核对确认无退化
  - 本轮为合法零发现（铁律 3）
- **累计**: 84 发现（P0:0 / P1:0 / P2:13 / P3:71）+ 150 clean 记录
- **提交**: 见 git log（本轮 rounds/R60 文件 + progress 索引同步更新）
- **R60 收尾结论**: 六十轮共 84 项发现无 P0/P1；13 项 P2。R61 候选：继续轮转新面。
