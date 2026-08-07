# librio 循环审查进度（DeepSeek v4 flash · 2026-08-07 起）

> 恢复口令："读 专家意见/项目终态交接-20260807.md 和 audit_loop/progress.md，继续。"
> 指令：专家意见/无限循环审查指令-opencode.md（15 维轮换 / 五铁律 / 只报不修）
> 恢复卡：专家意见/项目终态交接-20260807.md（HEAD=566d100，pytest 730 / behave 211 / ruff 442）

## 审查轮次总览

| 轮次 | 日期 | 维度子项 | 发现 | P1+ | 备注 |
|------|------|----------|------|-----|------|
| R1 | 2026-08-07 | 1.1 commit 后写操作 | 0 | 0 | clean（4 可疑全排除） |
| R1 | 2026-08-07 | 1.2 先查后改行锁 | 4 | 0 | 3×P2 + 1×P3观察（total_stock 聚合） |
| R1 | 2026-08-07 | 1.3 事件 handler 自 commit | 0 | 0 | clean（21 handler 无自 commit） |
| R1 | 2026-08-07 | 1.4 死信路径 | 0 | 0 | clean（异常隔离确认） |
| R1 | 2026-08-07 | 2.1 押金状态机 | 2 | 0 | F-005 cancel REFUNDING→PAID 时序缺口 + F-006 申请无前置 |
| R1 | 2026-08-07 | 2.2 五状态机矩阵 | 2 | 0 | F-007 回调终态无拦截 + F-008 FAILED 无出路（均 P3 观察） |
| R1 | 2026-08-07 | 2.3 前置校验完整性 | 0 | 0 | clean（并入 2.1/2.2 逐点核对） |
| R1 | 2026-08-07 | 3.1 金额 float 扫描 | 0 | 0 | clean（27 处 float 全非金额） |
| R1 | 2026-08-07 | 3.2 元/分转换点 | 0 | 0 | clean（无双重转换；deposit int(x*100) Decimal 安全） |
| R1 | 2026-08-07 | 3.3 支付/退款回调 | 0 | 0 | clean（幂等/签名/金额/状态前置全覆盖） |
| R1 | 2026-08-07 | 3.4 退款公式 | 1 | 0 | F-009 0 元退款单（P3 观察）；公式两处实现口径一致 |
| R1 | 2026-08-07 | 4.1 API 契约脚本 | 0 | 0 | clean（路径级 OK，脚本盲区：不查字段名） |
| R1 | 2026-08-07 | 4.2 api.js vs Schema | 0 | 0 | clean（抽查 12 个高频 payload 函数零 mismatch） |
| R1 | 2026-08-07 | 4.3 response_model 漏网 | 1 | 0 | F-010 16 端点缺契约（P3 观察）；无 ORM/敏感泄露 |
| R1 | 2026-08-07 | 5.1 data vs WXML 绑定 | 0 | 0 | clean（37 处链式访问全有守卫/初始化） |
| R1 | 2026-08-07 | 5.2 生命周期清理 | 1 | 0 | F-011 reader/vocabulary 音频无 destroy（P3 观察）；定时器全清理 |
| R1 | 2026-08-07 | 5.3 网络失败兜底 | 0 | 0 | clean（28:28 平衡，11 处候选全人工核实有兜底） |
| R1 | 2026-08-07 | 5.4 iOS 虚拟支付 | 0 | 0 | clean（5 支付入口全覆盖，无绕过路径） |
| R1 | 2026-08-07 | 6.1 inline script 泄漏 | 0 | 0 | clean（无 inline；formatDateTime 有意覆盖自洽） |
| R1 | 2026-08-07 | 6.2 innerHTML 注入 | 0 | 0 | clean（用户可控字段全 escape；4 处未 escape 均 int） |
| R1 | 2026-08-07 | 6.3 action wiring | 0 | 0 | clean（verify_action_wiring 全绿） |
| R1 | 2026-08-07 | 6.4 权限码 vs 种子 | 1 | 0 | F-012 11 个种子超集未接线（P3 观察）；双向零漏配 |
| R1 | 2026-08-07 | 7.1 失败路径/锁/幂等 | 1 | 0 | F-013 reset 任务无锁（P3，幂等）；23/24 有锁，全 try/except |
| R1 | 2026-08-07 | 7.2 时区边界 | 0 | 0 | clean（全应用侧 datetime，无 utcnow 混用） |
| R1 | 2026-08-07 | 7.3 大表风险 | 2 | 0 | F-014 purge 无分批 + F-015 date() 索引失效（均 P3） |
| R1 | 2026-08-07 | 7.4 9:00 错峰 | 0 | 0 | clean（两提醒任务均轻量） |
| R1 | 2026-08-07 | 8.1 慢查询基线 | 0 | 0 | clean（0 条；用户端 2 端点 401 未覆盖） |
| R1 | 2026-08-07 | 8.2 索引覆盖 | 0 | 0 | clean（高频列全有索引；低基数枚举无索引合理） |
| R1 | 2026-08-07 | 8.3 软删一致性 | 1 | 0 | F-016 refund 两处查询缺软删过滤（P3） |
| R1 | 2026-08-07 | 8.4 迁移漂移 | 0 | 0 | clean（alembic check + model consistency 均通过） |
| R1 | 2026-08-07 | 9.1 文档漂移 | 0 | 0 | clean（gen_config_doc --check 通过；level_of 66 键全覆盖） |
| R1 | 2026-08-07 | 9.2 fallback 漂移 | 1 | 0 | F-018 DEFAULTS 类型元数据漂移 4 键（P3） |
| R1 | 2026-08-07 | 9.3 TTL 缓存/审计 | 1 | 0 | F-017 ConfigAuditLog 生产零写入（P3）；缓存失效链完整 |
| R1 | 2026-08-07 | 10.1 反假绿脚本 | 0 | 0 | clean（check_fake_assertions 全通过） |
| R1 | 2026-08-07 | 10.2 断言业务含义 | 0 | 0 | clean（10 文件抽查；4 处 pass 全合法上下文） |
| R1 | 2026-08-07 | 10.3 behave 真实性 | 0 | 0 | clean（弱断言均有严格"拦截提示"兜底） |
| R1 | 2026-08-07 | 10.4 RED→GREEN | 1 | 0 | F-019 F12 幂等测试无 RED 守护（P3）；状态门正向对照转红 |
| R1 | 2026-08-07 | 11.1 敏感信息日志 | 1 | 0 | F-020 SMS phone 明文（P3）；高敏凭据零日志 clean |
| R1 | 2026-08-07 | 11.2 trace_id 贯穿 | 1 | 0 | F-021 业务/事件/任务链路断（P3）；中间件本身 clean |
| R1 | 2026-08-07 | 11.3 异常 exc_info | 1 | 0 | F-022 38 处 error 仅 4 带堆栈（P3） |
| R1 | 2026-08-07 | 12.1-12.4 安全 | 2 | 0 | F-023 upload_id 路径遍历 + F-024 delete_voice_files 穿越（均 P2） |
| R1 | 2026-08-07 | 13.1-13.3 性能 | 2 | 0 | F-025 child.user N+1 + F-026 题库搜索无 limit（均 P3） |
| R1 | 2026-08-07 | 14.1-14.3 合规 | 2 | 0 | F-027 隐私占位符 + F-028 reload=True（均 P3） |
| R1 | 2026-08-07 | 15.1-15.3 文档一致性 | 0 | 0 | 配置 66 键 / 表结构 52 表 / 基线 730+211 三零差异 |
| R2 | 2026-08-07 | 1~14 全维度换面（R2 攻击面升级） | 11 | 0 | F-034~044（4×P2 + 7×P3），C-072~086 |
| R2 | 2026-08-07 | 15.1 PRD 数字 vs 代码 | 1 | 0 | F-045 G+ 级书数 PRD 未定义（P3）+ C-087（30+ 项一致） |
| R2 | 2026-08-07 | 15.2 表结构 / 15.3 基线 | 0 | 0 | C-088（迁移 043-050 列级 diff）+ C-089（pytest 730/behave 211 无漂移） |
| R3 | 2026-08-07 | 交叉 X.1 定时任务×状态机 | 1 | 0 | F-046 定时任务直改状态绕过校验（P2） |
| R3 | 2026-08-07 | 交叉 X.2 定时任务×资金 | 1 | 0 | F-047 复核小计口径（P3）+ C-090 罚款公式跨路径一致 |
| R3 | 2026-08-07 | 交叉 X.3 配置×退款公式 | 0 | 0 | C-091 在途退款新旧值口径一致 |
| R3 | 2026-08-07 | 交叉 X.4 回调×状态机 | 1 | 0 | F-048 回调路径校验不等价（P3）+ C-092 |
| R3 | 2026-08-07 | 交叉 X.5 事件handler×金额 | 1 | 0 | F-050 事件金额同步约束（P3）+ C-094 |
| R3 | 2026-08-07 | 交叉 X.6 前端×API契约 | 1 | 0 | F-051 F4候补/F1换绑前端零入口（P3）+ C-095 契约全对齐 |
| R3 | 2026-08-07 | 交叉 X.7 权限×端点 | 1 | 0 | F-049 权限码接缝（P3）+ C-093 |
| R3 | 2026-08-07 | 交叉 X.8 测试×状态机 | 1 | 0 | F-052 FAILED 矩阵边无测试/ALUMNI 绕过矩阵（P3）+ C-096 |
| R4 | 2026-08-07 | 并发×资金 Y.1-Y.4 | 2 | 0 | F-053 cancel_order 无锁覆盖 PAID（P2）+ F-054 repay_deposit 仅拦 PAID（P3）+ C-097 |
| R5 | 2026-08-07 | 定时任务×资金纵深 Z.1-Z.3 | 1 | 0 | F-055 宽限期零罚款记录消耗首次免罚额度（P3）+ C-098 |
| R6 | 2026-08-07 | 借阅/预约并发面（R4 资金链未覆盖路径） | 1 | 0 | F-056 候补 NOTIFIED 无回归路径（P3）+ C-099 锁分层完整 |
| R7 | 2026-08-07 | 安全×文件链路纵深（F-023/024 同类枚举） | 0 | 0 | F-023 rmtree 删除面补充（不新建编号）+ C-100 文件操作点全枚举 |
| R8 | 2026-08-07 | 晋级链路（advancement）纵深 | 2 | 0 | F-057 取题端点泄漏 correct_answer（P3）+ F-058 审核无锁读-改-写（P3）+ C-101 |
| R9 | 2026-08-08 | reading 打卡链纵深（R8 建议路线） | 2 | 0 | F-059 end_session 重复结算时长膨胀（P3）+ F-060 试读页数限制单次 end 绕过（P3）+ C-102 |

