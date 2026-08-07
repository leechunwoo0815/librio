# R10 第十轮 report 只读链纵深 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件，不再追加到 findings-20260807.md。
> 编号延续：F-061 起（F-001~060 在 findings-20260807.md）；C-103 起（C-001~102 在 findings-20260807.md）。
> 累计口径见 progress.md「当前进度」。

## 范围

用户选择"继续新维度"（R9 完结建议路线：report 759 行只读链）。R10 深挖 report service（759 行）：
观察期报告生成/查看/评语/HTML/PDF、阅读统计（summary/today/trend/weekly/monthly）、双入口
（scheduler 定时 + admin 手动）生成链路。选择理由：R8 完结时 report 759 行只读链为剩余最大
未深挖 service；F-042（mark_viewed IDOR）已报，本轮验证其修复状态并排查 report 域其他缺口。

## 结果

- **发现 1 项**：F-061（P3）generate_due_reports 双入口并发双生成
- **clean 1 项**：C-103 report 只读链整体安全

---

## [F-20260808-061] generate_due_reports 双入口并发双生成（scheduler 持锁 / admin 手动无锁） — P3

- **级别**: P3（观察项；需 admin 手动与定时任务并发或两 admin 并发才触发，低频）
- **维度**: 7.1 定时任务×6.3 管理后台接缝（交叉维度）
- **文件**: `backend/domain/report/service.py:135-203`（generate_due_reports）/ `backend/tasks/scheduler.py:1659-1710`（check_observation_expiry，@distributed_lock）/ `backend/domain/admin/routers/admin_reports_router.py:122-133`（POST /reports/observation/generate）/ `backend/domain/report/models.py:20-31`（ObservationReport 无 child_id 唯一约束）
- **事实**:
  - scheduler 入口 `check_observation_expiry` 带 `@distributed_lock("job:check_observation_expiry", timeout=600)`（Redis SET NX EX），任务内查 `existing_report_ids`（L1685-1688）→ 调 `generate_due_reports()` → 内部**再次**查 `existing_report_ids`（service.py:152-157）→ 逐孩生成 + commit
  - admin 手动入口 `POST /reports/observation/generate`（require_perm("report.generate")）**直接调 `service.generate_due_reports()`，不获取 `job:check_observation_expiry` 分布式锁**
  - `ObservationReport` 模型（models.py:20-31）`child_id` 仅 `index=True`，**无 UniqueConstraint(child_id)**——DB 层无防重兜底
  - generate_due_reports 内部 `existing_report_ids` 为事务开始时的快照（L152-157），循环内生成成功即 commit（service.py:331-332）
- **证据**: ① `grep distributed_lock` 确认 scheduler 任务持锁、admin router 无锁调用（两处调用点代码已读）；② `models.py:24` `child_id = Column(BigInteger, ForeignKey("child.id"), nullable=False, index=True)` 无唯一约束；③ 排重 grep：findings 全文件无"双入口/重复生成/并发生成"命中，F-014/F-015 为 purge 分批与日期索引失效，不同面
- **触发**: scheduler 每日 9:30 check_observation_expiry 与运营同时点击"生成到期观察期报告"，或两名运营同时点击 → 两事务各自查 existing_report_ids（均空）→ 各自为同一批到期孩子生成报告 → 双份 ObservationReport
- **影响**: 同一孩子生成两份观察期报告（冗余数据）。展示端 detail/HTML/PDF 取 `order_by(id.desc()).first()`（service.py:106-107）仍读到最新一份，业务可见影响有限；运营侧"生成报告数"统计虚高；无资金/安全影响。SQLite 下并发需进程级同时执行，MySQL 下两连接并发成立
- **建议**: ① admin 手动入口复用 `@distributed_lock("job:check_observation_expiry")` 或引入独立锁 `job:report_generate`；② 或给 `ObservationReport.child_id` 加 UniqueConstraint 作 DB 兜底（需处理"同孩子多份历史报告"存量——若允许重生成则改唯一约束为应用层防重）；③ 或 generate_due_reports 循环内用 `SELECT ... FOR UPDATE` 串行化 existing 判定
- **排重**: 已 grep 确认不在 F-001~060 / C-001~102 中；F-042（mark_viewed IDOR）不涉生成链路；F-014/F-015（定时任务维度）不涉

