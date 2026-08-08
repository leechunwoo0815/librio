# R63 第六十三轮 scan_and_borrow 条码借书复核对 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-086 起 / C-156 起。

## 范围

R63 scan_and_borrow 条码借书复核对（R31 已审 borrow_book，本条码路径）。条码查重、自动建书+副本、
库存原子递增、barcode 唯一约束。

## 结果

- **发现 1 项**：F-086（P3）BookCopy.barcode 无唯一约束——并发扫码新条码双建副本（库存双计）
- **clean 1 项**：C-156 条码借书其余面正常（必填校验/原子递增/复用 borrow_book）

---

## [F-20260808-086] BookCopy.barcode 无唯一约束——并发扫码新条码双建副本（同 barcode 双记录 + 库存双计） — P3

- **级别**: P3（观察项；扫码低频 + 并发窗口极窄；无资金/安全，库存次日 reconcile 自愈）
- **维度**: R4 并发补面（先查后插无唯一约束模式，F-066/075/076 同类）
- **文件**: `backend/domain/book/models.py:90-91`（BookCopy.barcode 无 UniqueConstraint）/ `backend/domain/borrow/service.py:306-360`（scan_and_borrow 先查后插）
- **事实**:
  - BookCopy 注释"通过条码唯一标识"（models.py:86）但 `__table_args__` 空（L91）——**barcode 无唯一约束**
  - scan_and_borrow（L306-315）：查 `BookCopy.barcode == barcode` 无则建 copy（L334-347）——先查后插无 DB 兜底
  - **并发**：两扫码枪同时扫新条码（双请求查无 copy）→ 双建 BookCopy（同 barcode）+ 各库存 +1（total+2）→ **双副本记录 + 库存双计**
  - 库存次日 reconcile_stock 自愈（R1 C-025 已确认）；同 barcode 双 copy 残留（后续借书任一，另一条码记录冗余）
- **证据**: ① models.py:91 无 UniqueConstraint；② borrow/service.py:306-347 先查后插；③ 排重 grep：findings 无"barcode 唯一"命中；F-066/075/076（先查后插无唯一约束）为同模式先例
- **触发**: 两名店员同时扫码同一新条码（首次入库）→ 双副本
- **影响**: 同 barcode 双 BookCopy 记录（冗余）+ 库存双计（次日自愈）；无资金/安全。扫码低频 + 窗口极窄，P3 观察
- **建议**: ① BookCopy.barcode 加 UniqueConstraint（DB 兜底）；② 或 scan_and_borrow 的 barcode 查询加 with_for_update（行锁串行）；③ 或 IntegrityError 兜底（参照 R30 create_word 模式）
- **排重**: 已 grep 确认不在 F-001~085 / C-001~155 中；F-066/075/076（先查后插）为同模式；F-001/004（book 库存无锁）不同面

---

## [C-20260808-156] 条码借书其余面（必填校验/原子递增/复用） — clean

- **方法**: R63 定向纵深。读 borrow/service.py:298-382（scan_and_borrow 全）+ book/models.py + 排重
- **证据**:
  - **新书必填校验**：title/author/isbn/ar_value/age_min/age_max 全给才建书（L320-324）✓
  - **同 ISBN 复用**：isbn 查已有 Book（L328-332）✓（Book.isbn unique，R25 已核）
  - **库存原子递增**：total+1/available+1 SQL 更新（L351-359）✓
  - **F47**：NOT NULL 列显式写入（L335-343）✓
  - **复用 borrow_book**：校验链（上限/副本/库存/押金，R31 已核）✓
  - **条码存在路径**：直接借（L309-313）✓
- **排重**: R63 本轮条码面 clean 侧（F-086 barcode 唯一约束为唯一缺口）

---

## R63 完结汇总

- **范围**: scan_and_borrow 条码借书（查重/建书/库存/复用）
- **结果**: 发现 1 项（F-086 P3 barcode 无唯一约束）+ clean 1 项（C-156）
- **关键结论**:
  - 条码借书工程正常（必填校验/ISBN 复用/原子递增/复用 borrow_book）
  - 唯一缺口：BookCopy.barcode 无唯一约束（并发扫码双建副本）——先查后插家族第 4 处（F-066/075/076/086）；修复成本低（加 UniqueConstraint）
- **累计**: 85 发现（P0:0 / P1:0 / P2:13 / P3:72）+ 153 clean 记录
- **提交**: 见 git log（本轮 rounds/R63 文件 + progress 索引同步更新）
- **R63 收尾结论**: 六十三轮共 85 项发现无 P0/P1；13 项 P2。R64 候选：继续轮转新面。