## 维度轮换表（15 维，按序循环，深度递增）

- [x] 维度 1.1：commit 后写操作（R1 完成：clean，扫描脚本 scan_commit_after_write.py）
- [x] 维度 1.2：先查后改行锁（R1 完成：F-001/002/003/004 共 4 发现）
- [x] 维度 1.3：事件 handler 自 commit（R1 完成：clean）
- [x] 维度 1.4：死信路径（R1 完成：clean）
- [x] 维度 2.1：押金状态机（R1 完成：F-005/F-006 两缺口）
- [x] 维度 2.2：借阅/预约/订单/退款/会员 五状态机（R1 完成：F-007/F-008 P3 观察）
- [x] 维度 2.3：状态变更点前置校验完整性（R1 完成：并入 2.1/2.2）
- [x] 维度 3：资金安全（3.1 float clean / 3.2 元分 clean / 3.3 回调 clean / 3.4 公式一致 + F-009 P3 观察）
- [x] 维度 4：API 契约（4.1 脚本 clean / 4.2 字段名 clean / 4.3 F-010 契约缺口 P3 观察）
- [x] 维度 5：小程序端（5.1 clean / 5.2 F-011 音频泄漏 P3 / 5.3 clean / 5.4 clean）
- [x] 维度 6：管理后台（6.1-6.3 clean / 6.4 F-012 种子超集 P3 观察）
- [x] 维度 7：定时任务（7.1 F-013 无锁 P3 / 7.2 clean / 7.3 F-014+F-015 P3 / 7.4 clean）
- [x] 维度 8：数据库（8.1-8.2 clean / 8.3 F-016 软删过滤 P3 / 8.4 clean）
- [x] 维度 9：配置中心（9.1 clean / 9.2 F-018 类型漂移 P3 / 9.3 F-017 审计缺口 P3）
- [x] 维度 10：测试质量（10.1-10.3 clean / 10.4 F-019 幂等测试无 RED 守护 P3）
- [x] 维度 11：日志与可观测（11.1 F-020 phone 明文 / 11.2 F-021 trace 链路断 / 11.3 F-022 exc_info 缺失）
- [x] 维度 12：安全（12.1 LIKE 转义 clean / 12.2 越权差集 clean / 12.3 F-023 upload_id 路径遍历 + F-024 delete_voice_files 穿越 / 12.4 硬编码 clean）
- [ ] 维度 4：API 契约（4.1 verify_api_contract / 4.2 api.js vs Schema / 4.3 response_model）
- [ ] 维度 5：小程序端（5.1 data null / 5.2 清理 / 5.3 网络兜底 / 5.4 iOS 支付）
- [ ] 维度 6：管理后台（6.1 全局泄漏 / 6.2 innerHTML / 6.3 wiring / 6.4 权限码）
- [ ] 维度 7：定时任务（7.1 失败/锁/幂等 / 7.2 时区 / 7.3 大表 / 7.4 错峰）
- [ ] 维度 8：数据库（8.1 慢查询 / 8.2 索引 / 8.3 软删 / 8.4 迁移漂移）
- [ ] 维度 9：配置中心（9.1 gen_config_doc / 9.2 fallback / 9.3 TTL）
- [ ] 维度 10：测试质量（10.1 反假绿 / 10.2 抽样读 / 10.3 behave 真实 / 10.4 RED→GREEN）
- [ ] 维度 11：日志可观测（11.1 敏感信息 / 11.2 trace_id / 11.3 exc_info）
- [x] 维度 12：安全（12.1 escape_like clean / 12.2 越权差集 clean / 12.3 F-023+F-024 路径遍历 / 12.4 硬编码 clean）
- [x] 维度 13：性能（13.1 F-025 child.user N+1 P3 / 13.2 F-026 题库搜索无 limit P3 / 13.3 包体积 clean）
- [x] 维度 14：合规文案（14.1 极限词 clean / 14.2 F-027 隐私占位符 P3 / 14.3 F-028 reload=True P3）
- [x] 维度 15：文档一致性（15.1 配置 66 键零差异 / 15.2 表结构 52 表零差异 / 15.3 基线 730+211 一致）
- [x] R2 全维度换面（攻击面升级：并发/链路/故障注入视角，F-034~045 共 12 项、C-072~089 共 18 项）