---

## [C-20260808-103] report 只读链整体安全（端点校验 + HTML 转义 + 统计口径） — clean

- **方法**: R10 定向纵深。读 ReportService 全 759 行（get_observation_report/get_observation_report_detail/generate_due_reports/_generate_for_child/mark_observation_viewed/add_teacher_comment/render_report_html/render_report_pdf/get_summary/get_today_stats/get_trend/generate_weekly_report/generate_monthly_report）+ router.py 全 163 行 + models.py/repository.py/schemas.py + scheduler 调用点 + admin router 调用点 + distributed_lock 实现
- **证据**:
  - **端点校验完整**：stats 四端点 + observation detail/HTML/PDF + learning 全部 `GetOwnedChild`/`GetOwnedChildFromQuery`（router.py:34/43/53/63/72/83/95/125/140/159）✓；add_teacher_comment 用 `require_perm("report.comment")`（router.py:117）✓；mark_viewed 缺校验已由 F-042（R3）覆盖，排重不重报
  - **HTML 渲染安全**：Jinja2 `Environment(autoescape=select_autoescape(default=True, default_for_string=True))`（service.py:413-415）——child_name/teacher_comment/cta_text 全部自动转义，无存储型 XSS ✓
  - **PDF 异步线程**：`asyncio.to_thread(svc.render_pdf, html)`（service.py:453）不阻塞事件循环 ✓
  - **统计口径**：get_summary/today/trend/weekly/monthly 全部单孩子过滤（child_id ==）✓；days 参数 `Query(7, ge=1, le=90)` 上限（router.py:51）✓；ReadingSession 无软删调用点（grep 确认 soft_delete 调用集中在 teacher/venue/book/child/vocab/cert，无 ReadingSession）→ get_summary 等缺 is_deleted 过滤无实际影响（恒 0），不报
  - **generate_due_reports 异常隔离**：per-child try/except（service.py:166-200）+ 失败留 OBSERVATION 下轮重试 + SystemMessage 7 天去重告警（F31 模式）✓
  - **F14 口径**：到期判定统一 member_expire_time 单口径（service.py:139-148）✓；_generate_for_child 用 member_start_time 作观察起点（F14 为到期口径，不冲突）✓
  - **level_at_end 查询**：ChildLevel is_current → Level 名称（service.py:260-271），无权限/越权面 ✓
- **排重**: R10 本轮 report 面 clean 侧（F-061 双入口并发为唯一缺口）；F-042（R3 viewed IDOR）已报不重报；F-026（题库搜索无 limit）不涉

---

## R10 完结汇总

- **范围**: report 759 行只读链（观察期报告生成/查看/评语/HTML/PDF + 阅读统计 + 双入口生成链路）
- **结果**: 发现 1 项（F-061 P3 双入口并发双生成）+ clean 1 项（C-103）
- **关键结论**:
  - report 域整体安全：端点校验齐全、HTML 自动转义、统计单孩子口径、异常 per-child 隔离
  - 唯一结构性缺口：generate_due_reports 双入口（scheduler 持锁 / admin 无锁）无 DB 唯一约束兜底，并发双生成。触发概率低（需并发点击或与定时任务撞车），但修复成本低（admin 入口复用分布式锁）
  - mark_viewed 越权（F-042）为 R3 已知项，本轮验证仍在（未修）
- **累计**: 60 发现（P0:0 / P1:0 / P2:10 / P3:50）+ 100 clean 记录
- **提交**: 见 git log（本轮 rounds/R10 文件 + progress 索引同步更新）
- **R10 收尾结论**: 十轮共 60 项发现无 P0/P1；10 项 P2 全部未修（F-042 viewed IDOR / F-053 cancel_order 无锁 / F-025 N+1 等）。R11 候选：管理后台补面（权限码/全局泄漏/事件绑定，维度 6 第二轮）。
