# R40 第四十轮 reservation 预约域补面 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：C-133 起（本轮零发现）。

## 范围

R40 reservation 预约域补面（R6 F-056 候补/C-099 锁分层已审）。本轮换面：预约创建/取消业务链
（create_reservation/cancel_reservation/expire_reservation/join_waitlist/cancel_waitlist/
notify_next_waiter）——防重、守卫、候补闭环。

## 结果

- **发现 0 项**
- **clean 1 项**：C-133 预约域补面整体安全（create 防重 + cancel 守卫 + 候补闭环）

---

## [C-20260808-133] 预约域（创建防重/取消守卫/候补闭环） — clean

- **方法**: R40 定向纵深。读 reservation/service.py 关键段（create_reservation L48-129/fulfill_reservation
  L130-261/expire_reservation L262-297/join_waitlist L326-380/cancel_waitlist L381-413/
  _fulfill_waitlist L450-462/notify_next_waiter L463-515/cancel_reservation L516-575）+ 排重
- **证据**:
  - **create_reservation**（L48-129）：book with_for_update（L50-54）串行化——**间接防并发重复预约**（第二事务等待后看到 existing）✓ + offline_available/库存校验 + F46 未还书拦截（L88-100）+ expire_time 配置化 + _fulfill_waitlist 候补闭环 ✓
  - **cancel_reservation**（L516-575）：with_for_update + PENDING 守卫（F40 防双重释放，L535-538）+ user 归属校验（L540-547）+ **条件 UPDATE affected==1 判定**（L543-550，F-053 修复模式同款）✓
  - **expire_reservation**：状态守卫（F-046 周边，R2 已审 scheduler）✓
  - **候补**：join_waitlist/cancel_waitlist/_fulfill_waitlist/notify_next_waiter——F-056（NOTIFIED 无回归）已报，C-099（锁分层）已审 ✓
  - **fulfill_reservation**：取书校验链（C-099 已核借阅上限权威校验）✓
  - **事件**：ReservationCreated/CancelledEvent（C-109 已审重放）✓
- **排重**: R40 本轮预约域 clean 侧（零新缺陷）；F-056/C-099 已报不重

---

## R40 完结汇总

- **范围**: reservation 预约域补面（创建/取消/候补/过期）
- **结果**: 发现 0 项 + clean 1 项（C-133）
- **关键结论**:
  - 预约域工程质量高：book 行锁间接防重、cancel 条件 UPDATE 守卫、候补闭环、F40 双重释放防护
  - 经 R6（C-099）+ R40（业务链）两轮核查，预约面彻底
  - 本轮为合法零发现（铁律 3）
- **累计**: 76 发现（P0:0 / P1:0 / P2:11 / P3:65）+ 130 clean 记录
- **提交**: 见 git log（本轮 rounds/R40 文件 + progress 索引同步更新）
- **R40 收尾结论**: 四十轮共 76 项发现无 P0/P1；11 项 P2（含 F-077）。R41 候选：继续轮转新面。