## 当前进度

- **当前维度子项**：第九轮 reading 打卡链纵深 R9 完成（F-059 重复结算 + F-060 试读绕过 + C-102）→ R9 完结
- **本圈发现数**：2（R9：P3×2）
- **累计发现数**：59（P2×10 + P3×49 观察）+ 99 clean 记录
- **下次从哪开始**：R10 建议优先修 F-057（答案泄漏，低成本高影响）+ F-059（状态守卫）后复验；或继续新维度（report 759 行只读链）
- **上一圈结束时 HEAD**：待更新（R9 完结后为最新提交）

## 第三轮（R3）交叉维度接缝清单

1. 定时任务 × 状态机：scheduler 任务直接写状态字段、绕过 service 前置校验（reconcile/purge/damage confirm）→ ✓ F-046（P2）
2. 定时任务 × 资金：对账/核销任务中的金额计算与配置值口径 → ✓ C-090 + F-047（P3）
3. 配置 × 退款公式：配置键变更后，在途/历史退款计算用新值还是旧值（一致性）→ ✓ C-091
4. 支付回调 × 状态机：回调路径状态转移是否与 service 路径校验等价 → ✓ F-048（P3）+ C-092
5. 事件 handler × 金额：事件处理器中的金额/状态处理是否同步约束 → ✓ F-050（P3）+ C-094
6. 前端 × API 契约：小程序/管理端调用路径参数与后端 Schema 接缝（R2 F-042/043 周边）→ ✓ C-095 + F-051（P3）
7. 权限 × 端点：require_perm 与路由注册的接缝（新增端点漏权限码）→ ✓ F-049（P3）+ C-093
8. 测试 × 状态机：behave 场景状态转移 vs 代码状态机矩阵覆盖差集 → ✓ C-096 + F-052（P3）

