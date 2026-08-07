# R32 第三十二轮 refund 域补面 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：C-125 起（本轮零发现）。

## 范围

R32 refund 域补面（F-002/005/006/009/016/031 + C-010/011 已审）。本轮换面：apply_refund 校验链
（归属/防重/年度限次/亲子课/未还书/罚款抵扣/自动审核）+ audit_refund（审核守卫/锁）+ 执行链复核对。

## 结果

- **发现 0 项**
- **clean 1 项**：C-125 refund 域补面整体安全（apply 校验链 + audit 守卫 + 金额口径）

---

## [C-20260808-125] refund 域（apply 校验链/audit 守卫/金额口径） — clean

- **方法**: R32 定向纵深。读 refund/service.py 关键段（apply_refund L37-177/audit_refund L178-217/_execute_wechat_refund L218-296/_rollback_refund_failure L297-337/mark_refunded L338-398/handle_refund_failed L399-448/_calculate L449-473）+ 排重对照
- **证据**:
  - **apply_refund 校验链**（L37-177）：order with_for_update + 归属 + PAID 守卫 + assert_no_pending_transfer + 防重（PENDING 已有拒）with_for_update + P2-7 年度限次（365 天 F25 闰年安全，APPROVED/COMPLETED 计数防循环退款 F51）+ B3 亲子课时间 + P0 未还书拦截 ✓ 全链完整
  - **金额服务端计算**：used_days 服务端算（L128，不信任前端）+ _calculate（R5 C-011 已审公式一致）+ E7 罚款抵扣（min(refund, outstanding)）+ F75-② 原额落库 + fine_deducted 分列 ✓
  - **E1 小额自动审核**：final_amount ≤ refund_auto_approve_max（默认 500）自动 APPROVED + order.refund_status=1 ✓
  - **audit_refund**（L178-217）：refund with_for_update + PENDING 守卫（防双重审批）+ 通过时 order with_for_update + refund_status=1 + F38 out_refund_no 兜底 ✓
  - **执行链**：_execute_wechat_refund/_rollback_refund_failure/mark_refunded/handle_refund_failed——F-002（回退无锁）/F-005（取消时序）/F-016（软删）/F-031（乱序覆盖）已报排重；F38 out_refund_no 幂等键防重复打款 ✓
  - **out_refund_no**：申请时生成（F38 重试复用）✓
- **排重**: R32 本轮 refund 域 clean 侧（零新缺陷）；F-002/005/006/009/016/031 已报不重；C-010/011（回调/公式）互补

---

## R32 完结汇总

- **范围**: refund 域补面（apply 校验链/audit 守卫/金额口径）
- **结果**: 发现 0 项 + clean 1 项（C-125）
- **关键结论**:
  - refund 域工程质量高：apply 校验链完整（归属/防重/年度限次/亲子课/未还书/罚款抵扣）、audit 行锁守卫、金额服务端计算 + 分列落库
  - 经 R1-R3（状态机）+ R5（公式）+ R32（复核对）多轮核查，refund 面彻底
  - 本轮为合法零发现（铁律 3）
- **累计**: 75 发现（P0:0 / P1:0 / P2:10 / P3:65）+ 122 clean 记录
- **提交**: 见 git log（本轮 rounds/R32 文件 + progress 索引同步更新）
- **R32 收尾结论**: 三十二轮共 75 项发现无 P0/P1；10 项 P2 全部未修。R33 候选：综合异常路径（全局异常处理/500 兜底/错误消息）或继续轮转新面。
