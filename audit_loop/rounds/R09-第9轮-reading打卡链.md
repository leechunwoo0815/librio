# R09 第九轮 reading 打卡链 — 审查报告（2026-08-07，历史轮次拆分）

> 本文件由 audit_loop/findings-20260807.md 按轮次拆分而来（用户指令统一形式）。
> 编号范围：F-059~060 / C-102；完整累计统计见 audit_loop/progress.md。

## R9 第九轮 reading 打卡链纵深 完结汇总（2026-08-08）

- **范围**: 用户选择"继续新维度"（R8 完结时建议路线）。R9 深挖 reading service（595 行）打卡/进度/会话/录音全链：save_progress / start_session / end_session / _check_auto_checkin / _check_voice_checkin / _check_finish_book_checkin / save_recording / get_streak / get_checkin_calendar + streak 事件链（misc_handlers）+ 统计链（reading_handlers/child service）+ CheckIn/ReadingProgress 唯一约束。
- **结果**: 发现 2 项（**F-059 P3** end_session 重复结算时长膨胀 / **F-060 P3** 试读页数限制单次 end 绕过）+ clean 1 项（C-102 reading 打卡链锁+唯一约束完整）。
- **关键结论**:
  - **打卡链并发防护完整**（C-102）：save_progress 双行锁 + submission 防重、end_session 行锁、三处打卡全部 add_with_unique_fallback + 唯一约束 + 每日上限、streak 幂等重算 + Child 行锁、全勤消息幂等——打卡/进度/streak 面干净
  - **end_session 缺状态守卫**（F-059）：end_time 已存在仍可重复调用 → duration 随 end_time 后移膨胀 + 每次发布事件 → total_reading_minutes 重复累计（handler 无幂等守卫，网络重试/前端重复提交即触发）
  - **试读限制只查 start 历史累计、end 无上限无复核**（F-060）：EndSessionRequest.pages_read 无 Field 上限，试读用户单次 end 传任意页数即突破 trial_pages 付费墙
- **累计**: 59 发现（P0:0 / P1:0 / P2:10 / P3:49）+ 99 clean 记录（C-001~C-102 实有 99 条）
- **R9 提交**: 见 git log（findings + progress 同步更新）
- **R9 收尾结论**: 九轮共 59 项发现无 P0/P1；10 项 P2 全部未修。F-057（答案泄漏）仍为优先修复项（低成本高影响）。剩余未深挖大 service：report 759 行只读链（建议 R10 候选）；或对 P2 修复后复验。F-059 修复成本极低（end_session 加状态守卫），可与 F-057 一并纳入修复批次。