**R3 完结**：8/8 项完成，发现 F-046~052（P2×1 + P3×6）+ clean C-090~096，累计 51 发现 / 93 clean，HEAD=745b8bc。汇总见 findings-20260807.md「R3 第三轮交叉维度 完结汇总」。

## 第四轮（R4）并发 × 资金接缝清单（P2 聚集区定向深挖）

> R3 完结建议：R4 从"并发×资金"接缝切入（P2 级最密集区域：行锁覆盖 + 定时任务×状态机）。

1. 订单支付路径：create→支付→回调→关闭 全链路锁覆盖与竞态窗口（先付后关 F-035 已修对照；FAILED/CLOSED 并发边界）→ ✓ F-053（P2）cancel_order 无锁先查后改覆盖已 PAID
2. 押金路径：pay→激活→退款申请→审核→打款 锁覆盖（R1 F-005/006/030 已报点周边换面）→ ✓ F-054（P3）repay_deposit 仅拦 PAID 可重复建单
3. 退款路径：申请→审核→退款回调→对账 锁覆盖与幂等（F-007/031 周边）→ ✓ C-097 内（apply/audit/mark_refunded/handle_failed 全锁）
4. 罚款路径：还书逾期罚款/丢失扣款 vs 押金退款并发时序（F-047 is_first_overdue 无锁周边）→ ✓ C-097 内（return_book 双锁 + sync_outstanding_fine 契约明确）

