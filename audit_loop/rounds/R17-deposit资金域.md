# R17 第十七轮 deposit 资金域补面（罚款支付链）— 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-066 起 / C-110 起。

## 范围

R17 deposit 资金域补面。R1（F-005/006 状态机）、R4（F-053/054 并发）、R5（退款公式 F-055）、R2（F-030
网关失败覆盖、F-033 int 截断）、X.4（F-048 回调 trade_state）已审。本轮换面（R6 完结标注"deposit 1045 行
未深挖"）：罚款支付链（pay_fines/_settle_fine_payment/reset_stale_pending_deposits）+ 资金操作链
（deduct_deposit/mark_book_lost/partial_refund_deposit）的锁覆盖与金额处理复查。

## 结果

- **发现 1 项**：F-066（P3）pay_fines 并发双缴款单（先查后插无唯一约束，双单都支付则多收罚款）
- **clean 1 项**：C-110 deposit 资金链整体健康（deduct/mark_book_lost/partial_refund/settle 锁与金额正确）

---

## [F-20260808-066] pay_fines 先查后插无唯一约束——并发双缴款单，双单均支付则多收罚款 — P3

- **级别**: P3（观察项；需 MySQL 并发 + 用户双端同时操作才触发；SQLite 串行下第二请求复用 pending）
- **维度**: R4 并发×资金补面（Y.2 押金路径同类漏改）
- **文件**: `backend/domain/deposit/service.py:851-870`（pay_fines 防重）/ `backend/domain/deposit/models.py:97-105`（FinePayment 无唯一约束）
- **事实**:
  - `pay_fines`（L851-870）防重逻辑：查 `FinePayment(child_id, status==PENDING, amount==outstanding)`（L853-860）→ 有则复用，无则新建（L862-870）——**先查后插无 DB 唯一约束兜底**（FinePayment `__table_args__` 空，models.py:101）
  - 并发场景：两请求同时读 outstanding=100 → 同时查 pending（均空）→ 各建 FinePayment A/B（金额 100）→ 用户双端各支付 A/B → 各 _settle_fine_payment（A settle 后 outstanding 100→0；B settle 时 max(0, 0-100)=0）→ **家长实付 200 元，罚款只 100 元，多收 100 无退款路径**
  - child 查询（L839-843）无 with_for_update——读 outstanding 无锁（但 settle 有锁 + max 兜底，单点无资金损失；组合成双单问题）
  - `reset_stale_pending_deposits`（L983-998）已清理超时 PENDING 缴款单（注释明确"P3 观察项闭环"）——残留单会被清理，但**已支付的双单无法被清理/退款**
- **证据**: ① service.py:851-870 先查后插代码；② models.py:101 `__table_args__ = {"extend_existing": True}` 无 UniqueConstraint；③ 排重 grep：findings 无 pay_fines/FinePayment 命中；F-053（cancel_order 先查后改无锁）为订单域同模式，本项为押金罚款域新面
- **触发**: 同一孩子的罚款缴款并发请求（双端同时点"缴纳罚款"）→ MySQL 下两事务同时通过 pending 查重 → 双缴款单 → 用户两个都支付（支付页无单号互斥提示）
- **影响**: 多收罚款（家长付两次 100 元，实际罚款 100）——需人工退款；无系统资金损失（款项入账正确，多收部分在账上）。窗口极窄（MySQL 并发 + 双端操作），P3 观察
- **建议**: ① FinePayment 加唯一约束 `(child_id, status, amount)` 或应用层 `SELECT ... FOR UPDATE` 串行化 pending 查重（对齐 F-053 修复模式：条件 UPDATE 或行锁重取）；② 或 settle 时校验"缴款单金额 ≤ 当前 outstanding"（B 单 settle 时 outstanding 已 0 → 拒绝并提示退款）；③ 前端支付页对同 child 的 pending 单互斥提示
- **排重**: 已 grep 确认不在 F-001~065 / C-001~109 中；F-053（cancel_order）/F-058（review_submission）为同模式不同域；reset 任务注释提及的"P3 残留单"为**残留清理**面，本项为**并发双单**面，不同

---

## [C-20260808-110] deposit 资金操作链（deduct/mark_book_lost/partial_refund/settle） — clean

- **方法**: R17 定向纵深。读 deposit/service.py 全 1045 行关键段：deduct_deposit（L415-453）/mark_book_lost（L454-521）/partial_refund_deposit（L724-830）/pay_fines（L831-908）/_settle_fine_payment（L934-955）/reset_stale_pending_deposits（L956-999）+ FinePayment/DepositRecord 模型
- **证据**:
  - **deduct_deposit**（L415-453）：get_active_by_child_for_update 行锁 + PAID 守卫 + `min(amount, record.amount)` 扣款封顶 + 超额记 outstanding_fines + child 行锁 ✓
  - **mark_book_lost**（L454-521）：BorrowRecord with_for_update + 状态守卫（仅 BORROWING/OVERDUE）+ Decimal 罚款计算（book_price × multiplier）+ child 行锁 + outstanding 差额增量（F61 模式）+ BookCopy 条件 UPDATE + book.total_stock max 减 1（F-001/F-004 已报无锁，排重）✓
  - **partial_refund_deposit**（L724-830）：行锁 + PAID 守卫 + 限一次（partial_refunded）+ 借满 N 本无逾期校验 + Phase 1 落库 commit 释放锁 → Phase 2 事务外调网关 → 失败回滚标记（L797-805 with_for_update 重取回滚）✓ 设计良好
  - **_settle_fine_payment**（L934-955）：child with_for_update + `max(0, outstanding - paid)` 归零兜底 ✓
  - **reset_stale_pending_deposits**（L956-999）：超时 PENDING 押金复位 UNPAID（F39）+ 超时 PENDING 罚款单软删（P3 闭环）✓
  - **金额精度**：全链 Decimal（refund_amt/outstanding/fine_amount）+ yuan_to_cents 转换（partial_refund L782-785）+ calc_fine quantize ROUND_HALF_UP（来源保证 2 位小数 → pay_fines int(×100) 截断无害）✓ F-033 为 config 来源面已报
- **排重**: R17 本轮 deposit 资金链 clean 侧（F-066 并发双单为唯一缺口）；F-001/004（book 无锁）、F-030（网关失败）、F-033（int 截断）、F-048（回调 trade_state）、F-053/054（R4 并发）已报不重

---

## R17 完结汇总

- **范围**: deposit 资金域补面（罚款支付链 + 资金操作链）
- **结果**: 发现 1 项（F-066 P3 pay_fines 并发双单）+ clean 1 项（C-110 资金链健康）
- **关键结论**:
  - deposit 资金链工程质量高：deduct/partial_refund/settle 全带锁 + 金额 Decimal + 封顶/兜底/回滚机制齐全
  - 唯一缺口：pay_fines 先查后插无唯一约束（FinePayment）——并发双单双支付多收罚款；窗口极窄（MySQL 并发 + 双端操作），但修复成本低（加唯一约束或 settle 校验）
  - mark_book_lost 的 book.total_stock 无锁为 F-001 已报（排重不重报）
- **累计**: 65 发现（P0:0 / P1:0 / P2:10 / P3:55）+ 107 clean 记录
- **提交**: 见 git log（本轮 rounds/R17 文件 + progress 索引同步更新）
- **R17 收尾结论**: 十七轮共 65 项发现无 P0/P1；10 项 P2 全部未修。R18 候选：订单域补面（order 764 行 R6 标注未深挖——会员订单链/亲子课报名/退款审核，本轮换面：订单金额与会员期计算）。