**R4 进度**：Y.1-Y.4 完成，发现 F-053（P2）+ F-054（P3）+ clean C-097，累计 53 发现 / 94 clean。

**R4 完结**：4/4 项完成，发现 F-053~054（P2×1 + P3×1）+ clean C-097，累计 53 发现 / 94 clean，HEAD=98b7ff7。汇总见 findings-20260807.md「R4 第四轮 并发 × 资金 定向深挖」。

## 第五轮（R5）定时任务 × 资金 纵深清单

> R4 完结建议：R5 继续 P2 聚集区——"定时任务×资金"纵深（F-046 定时任务直改状态周边：graduate_children 无行锁 + is_first_overdue 跨事务竞态已报，查同类；mark_overdue_books 锁覆盖复验）。

1. mark_overdue_books 锁覆盖复验（F58/F80 已修点确认：L1581/1612 行锁重取 + L1632 child 批量锁）→ ✓ C-098 内（覆盖完整）
2. 罚款额度语义纵深：apply_fine/is_first_overdue 首次免罚判定 vs 宽限期零罚款记录 → ✓ F-055（P3）宽限期记录消耗免罚额度，首次真实罚款不免
3. 其余资金相关任务（alert_stale_refunds/check_paid_not_activated/check_member_expiry/reconcile_stock/reconcile_child_stats/reset_stale_pending_deposits）→ ✓ C-098 内（无资金写/已修/已排重）

**R5 进度**：Z.1-Z.3 完成，发现 F-055（P3）+ clean C-098，累计 54 发现 / 95 clean。R5 完结。

## 第六轮（R6）借阅/预约并发面清单

> R5 完结建议：R6 继续 P2 聚集区——"并发×资金"剩余面或按用户指定维度。本轮选 R4 资金链未覆盖的借阅/预约路径并发面（P2 聚集区新面：预约创建/取书/过期锁覆盖 + F4 候补队列状态机）。

1. 预约创建/取书/过期全链锁覆盖：create_reservation（Book 行锁 + F46 拦截）/ fulfill_reservation（F45 条件 UPDATE 防并发双取）/ expire_reservation（F45 同口径）→ ✓ C-099 内（全 F45 条件 UPDATE，affected==1 判定）
2. 借阅上限并发口径：fulfill 无锁预检 vs borrow_from_reservation 权威锁 → ✓ C-099 内（权威校验 with_for_update 锁 active_records，空集无超限风险）
3. F4 候补队列状态机：join/notify/fulfill/cancel 全链 + NOTIFIED 回归路径 → ✓ F-056（P3）NOTIFIED 无回归路径，通知未抢到者永久失格
4. 事件 handler 注册顺序：book.returned 先库存 +1 再候补通知 → ✓ C-099 内（registry.py:64-65 顺序正确）

**R6 进度**：完成，发现 F-056（P3）+ clean C-099，累计 55 发现 / 96 clean。R6 完结。

## 第七轮（R7）安全 × 文件链路纵深清单

> R6 完结建议 P2 修复后复验，但 R6 后无任何代码提交（HEAD 仍为 48ae387 纯文档）——10 项 P2 全部未修，复验无对象。换面执行安全×文件链路纵深（F-023/024 同类漏改枚举，模式 1 纪律）。

1. F-023/F-024 修复状态确认 → ✓ 均未修（R6 后无代码提交）
2. F-023 影响面补全：complete_upload rmtree（L206）删除面 → ✓ 补充证据并入 F-023（任意已存在目录递归删除）
3. 全库文件写/删/移动点枚举（os.remove/unlink/rename/move/rmtree/write_bytes/open wb）→ ✓ C-100（除 F-023/024 外全部安全：safe_name=uuid+basename、deletion_service 防穿越版、CSV 固定名、cert_path 配置固定）

**R7 进度**：完成，无新编号（F-023 补充）+ clean C-100，累计 55 发现 / 97 clean。R7 完结。

## 第八轮（R8）晋级链路（advancement）纵深清单

> 用户选择"继续新维度"。R8 深挖最大 service（advancement 1170 行，R1-R7 未系统覆盖）：测验/晋级/审核/计数全链。

1. quiz 全链路：start_quiz / submit_answers / 取题端点权限与答案下发 → ✓ F-057（P3）GET /quiz/questions/{book_id} 无校验返回 correct_answer，任意登录用户可拉答案刷满分
2. 晋级检测：check_and_advance 并发安全 + 计数 increment 锁覆盖 → ✓ C-101 内（submit 行锁+守卫、三个 increment 全带锁、check_and_advance 并发重取跳过）
3. 读书提交审核：review_submission 读-改-写锁覆盖 → ✓ F-058（P3）无锁先查后改，并发审核双计已读书数
4. 事件链：quiz.passed 五 handler + registry 注册 → ✓ C-101 内（无重复 commit、计数全锁）

**R8 进度**：完成，发现 F-057（P3）+ F-058（P3）+ clean C-101，累计 57 发现 / 98 clean。R8 完结。

## 第九轮（R9）reading 打卡链纵深清单

> 用户选择"继续新维度"（R8 完结建议路线）。R9 深挖 reading service（595 行）：打卡/进度/会话/录音全链。

1. save_progress：ReadingProgress 行锁 + ReadingSubmission 防重 + Child 行锁 + first_finish 幂等 → ✓ C-102 内（双行锁 + 唯一约束 uq_child_book_progress）
2. start_session 试读限制 + end_session 结算 → ✓ F-060（P3）试读页数限制只在 start 查历史累计，end 无上限无复核可单次绕过；F-059（P3）end_session 无 end_time 守卫可重复结算时长膨胀
3. 三处打卡（auto/voice/finish_book）：查重 + 每日上限 + add_with_unique_fallback → ✓ C-102 内（唯一约束 uq_checkin_child_date_type + SAVEPOINT 兜底）
4. streak 事件链 + 统计链（misc_handlers / reading_handlers / child update_reading_stats）→ ✓ C-102 内（Child 行锁 + 自然日幂等重算 + 全勤消息幂等）
5. save_recording：逾期锁定 + voice_consent 校验 → ✓ C-102 内（audio_url 直存为 F-024 已知入口，排重不重报）

**R9 进度**：完成，发现 F-059（P3）+ F-060（P3）+ clean C-102，累计 59 发现 / 99 clean。R9 完结。

## 待甲方 / 需人工

（无）
