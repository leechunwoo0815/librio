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
| R10 | 2026-08-08 | report 只读链纵深（R9 建议路线） | 1 | 0 | F-061 generate_due_reports 双入口并发双生成（P3）+ C-103 |
| R11 | 2026-08-08 | 管理后台 RBAC 纵深（维度6第三轮） | 1 | 0 | F-062 create_admin 无角色层级校验（P3）+ C-104 权限码全覆盖 |
| R12 | 2026-08-08 | 小程序前端补面（维度5第三轮） | 0 | 0 | C-105 存储/登录/支付/请求/端点契约全安全（零发现） |
| R13 | 2026-08-08 | 定时任务删除面（维度7第三轮） | 1 | 0 | F-063 assessment 不在删除级联清单孤儿残留（P3）+ C-106 |
| R14 | 2026-08-08 | 数据库索引补面（维度8第三轮） | 1 | 0 | F-064 leaderboard 全表排序无索引（P3）+ C-107 |
| R15 | 2026-08-08 | 性能补面（维度13第三轮） | 1 | 0 | F-065 assessment 列表 N+1 第三处同类（P3）+ C-108 |
| R16 | 2026-08-08 | 事件链接缝（重放幂等性） | 0 | 0 | C-109 事件链重放面整体健康（零发现） |
| R17 | 2026-08-08 | deposit 资金域补面（罚款支付链） | 1 | 0 | F-066 pay_fines 并发双缴款单（P3）+ C-110 |
| R18 | 2026-08-08 | 订单域补面（价格链+亲子课名额） | 1 | 0 | F-067 B3 名额校验竞态超员（P3）+ C-111 |
| R19 | 2026-08-08 | 评估域全链（assessment/ar_evaluation） | 1 | 0 | F-068 EvaluationService 未接线 ar_level 断链（P3）+ C-112 |
| R20 | 2026-08-08 | 家长课程域（排期/名额） | 1 | 0 | F-069 时段 create/update 缺输入校验（P3）+ C-113 |
| R21 | 2026-08-08 | 证书域（生成链） | 0 | 0 | C-114 证书生成幂等闭环（零发现） |
| R22 | 2026-08-08 | 消息域（分组/已读链） | 1 | 0 | F-070 消息分组缺 EXPIRED/EXITED/ALUMNI 映射（P3）+ C-115 |
| R23 | 2026-08-08 | 题库域（题目 CRUD/判分） | 1 | 0 | F-071 correct_answer 未校验 A-D/option 存在性（P3）+ C-116 |
| R24 | 2026-08-08 | 生词域（查词限额/生词本） | 1 | 0 | F-072 查词限额可绕过（不传 child_id 计数无效）（P3）+ C-117 |
| R25 | 2026-08-08 | 书域（CRUD/ISBN/上架） | 1 | 0 | F-073 age 倒挂+ISBN 格式校验缺失（P3）+ C-118 |
| R26 | 2026-08-08 | venue/teacher 排班域 | 1 | 0 | F-074 排班时间校验缺失（R20 同类漏改）（P3）+ C-119 |
| R27 | 2026-08-08 | activity 活动域（报名/签到） | 1 | 0 | F-075 enroll 并发双报名无唯一约束（P3）+ C-120 |
| R28 | 2026-08-08 | 书架域（想读清单） | 0 | 0 | C-121 书架域整体安全（零发现） |
| R29 | 2026-08-08 | 剩余小域（profile/wechat/security） | 0 | 0 | C-122 剩余小域整体安全（零发现） |
| R30 | 2026-08-08 | 模式汇总复查（先查后插枚举） | 1 | 0 | F-076 BookPage 先查后插无唯一约束第3处（P3）+ C-123 |
| R31 | 2026-08-08 | borrow 全链复核对 | 0 | 0 | C-124 borrow 全链安全（零发现） |
| R32 | 2026-08-08 | refund 域补面 | 0 | 0 | C-125 refund 域补面安全（零发现） |
| R33 | 2026-08-08 | 综合异常路径 | 0 | 0 | C-126 异常体系统一全局兜底（零发现） |
| R34 | 2026-08-08 | user 域补面（登录/token 链） | 1 | 0 | F-077 wx_login phone_code 账号接管（P2）+ C-127 |
| R35 | 2026-08-08 | child 域补面（状态机/权益转移） | 0 | 0 | C-128 child 域补面安全（零发现） |
| R36 | 2026-08-08 | borrow 管理端补面 | 0 | 0 | C-129 borrow 管理端安全（零发现） |
| R37 | 2026-08-08 | 身份链同类模式枚举（F-077 后续） | 0 | 0 | C-130 身份链枚举完成（F-077 孤立点） |
| R38 | 2026-08-08 | audio 域 | 0 | 0 | C-131 audio 域安全（零发现） |
| R39 | 2026-08-08 | 文件上传链复查 | 0 | 0 | C-132 上传链大小限制面完整（零发现） |
| R40 | 2026-08-08 | reservation 预约域补面 | 0 | 0 | C-133 预约域补面安全（零发现） |
| R41 | 2026-08-08 | benefit_transfer 审核链 | 1 | 0 | F-078 approve/reject 无锁读-改-写（P3）+ C-134 |
| R42 | 2026-08-08 | teacher_workbench 补面 | 0 | 0 | C-135 workbench 聚合安全（零发现） |
| R43 | 2026-08-08 | advancement 管理端补面（级别/成就） | 0 | 0 | C-136 级别成就 CRUD 安全（零发现） |
| R44 | 2026-08-08 | message 管理端群发 | 1 | 0 | F-079 群发组值无白名单校验（P3）+ C-137 |
| R45 | 2026-08-08 | 综合接口覆盖复查 | 0 | 0 | C-138 接口覆盖零缺失（零发现） |
| R46 | 2026-08-08 | damage 损坏报告域（定责/赔偿链） | 1 | 0 | F-080 confirm/reject/review 无锁双计罚款（P2）+ C-139 |
| R47 | 2026-08-08 | damage override 冲正链 | 0 | 0 | C-140 override 冲正链安全（零发现） |
| R48 | 2026-08-08 | quiz_handlers 联动链 | 0 | 0 | C-141 handler 链安全（零发现） |
| R49 | 2026-08-08 | dictionary 词典域 | 1 | 0 | F-081 update_word 撞唯一约束 500（P3）+ C-142 |
| R50 | 2026-08-08 | assessment 测评状态机 | 0 | 0 | C-143 assessment 状态机弱候选不值报（零发现） |
| R51 | 2026-08-08 | export 导出域 | 1 | 0 | F-082 CSV 导出敏感字段+公式注入（P3）+ C-144 |
| R52 | 2026-08-08 | user 管理端（账号迁移/监护人） | 1 | 0 | F-083 migrate_account 漏迁 ConsentRecord（P3）+ C-145 |
| R53 | 2026-08-08 | refund 管理端（admin 直建退款/执行） | 1 | 0 | F-084 admin 重复打款无状态守卫（P2）+ C-146 |
| R54 | 2026-08-08 | 订单支付回调链（升级/续费） | 0 | 0 | C-147 订单回调链安全（零发现） |
| R55 | 2026-08-08 | 定时提醒链（due/pending 提醒） | 1 | 0 | F-085 待审核提醒每日重复（P3）+ C-148 |
| R56 | 2026-08-08 | borrow-押金联动链 | 0 | 0 | C-149 押金联动安全（零发现） |
| R57 | 2026-08-08 | deposit 支付回调激活链 | 0 | 0 | C-150 回调激活链安全（零发现） |
| R58 | 2026-08-08 | 订阅消息触达链 | 0 | 0 | C-151 订阅消息链安全（零发现） |
| R59 | 2026-08-08 | 用户侧 cancel_order 链 | 0 | 0 | C-152 cancel 链已覆盖（F-053 未修确认） |
| R60 | 2026-08-08 | mark_overdue_books 任务复核对 | 0 | 0 | C-153 任务复核对安全（零发现） |
| R61 | 2026-08-08 | start_quiz 复核对 | 0 | 0 | C-154 start_quiz 复核对安全（零发现） |
| R62 | 2026-08-08 | check_and_advance 复核对 | 0 | 0 | C-155 晋级复核对安全（零发现） |
| R63 | 2026-08-08 | scan_and_borrow 条码借书复核对 | 1 | 0 | F-086 BookCopy.barcode 无唯一约束（P3）+ C-156 |
| R64 | 2026-08-08 | 借阅上限边界复核对 | 0 | 0 | C-157 上限边界安全（零发现） |
| R65 | 2026-08-08 | message 已读一致性复核对 | 0 | 0 | C-158 已读双轨安全（零发现） |
| R66 | 2026-08-08 | BookPage 读取/渲染链 | 0 | 0 | C-159 渲染链安全（零发现） |
| R67 | 2026-08-08 | submit_answers 判分复核对 | 0 | 0 | C-160 判分复核对安全（零发现） |
| R68 | 2026-08-08 | admin 配置写入链复核对 | 0 | 0 | C-161 配置写入链安全（零发现） |
| R69 | 2026-08-08 | 权益转移申请链 | 1 | 0 | F-087 target pending 检查不对称（P3）+ C-162 |
| R70 | 2026-08-08 | 银行转账确认链 | 0 | 0 | C-163 转账确认链安全（零发现） |

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

- **当前维度子项**：第七十轮银行转账确认链 R70 完成（C-163 复用回调幂等链，零发现）→ R70 完结
- **本圈发现数**：0（R70：零发现合法产出）
- **累计发现数**：86（P0:0 / P1:0 / P2:13 / P3:73）+ 160 clean 记录
- **下次从哪开始**：R71 建议继续新维度（继续轮转新面）
- **上一圈结束时 HEAD**：R70 完结后最新提交（见轮次表下方说明）

> 轮次报告文件拆分（用户指令 2026-08-08 起）：每轮一个独立 md 文件存 `audit_loop/rounds/Rxx-<维度>.md`，
> 编号跨文件连续（F-061 起 / C-103 起），findings-20260807.md 冻结不再追加。本表只做索引。
>
> R10-R30 模式汇总：① 先查后插无唯一约束 ×4（F-066/075/076/086）② 管理端 schema 校验缺失 ×4（F-069/071/073/074）
> ③ 业务规则绕过 ×2（F-060/072）④ 覆盖盲区/遗漏 ×8（F-061/062/063/064/065/068/070/083）⑤ 状态守卫缺失 ×2（F-059/084）
> ⑥ 身份认证缺陷 ×1（F-077 账号接管 P2）⑦ 先查后改无锁 ×7（F-053/058/066/075/076/078/080）⑧ 消息触达链两端（F-070/079）
> ⑨ 异常兜底不对称 ×1（F-081）⑩ 敏感数据/注入 ×1（F-082）⑪ 重复提醒无去重 ×1（F-085）⑫ 检查不对称 ×1（F-087）

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

## 第十轮（R10）report 只读链纵深清单

> 用户选择"继续新维度"（R9 完结建议路线）。R10 深挖 report service（759 行）：观察期报告生成/查看/评语/HTML/PDF + 阅读统计 + 双入口生成链路。

1. 观察期报告生成链路：generate_due_reports + _generate_for_child + scheduler/admin 双入口 → ✓ F-061（P3）双入口并发双生成（scheduler 持 Redis 锁 / admin 手动无锁，ObservationReport 无 child_id 唯一约束）
2. 报告查看/评语/标记：mark_viewed（F-042 已报排重）+ add_teacher_comment（require_perm 校验）→ ✓ C-103 内
3. HTML/PDF 渲染：Jinja2 autoescape + asyncio.to_thread → ✓ C-103 内（无 XSS、不阻塞事件循环）
4. 阅读统计五端点：summary/today/trend/weekly/monthly → ✓ C-103 内（单孩子过滤 + days 上限 + 无软删影响）
5. 异常隔离与口径：per-child try/except + F14 member_expire_time 单口径 → ✓ C-103 内

**R10 进度**：完成，发现 F-061（P3）+ clean C-103，累计 60 发现 / 100 clean。R10 完结。

## 第十一轮（R11）管理后台 RBAC 纵深清单

> 管理后台第三轮换面（R1 6.1-6.4 / R2 6.1-6.4 已审）。本轮：① 152 端点权限码覆盖率；② RBAC 自身安全；③ 提权面。

1. 152 端点权限码全覆盖：脚本逐端点解析 12 router → ✓ C-104 内（零漏配；revive_child 为 require_super_admin 非漏配）
2. RBAC 核心实现：has_permission/is_super_admin/get_permission_codes/get_data_scope → ✓ C-104 内（超管不可降权 + 最后超管保护 + 不能改自己角色）
3. 提权面：create_admin/update_admin/set_role_permissions 角色分配约束 → ✓ F-062（P3）create_admin 无角色层级校验（不对称于 update_admin 的 _check_admin_role_change；admin.create 下放后即可创建超管提权）

**R11 进度**：完成，发现 F-062（P3）+ clean C-104，累计 61 发现 / 101 clean。R11 完结。

## 第十二轮（R12）小程序前端补面清单

> 小程序第三轮换面（R1 5.1-5.4 / R2 5.1-5.3 已审）。本轮六面：存储/登录/支付/请求/敏感展示/端点契约。

1. 本地存储安全：setStorageSync 内容枚举 → ✓ C-105 内（仅 token/userInfo/currentChildId/quiz 缓存/隐私标记，无敏感凭证）
2. 登录态恢复 + 401 清理：app.js onLaunch + request.js 401 → ✓ C-105 内（token 缺失不恢复 userInfo，无冒充登录）
3. 支付/下单防重锁：deposit/official/observation 支付链 → ✓ C-105 内（loading/submitting 锁；服务端防重在 R4/R9 已审）
4. request.js 鉴权/超时/错误：401/403/网络预检/超时/统一错误 → ✓ C-105 内
5. 敏感数据展示：WXML grep phone/openid/password/身份证 → ✓ C-105 内（零命中，phonetic 为误报）
6. 端点契约：后端 334 路由 vs 前端 api.js 37 调用 → ✓ C-105 内（零缺失）

**R12 进度**：完成，零发现 + clean C-105，累计 61 发现 / 102 clean。R12 完结（合法零发现轮）。

## 第十三轮（R13）定时任务删除面清单

> 定时任务第三轮换面（R1 7.1-7.4 / R2 时刻表 / R5 资金 / F-046 状态写已审）。本轮：删除任务表覆盖完整性。

1. execute_child_deletions 级联清单：DELETE_TABLES_BY_CHILD 18 表 vs 全库 25 张 child_id 表 → ✓ F-063（P3）assessment 不在清单孤儿残留（文档 §4.2 + 代码双重遗漏，ar_evaluation/observation_evaluation 在清单内唯独 assessment 漏）
2. purge_expired_data 三段删除（非财务/财务/语音）→ ✓ C-106 内（级联顺序 quiz_answer→quiz、备份、软删→冷静期→物理删、财务保留期合规）
3. 文档 §4.2 一致性：合规清单 vs 代码清单 → ✓ C-106 内（除 assessment 外全覆盖）

**R13 进度**：完成，发现 F-063（P3）+ clean C-106，累计 62 发现 / 103 clean。R13 完结。

## 第十四轮（R14）数据库索引补面清单

> 数据库第三轮换面（R1 8.1-8.4 / R2 8.2-8.3 已审）。本轮四面：函数包裹列/排序列/组合过滤/管理端-用户端差集。

1. 函数包裹列查询点（F-015 同类漏改）：func.date/year/month 全库扫描 → ✓ C-107 内（F-015 为唯一已报，其余低频聚合影响面小）
2. 排序列索引核对：last_read_time/pay_time/borrow_time/achieved_at/evaluation_date → ✓ C-107 内（均单 child 过滤后小结果集排序）
3. 组合过滤列：close_expired_orders/expire_reservations/mark_overdue_books → ✓ C-107 内（pay_status 低基数 C-025 已判可接受，expire_time/due_date 有索引）
4. 管理端-用户端排序差集 → ✓ F-064（P3）leaderboard 全表 ORDER BY total_words_read 无索引（R2 8.2 只核管理端漏用户端）

**R14 进度**：完成，发现 F-064（P3）+ clean C-107，累计 63 发现 / 104 clean。R14 完结。

## 第十五轮（R15）性能补面清单

> 性能第三轮换面（R1 13.1-13.3 / R2 13.1 已审）。本轮：循环内查询全扫描 + 聚合链复查 + 预取模式分类。

1. 循环内 db.query 全库扫描（F-025/F-044 同类漏改）→ ✓ F-065（P3）assessment 管理端列表逐条查 Child/Teacher/Venue（N+1 第三处）；全库 N+1 共 3 处全部识别
2. 批量预取模式复核 → ✓ C-108 内（borrow/order/export/refund/report 等均 id.in_ 一次性取回，R2 C-082 分类）
3. 聚合链复查（ReadingSession/Quiz/CheckIn 增长表）→ ✓ C-108 内（F-036/F-064 已覆盖或单 child 过滤）

**R15 进度**：完成，发现 F-065（P3）+ clean C-108，累计 64 发现 / 105 clean。R15 完结。

## 第十六轮（R16）事件链接缝清单

> 事件链换面（C-003/C-043/C-094/C-101/C-102 已审）。本轮：重放幂等性。

1. 发布点守卫：order.paid 回调幂等链（already paid + trade_no 重复 + 行锁）→ ✓ C-109 内（重复回调不重复 publish）
2. handler 幂等：handle_order_paid（状态守卫 + EXITED 拦截）/borrow copy（同值覆盖）/book.overdue（纯日志）→ ✓ C-109 内
3. 注册顺序：book.returned/reservation 链 copy 释放先于候补放行 → ✓ C-109 内（顺序正确，无测试守护为风格观察）
4. 事件总线机制：同步 + 异常回滚 → ✓ C-109 内（C-003/C-043 已确认）

**R16 进度**：完成，零发现 + clean C-109，累计 64 发现 / 106 clean。R16 完结（合法零发现轮）。

## 第十七轮（R17）deposit 资金域补面清单

> deposit 资金域补面（R6 完结标注"1045 行未深挖"）。本轮：罚款支付链 + 资金操作链。

1. pay_fines + _settle_fine_payment：防重/金额/核销 → ✓ F-066（P3）先查后插无唯一约束并发双缴款单（双单均支付多收罚款，需 MySQL 实证）；settle 带锁 + max 兜底 ✓
2. deduct_deposit：行锁 + PAID 守卫 + 扣款封顶 + 超额转 outstanding → ✓ C-110 内
3. mark_book_lost：行锁 + 状态守卫 + Decimal 罚款 + 差额增量 → ✓ C-110 内（book 无锁 F-001 排重）
4. partial_refund_deposit：Phase 1+2 分离 + 失败回滚 → ✓ C-110 内（设计良好）
5. reset_stale_pending_deposits：PENDING 复位 + 罚款单软删清理 → ✓ C-110 内（P3 残留闭环）

**R17 进度**：完成，发现 F-066（P3）+ clean C-110，累计 65 发现 / 107 clean。R17 完结。

## 第十八轮（R18）订单域补面清单

> 订单域补面（R6 完结标注"764 行未深挖"）。本轮：价格链 + 亲子课名额 + 升级 + 退款。

1. create_order 价格链：金额后端计算 + 前置状态校验 + F22 防重 → ✓ C-111 内（防重带锁）
2. _apply_discount：多孩 + 续费折扣 + 不可叠加取最低 → ✓ C-111 内（quantize F-032 排重）
3. _calc_observation_credit（A6 抵扣）：实付÷天数×剩余 + ROUND_HALF_UP + 封顶 → ✓ C-111 内
4. 升级链路：F16 实付金额口径 + max(0) → ✓ C-111 内
5. B3 亲子课名额校验 → ✓ F-067（P3）slot 无行锁 + paid_count 无锁 count 并发超员（对齐 F22 带锁模式修复）

**R18 进度**：完成，发现 F-067（P3）+ clean C-111，累计 66 发现 / 108 clean。R18 完结。

## 第十九轮（R19）评估域全链清单

> 评估域全链（此前零审查记录）。assessment CRUD + evaluation 服务 + child.ar_level 写路径 + 接线完整性。

1. assessment 管理端 CRUD：权限/软删/查询 → ✓ C-112 内（require_perm 全覆盖 + is_deleted 过滤 + completed 自动补时间）
2. evaluation 服务接线：EvaluationService 调用方检查 → ✓ F-068（P3）无调用方——child.ar_level 唯一写路径断裂（周报/月报 current_ar_level 恒空，前端不展示无用户可见异常）
3. child.ar_level 写路径：全库 grep → ✓ F-068 内（唯一写点 evaluation/service.py:53，断链）
4. evaluation 三表删除覆盖：deletion_service → ✓ C-112 内（R13 C-106 已核 ar/obs/guidance 在删除清单）

**R19 进度**：完成，发现 F-068（P3）+ clean C-112，累计 67 发现 / 109 clean。R19 完结。

## 第二十轮（R20）家长课程域清单

> 家长课程域（parent_course_time，此前零审查）。排期/名额 CRUD + 权限 + 校验 + 软删关联。

1. 时段 CRUD 输入校验 → ✓ F-069（P3）create/update 缺 end<start/重叠/名额下界校验（schemas 无 Field 约束，管理端可建非法时段）
2. 权限：管理端四端点 require_perm + 用户端公开时段 → ✓ C-113 内
3. 用户端状态过滤：仅 status==1 + is_deleted==0 → ✓ C-113 内
4. 软删与订单关联：软删后新报名拒绝、已存在订单保留 → ✓ C-113 内
5. B3 名额并发（R18 F-067）→ 排重不重报

**R20 进度**：完成，发现 F-069（P3）+ clean C-113，累计 68 发现 / 110 clean。R20 完结。

## 第二十一轮（R21）证书域清单

> 证书域（此前零审查）。生成幂等/归属/转义/事件闭环/删除覆盖。

1. generate_certificate 幂等：get_by_child_and_level 已有返回 → ✓ C-114 内
2. 事件链闭环：level.advanced 发布点防重（C-101）+ handler 内幂等 → ✓ C-114 内（双层防重）
3. 归属校验：GET /certificate/{child_id} GetOwnedChild → ✓ C-114 内
4. HTML 转义：Jinja2 autoescape → ✓ C-114 内
5. 删除覆盖：level_certificate 在删除清单（R13 C-106）+ 管理端权限（R11）→ ✓ C-114 内

**R21 进度**：完成，零发现 + clean C-114，累计 68 发现 / 111 clean。R21 完结（合法零发现轮）。

## 第二十二轮（R22）消息域清单

> 消息域（F-044 N+1 已报）。本轮：分组映射/已读链/群发机制。

1. 分组映射：_USER_GROUP_MAP vs MemberStatus 六态 → ✓ F-070（P3）只映射 TRIAL/OBS/OFF，EXPIRED/EXITED/ALUMNI 掉入 default "trial" 收错群发
2. 已读链：mark_as_read 归属校验 + 批量查询 → ✓ C-115 内
3. 群发机制：单条 SystemMessage + target_role_codes（不遍历用户）→ ✓ C-115 内（L443 已确认设计正确）
4. mark_all_read N+1 → F-044 排重不重报

**R22 进度**：完成，发现 F-070（P3）+ clean C-115，累计 69 发现 / 112 clean。R22 完结。

## 第二十三轮（R23）题库域清单

> 题库域（quiz_question 逻辑在 AdvancementService）。题目 CRUD/判分一致性。

1. create_question 校验：correct_answer A-D 范围 + option 存在性 + book 存在性 → ✓ F-071（P3）只限 1 字符不校验 A-D，option_c/d 可空不联动校验（畸形题致判分异常）
2. update_question 字段白名单 + delete 软删 → ✓ C-116 内
3. list_questions：escape_like + 分页 → ✓ C-116 内
4. 判分一致性：correct_answer == selected 直接比较 → ✓ C-116 内（C-101 已审锁）
5. F-026（搜索无 limit）/F-057（取题泄漏）→ 排重不重报

**R23 进度**：完成，发现 F-071（P3）+ clean C-116，累计 70 发现 / 113 clean。R23 完结。

## 第二十四轮（R24）生词域清单

> 生词域（UserVocabulary）。查词限额/生词本 CRUD/归属/打卡。

1. 查词限额：lookup_word child_id 可选 → ✓ F-072（P3）不传 child_id 时计数基于 UserVocabulary 无写入恒 0，试读 30 次/天上限可绕过（与 F-060 同类绕过模式）
2. 生词本 CRUD：唯一约束 uq_child_word + GetOwnedVocab 归属 + 软删 → ✓ C-117 内
3. 生词打卡：add_with_unique_fallback + 每日上限 → ✓ C-117 内（C-102 已核同类）
4. 词典音频：db_audio 优先 + youdao 兜底 → ✓ C-117 内（F-011 前端展示面已报）

**R24 进度**：完成，发现 F-072（P3）+ clean C-117，累计 71 发现 / 114 clean。R24 完结。

## 第二十五轮（R25）书域清单

> 书域（Book/BookCopy）。CRUD/ISBN/上架/拷贝管理。

1. create_book 校验：ISBN 唯一（DB+应用双层）+ age 交叉 → ✓ F-073（P3）缺 age_min<=age_max 交叉校验 + isbn 无格式校验（与 R20/R23 同类 schema 校验缺失模式）
2. update/delete：with_for_update 行锁 + 软删 → ✓ C-118 内
3. toggle_publish：SQL 原子更新（无读-改-写竞态）→ ✓ C-118 内
4. search_books：escape_like + 分页 → ✓ C-118 内
5. F-001/004/026/034/038 → 排重不重报

**R25 进度**：完成，发现 F-073（P3）+ clean C-118，累计 72 发现 / 115 clean。R25 完结。

## 第二十六轮（R26）venue/teacher 排班域清单

> venue 公开端点 + teacher 管理 + 排班。

1. create_schedule 时间校验 → ✓ F-074（P3）start/end 仅 min_length 无格式/顺序校验 + 无同老师同日重叠校验（R20 F-069 parent_course_time 同类漏改，模式 1）
2. venue 公开端点：列表/联系方式无鉴权 → ✓ C-119 内（C-033 已证公共资源设计）
3. teacher CRUD：权限齐 + 软删 + assign 归属 → ✓ C-119 内
4. 排班 CRUD：require_perm("teacher.schedule") + 软删 → ✓ C-119 内

**R26 进度**：完成，发现 F-074（P3）+ clean C-119，累计 73 发现 / 116 clean。R26 完结。

## 第二十七轮（R27）activity 活动域清单

> 活动域（报名/取消/签到/名额/状态机）。

1. enroll 防重与名额 → ✓ F-075（P3）先查后插无唯一约束并发双报名（人数原子递增防超卖 ✓，但同 child 双记录双 ticket）；ActivityEnrollment 无 (child_id, activity_id) 唯一约束
2. 名额原子递增/递减（条件 UPDATE）→ ✓ C-120 内（防超卖 + 释放正确）
3. cancel_enrollment：行锁 + 时间校验 + 守卫 → ✓ C-120 内
4. 签到：状态守卫 + 防重 + 票码 → ✓ C-120 内
5. 归属/权限：GetOwnedChildFromBody/GetOwnedEnrollment + require_perm → ✓ C-120 内

**R27 进度**：完成，发现 F-075（P3）+ clean C-120，累计 74 发现 / 117 clean。R27 完结。

## 第二十八轮（R28）书架域清单

> 书架域（想读清单，此前零审查）。N+1/防重/状态/容量。

1. get_shelf N+1：joinedload(Bookshelf.book) → ✓ C-121 内（一次 join，无循环查询）
2. add_to_shelf 防重 + 容量 100 检查 → ✓ C-121 内（弱并发候选因收藏性质不值报）
3. 状态流转：WANT_READ→FINISHED/REMOVED + 排除 REMOVED → ✓ C-121 内
4. 软删过滤 + 归属 → ✓ C-121 内

**R28 进度**：完成，零发现 + clean C-121，累计 74 发现 / 118 clean。R28 完结（合法零发现轮）。

## 第二十九轮（R29）剩余小域综合补面清单

> 剩余小域（profile/wechat/security/consent）。token 缓存/QR 安全/内容检测/聚合查询。

1. wechat access_token 缓存：Redis 主 + 内存降级 + 双重检查锁 + TTL 余量 → ✓ C-122 内（工程化范本）
2. QR 码：scene/page 长度限制 + check_path 微信侧兜底 + 鉴权 → ✓ C-122 内
3. check-text：v2 suggest + detail 兜底 + 违规拦截 → ✓ C-122 内（P2-1 已闭环）
4. profile 聚合：batch in_ 预取无 N+1 → ✓ C-122 内
5. consent：voice_consent（R9 已审）→ 排重

**R29 进度**：完成，零发现 + clean C-122，累计 74 发现 / 119 clean。R29 完结（合法零发现轮）。

## 第三十轮（R30）模式汇总复查清单

> R10-R29 三类新模式汇总 + 模式①（先查后插无唯一约束）全库枚举。

1. 模式①枚举：19 处先查后插逐一核对 → ✓ F-076（P3）BookPage 无 (book_id, page_number) 唯一约束（第 3 处）；其余 18 处安全（唯一约束/IntegrityError/追加语义）
2. 模式分类：①并发唯一约束×3 / ②schema 校验×4 / ③业务规则绕过×2 → ✓ C-123 内（已汇总到当前进度段）
3. 修复建议模式化：补唯一约束 / 补 schema 交叉校验 / 计数与业务解耦 → ✓ C-123 内

**R30 进度**：完成，发现 F-076（P3）+ clean C-123，累计 75 发现 / 120 clean。R30 完结。

## 第三十一轮（R31）borrow 全链复核对清单

> borrow 全链复核对（R4/R5/R6 已审，本轮换面）。上限/副本/库存/还书/条码。

1. borrow_book：上限行锁 + 防重借 + 副本锁 + 原子扣库存 → ✓ C-124 内（C-099 已审上限）
2. return_book：状态守卫 + with_for_update + 罚款差额增量 → ✓ C-124 内（R5/F-047 已审公式）
3. scan_and_return：条码防重（活跃查询 + return 守卫双防）→ ✓ C-124 内
4. 事件链：BookBorrowed/ReturnedEvent → ✓ C-124 内（C-109 已审重放）

**R31 进度**：完成，零发现 + clean C-124，累计 75 发现 / 121 clean。R31 完结（合法零发现轮）。

## 第三十二轮（R32）refund 域补面清单

> refund 域补面（F-002/005/006/009/016/031 已审）。apply 校验链/audit 守卫/金额口径。

1. apply_refund 校验链：归属/防重/年度限次（F25 闰年安全）/亲子课/未还书/罚款抵扣 → ✓ C-125 内全链完整
2. 金额服务端计算：used_days 服务端算 + E7 抵扣 + F75-② 原额 + F38 out_refund_no → ✓ C-125 内
3. E1 小额自动审核 + audit 行锁守卫（防双重审批）→ ✓ C-125 内
4. 执行链：F-002/005/016/031 已报排重 + F38 幂等键 → ✓ C-125 内

**R32 进度**：完成，零发现 + clean C-125，累计 75 发现 / 122 clean。R32 完结（合法零发现轮）。

## 第三十三轮（R33）综合异常路径清单

> 综合异常路径。全局兜底/异常体系/技术栈泄露/裸异常。

1. 全局异常：global_exception_handler 500 固定文案 + exc_info → ✓ C-126 内（不泄堆栈）
2. 异常体系：BusinessException 9 子类 + 结构化响应 → ✓ C-126 内
3. service 层裸 ValueError 扫描：仅 3 处 schema validator 内（Pydantic 转 422）→ ✓ C-126 内（无 500 面）
4. 技术栈泄露：R1/R2 已确认干净 + F-022/F-028 已报 → 排重

**R33 进度**：完成，零发现 + clean C-126，累计 75 发现 / 123 clean。R33 完结（合法零发现轮）。

## 第三十四轮（R34）user 域补面清单

> user 域（登录/token/手机号换绑/身份一致性）。

1. wx_login phone_code 链 → ✓ **F-077（P2）** update_user_phone 手机号被占时返回他人用户 → user 被替换 → 生成他人身份 token（账号接管）；change_phone 有防占用、wx_login 无（同类漏改）
2. 限流：wx_login/phone_login rate_limit(10,60) → ✓ C-127 内
3. change-phone 防占用 + 验证码 → ✓ C-127 内
4. openid 查重 + set_current_child 归属 → ✓ C-127 内
5. F-003/020/041/051 → 排重不重报

**R34 进度**：完成，发现 F-077（P2）+ clean C-127，累计 76 发现 / 124 clean。R34 完结。

## 第三十五轮（R35）child 域补面清单

> child 域（状态机/权益转移/审计/删除复活）。

1. update_status：二次确认 + 状态机矩阵 + from→to 审计 → ✓ C-128 内（write_operation_log commit 依赖已确认正确）
2. 权益转移：_validate_transfer 全维校验（同用户/状态/借阅/罚款/ALUMNI F21）→ ✓ C-128 内
3. 删除/复活链：F-013/C-106/R11 已审 → 排重
4. can_borrow_books + 统计更新 → ✓ C-128 内

**R35 进度**：完成，零发现 + clean C-128，累计 76 发现 / 125 clean。R35 完结（合法零发现轮）。

## 第三十六轮（R36）borrow 管理端补面清单

> borrow 管理端（罚款清零/借还/预约/押金/操作日志）。

1. clear_child_fines：child 行锁 + 清零留痕 → ✓ C-129 内（资金面锁正确）
2. 管理端借还：复用用户域 BorrowService（单点校验）+ 操作日志 → ✓ C-129 内
3. 预约/押金管理：require_perm + 用户域 service 复用 → ✓ C-129 内（C-099/R17 已核）
4. 列表查询：批量 in_ 预取无 N+1 → ✓ C-129 内

**R36 进度**：完成，零发现 + clean C-129，累计 76 发现 / 126 clean。R36 完结（合法零发现轮）。

## 第三十七轮（R37）身份链同类模式枚举清单

> F-077 后续：全库"user 赋值 + token 来源"模式枚举（模式 1 纪律）。

1. user = service 调用 5 处逐一分析 → ✓ C-130 内（仅 wx_login L51 危险）
2. create_access_token 2 处 token 来源核对 → ✓ C-130 内（wx_login 被替换 / phone_login 安全）
3. update_user_phone 2 调用点：wx_login（漏洞）+ change_phone（防占用）→ ✓ C-130 内（F-077 孤立点确认）
4. link_openid（绑定不替换身份）→ ✓ C-130 内（phone_login 安全）

**R37 进度**：完成，零发现 + clean C-130，累计 76 发现 / 127 clean。R37 完结（合法零发现轮）。

## 第三十八轮（R38）audio 域清单

> audio 域（列表/CRUD/统计）。

1. list_audios：escape_like + 分页 + SQL 聚合统计 → ✓ C-131 内
2. create/update：book 校验 + schema 字段 → ✓ C-131 内
3. delete：软删 + is_deleted 过滤 → ✓ C-131 内
4. 权限：require_perm（R11 已核）→ ✓ C-131 内
5. F-011/023/024 → 排重不重报

**R38 进度**：完成，零发现 + clean C-131，累计 76 发现 / 128 clean。R38 完结（合法零发现轮）。

## 第三十九轮（R39）文件上传链复查清单

> 上传链复查（F-023/024/043 + C-079 已报）。

1. 单文件 upload_file：save_upload 10MB 兜底确认（F-043 已证安全）→ ✓ C-132 内
2. 分片 upload_chunk：无大小限制（F-043 已报）→ 排重
3. 扩展名/魔数/落盘：C-079 已核 → ✓ C-132 内
4. complete_upload：合并魔数（F-043 已报大小面）→ ✓ C-132 内

**R39 进度**：完成，零发现 + clean C-132，累计 76 发现 / 129 clean。R39 完结（合法零发现轮）。

## 第四十轮（R40）reservation 预约域补面清单

> 预约域补面（R6 F-056/C-099 已审）。创建/取消/候补业务链。

1. create_reservation：book 行锁间接防重 + F46 未还拦截 + 候补闭环 → ✓ C-133 内
2. cancel_reservation：PENDING 守卫（F40）+ 条件 UPDATE affected==1 → ✓ C-133 内
3. 候补链：F-056（回归缺失）+ C-099（锁分层）→ 排重
4. 事件链：C-109 已审重放 → ✓ C-133 内

**R40 进度**：完成，零发现 + clean C-133，累计 76 发现 / 130 clean。R40 完结（合法零发现轮）。

## 第四十一轮（R41）benefit_transfer 审核链清单

> 权益转移管理端审核链（R35 已审 transfer 本体）。

1. approve/reject 状态守卫 → ✓ F-078（P3）无 with_for_update（先查后改无锁，F-053 同模式）；实际被 transfer_benefit 二次校验兜底（无数据危害）
2. transfer 二次校验（R35 已核 _validate_transfer）→ ✓ C-134 内（双执行被拦截）
3. 权限 + 审核留痕 → ✓ C-134 内

**R41 进度**：完成，发现 F-078（P3）+ clean C-134，累计 77 发现 / 131 clean。R41 完结。

## 第四十二轮（R42）teacher_workbench 补面清单

> 老师工作台（聚合查询/批量预取/反馈）。

1. get_workbench：批量 in_ 预取（无 N+1）+ limit(20/5) + 只读 → ✓ C-135 内
2. post_feedback：child 归属校验 + GuidanceRecord/消息联动 → ✓ C-135 内（R41/R22 已审）
3. 权限：require_perm（R11 已核）→ ✓ C-135 内

**R42 进度**：完成，零发现 + clean C-135，累计 77 发现 / 132 clean。R42 完结（合法零发现轮）。

## 第四十三轮（R43）advancement 管理端补面清单

> 级别/成就/证书管理 CRUD（R8 quiz/晋级链已审）。

1. 级别 CRUD：pass_rate 映射 + 软删 → ✓ C-136 内（F-045 required_books 已报排重）
2. 成就 CRUD + grant 防重（C-101 已核）→ ✓ C-136 内
3. 证书操作：R11 权限 + R21 证书域 → ✓ C-136 内
4. 管理端配置属性：权限齐（R11 已核 152 端点）→ ✓ C-136 内

**R43 进度**：完成，零发现 + clean C-136，累计 77 发现 / 133 clean。R43 完结（合法零发现轮）。

## 第四十四轮（R44）message 管理端群发清单

> 消息管理端群发（R22 接收端已审，本轮发送端）。

1. send_message 三模式目标校验（user/teacher 查存在）→ ✓ C-137 内
2. 群发组值 → ✓ F-079（P3）target_role_groups 无白名单校验，无效组值静默触达失败（与 F-070 接收端映射构成触达链两端）
3. 列表/软删/逾期提醒 → ✓ C-137 内

**R44 进度**：完成，发现 F-079（P3）+ clean C-137，累计 78 发现 / 134 clean。R44 完结。

## 第四十五轮（R45）综合接口覆盖复查清单

> 接口覆盖复查（R4 C-095 参数契约 / R12 C-105 端点契约互补）。

1. 后端 334 路由 vs 前端 38 去重调用 → ✓ C-138 内（零缺失）
2. api.js 37 端点全域覆盖 → ✓ C-138 内
3. 路径模板归一化对比 → ✓ C-138 内

**R45 进度**：完成，零发现 + clean C-138，累计 78 发现 / 135 clean。R45 完结（合法零发现轮）。

## 第四十六轮（R46）damage 损坏报告域清单

> damage 域（定责/赔偿/审核/申诉/找回）。

1. confirm/reject/review 状态守卫 → ✓ **F-080（P2）** _get_report_or_raise 无 with_for_update，并发双确认双计罚款（F-053/F-058 同模式，先查后改无锁第 7 处）
2. 双人复核（B9：admin != 本人）+ 物理回滚（丢失定级）→ ✓ C-139 内
3. 资金锁：child with_for_update（罚款计入串行）→ ✓ C-139 内（report 状态层为 F-080 缺口）
4. 状态机/通知/操作日志/权限 → ✓ C-139 内

**R46 进度**：完成，发现 F-080（P2）+ clean C-139，累计 79 发现 / 136 clean。R46 完结。

## 第四十七轮（R47）damage override 冲正链清单

> damage review override 深挖（R46 F-080 并发面已报）。

1. 倍率一致：LEVEL_MULTIPLIERS {0/0.5/1.5} + F49 改判默认 0.5×定价 → ✓ C-140 内
2. 金额差值回滚：diff → outstanding_fines（max(0) 兜底）→ ✓ C-140 内
3. 丢失改判逆向联动：BookCopy/库存（F49 available 不加）/借阅状态 → ✓ C-140 内
4. 锁覆盖：child/record/copy 全 with_for_update → ✓ C-140 内

**R47 进度**：完成，零发现 + clean C-140，累计 79 发现 / 137 clean。R47 完结（合法零发现轮）。

## 第四十八轮（R48）quiz_handlers 联动链清单

> quiz.passed 六 handler（advancement/stats/borrow/bookshelf/submission/failed）。

1. submission 自动审核：PENDING 行锁（防双 APPROVED）+ 时长检查 → ✓ C-141 内
2. bookshelf handler：with_for_update + FINISHED → ✓ C-141 内
3. book_finished 转发：increment + check_and_advance（C-101 防双重晋级）→ ✓ C-141 内
4. borrow handler 异常隔离（try/except 不影响主流程）→ ✓ C-141 内

**R48 进度**：完成，零发现 + clean C-141，累计 79 发现 / 138 clean。R48 完结（合法零发现轮）。

## 第四十九轮（R49）dictionary 词典域清单

> 词典域（搜索/CRUD/唯一约束一致性）。

1. create_word：唯一约束 + IntegrityError 兜底（R30 已确认）→ ✓ C-142 内
2. update_word → ✓ F-081（P3）改 word 撞唯一约束无兜底 → 500（create 有 update 无，同文件不对称）
3. search_words：escape_like 双字段 + 分页 → ✓ C-142 内
4. delete：软删 + is_deleted 过滤 → ✓ C-142 内

**R49 进度**：完成，发现 F-081（P3）+ clean C-142，累计 80 发现 / 139 clean。R49 完结。

## 第五十轮（R50）assessment 测评状态机清单

> assessment 状态机（R19 CRUD/R15 N+1 已审）。

1. create/update 状态处理：completed 自动补时间 → ✓ C-143 内
2. status 无枚举校验 → ✓ C-143 内（管理端记录 + 非核心状态机域，弱候选不值报）
3. R19 C-112 / R15 F-065 / R19 F-068 → 排重不重报

**R50 进度**：完成，零发现 + clean C-143，累计 80 发现 / 140 clean。R50 完结（合法零发现轮）。

## 第五十一轮（R51）export 导出域清单

> 导出域（CSV 生成/模块分发/敏感字段/注入）。

1. users 导出字段 → ✓ F-082（P3）phone/openid 明文 + 用户可控字段无公式注入防护（F-020/041 日志面已报，导出文件面本轮新）
2. 模块白名单：model_map 固定 → ✓ C-144 内
3. 批量预取无 N+1 + limit(10000) → ✓ C-144 内
4. 权限 + 限流 → ✓ C-144 内

**R51 进度**：完成，发现 F-082（P3）+ clean C-144，累计 81 发现 / 141 clean。R51 完结。

## 第五十二轮（R52）user 管理端补面清单

> user 管理端（账号迁移/监护人变更/复活）。

1. migrate_account 迁移覆盖 → ✓ F-083（P3）漏迁 ConsentRecord（user_id 无 FK 声明漏网，迁移后新账号录音被拒）
2. change_guardian：confirmed + 行锁 + 非同一人 → ✓ C-145 内
3. revive_child：require_super_admin（R11/R35 已审）→ ✓ C-145 内
4. 4 类 user_id FK 表全迁（order/message/refund/child）→ ✓ C-145 内

**R52 进度**：完成，发现 F-083（P3）+ clean C-145，累计 82 发现 / 142 clean。R52 完结。

## 第五十三轮（R53）refund 管理端补面清单

> refund 管理端（admin 直建退款/执行链）。

1. create_refund 状态校验 → ✓ **F-084（P2）** 无 pay_status/已存在退款单校验（apply_refund L51 有、管理端无——不对称）；_execute_wechat_refund 无状态守卫 → 已退款订单重复打款（F38 新单号不拦截）
2. F52 金额公式（calculate_refund 非死代码）→ ✓ C-146 内
3. F38 单号复用 + F37 原额 + F2 元分 → ✓ C-146 内
4. 权限 + 操作日志 → ✓ C-146 内

**R53 进度**：完成，发现 F-084（P2）+ clean C-146，累计 83 发现 / 143 clean。R53 完结。

## 第五十四轮（R54）订单支付回调链清单

> 订单回调链（R16 守卫/幂等已审，本轮金额语义）。

1. F16 升级重置（upgrade_deduct>0 防双重受益）→ ✓ C-147 内
2. 续费叠加 / 过期重置 → ✓ C-147 内
3. A6 双语义（L1224 已评估自洽）→ 排重
4. OBSERVATION 激活 + days 按类型 → ✓ C-147 内

**R54 进度**：完成，零发现 + clean C-147，累计 83 发现 / 144 clean。R54 完结（合法零发现轮）。

## 第五十五轮（R55）定时提醒链清单

> 定时提醒链（due 到期/pending 待审提醒）。

1. check_due_date_reminders：JOIN 查询 + 上界过滤 + 5/3/1/0 递增 → ✓ C-148 内（无重复）
2. remind_pending_submissions → ✓ F-085（P3）无去重——7 天后每日重复提醒（消息轰炸，修复加 last_remind_at 或只提醒一次）
3. F-038（is_deleted 缺口）→ 排重

**R55 进度**：完成，发现 F-085（P3）+ clean C-148，累计 84 发现 / 145 clean。R55 完结。

## 第五十六轮（R56）borrow-押金联动链清单

> borrow-押金联动（R31 borrow 链已审）。

1. 押金阻塞：deposit_status 三态校验（borrow_book/from_reservation/can_borrow_books）→ ✓ C-149 内
2. 欠费不阻塞借书 = PRD V3.5 明确设计 → ✓ C-149 内（非缺陷）
3. 罚款链：R5 公式/R17 缴纳/R31 还书/R32 退款抵扣 → 排重

**R56 进度**：完成，零发现 + clean C-149，累计 84 发现 / 146 clean。R56 完结（合法零发现轮）。

## 第五十七轮（R57）deposit 支付回调激活链清单

> deposit 回调链（R17 资金链已审，本轮回调面）。

1. handle_callback：F74 幂等 + 仅 PENDING 守卫 + 金额校验 + 行锁 → ✓ C-150 内
2. handle_deposit_paid_for_child：child 行锁 + PAID → ✓ C-150 内（双路径同值幂等）
3. F-048（trade_state 缺口）/F-066（pay_fines 并发）→ 排重

**R57 进度**：完成，零发现 + clean C-150，累计 84 发现 / 147 clean。R57 完结（合法零发现轮）。

## 第五十八轮（R58）订阅消息触达链清单

> 订阅消息链（映射/降级/异步/授权）。

1. 标题→模板映射（9 类高价值）→ ✓ C-151 内
2. 降级链路（开关/openid/标题/模板任一不满足只落库）→ ✓ C-151 内
3. 异步 daemon + 失败静默 + 字段截断 → ✓ C-151 内
4. 模板激活为外部阻塞（恢复卡 §二.9）→ ✓ C-151 内（非代码缺陷）

**R58 进度**：完成，零发现 + clean C-151，累计 84 发现 / 148 clean。R58 完结（合法零发现轮）。

## 第五十九轮（R59）用户侧 cancel_order 链清单

> cancel_order 复核对（F-053/F-008 已报）。

1. 状态守卫：仅 PENDING 可取消 → ✓ C-152 内
2. F-053（无锁 P2）→ 已报未修确认（排重）
3. F-008（FAILED 无出路 P3）→ 已报（排重）
4. 与 close_expired_orders 同值幂等 → ✓ C-152 内（F5 已审）

**R59 进度**：完成，零发现 + clean C-152，累计 84 发现 / 149 clean。R59 完结（合法零发现轮）。

## 第六十轮（R60）mark_overdue_books 任务复核对清单

> mark_overdue_books 复核对（R5 公式面已审）。

1. F58 守卫在位：逐条行锁重取 + 状态守卫（防还书覆盖）→ ✓ C-153 内
2. 状态机：BORROWING→OVERDUE + 按日累计 → ✓ C-153 内
3. 公式统一：fine_policy 单一实现 → ✓ C-153 内（R5 已审）
4. F-047/F-055 → 排重

**R60 进度**：完成，零发现 + clean C-153，累计 84 发现 / 150 clean。R60 完结（合法零发现轮）。

## 第六十一轮（R61）start_quiz 复核对清单

> start_quiz 复核对（R8 C-101 已审）。

1. 冷却检查（quiz_cooldown_minutes）+ 时区口径 → ✓ C-154 内
2. 僵尸 IN_PROGRESS→EXPIRED 清理（P3）→ ✓ C-154 内
3. C2 题数（低龄 3 题）→ ✓ C-154 内
4. 并发弱候选（双 IN_PROGRESS）无实质危害不值报 → ✓ C-154 内

**R61 进度**：完成，零发现 + clean C-154，累计 84 发现 / 151 clean。R61 完结（合法零发现轮）。

## 第六十二轮（R62）check_and_advance 复核对清单

> 晋级检测复核对（R8 C-101 已审）。

1. 晋级锁：ChildLevel is_current 行锁 + 并发重取跳过 → ✓ C-155 内
2. 晋级条件：books + quiz 双达标 + C6 收敛 → ✓ C-155 内
3. teacher_review 分流（Level 字段优先）→ ✓ C-155 内
4. 晋级执行：is_current=False + 新 ChildLevel + LevelAdvancedEvent → ✓ C-155 内（R21 证书链已审）

**R62 进度**：完成，零发现 + clean C-155，累计 84 发现 / 152 clean。R62 完结（合法零发现轮）。

## 第六十三轮（R63）scan_and_borrow 条码借书复核对清单

> 条码借书（查重/建书/库存/复用）。

1. barcode 唯一约束 → ✓ F-086（P3）BookCopy.barcode 无 UniqueConstraint，并发扫码双建副本（先查后插家族第 4 处 F-066/075/076/086）
2. 新书必填校验 + 同 ISBN 复用 → ✓ C-156 内
3. 库存原子递增 + F47 → ✓ C-156 内
4. 复用 borrow_book（R31 已核）→ ✓ C-156 内

**R63 进度**：完成，发现 F-086（P3）+ clean C-156，累计 85 发现 / 153 clean。R63 完结。

## 第六十四轮（R64）借阅上限边界复核对清单

> 借阅上限边界（R31/C-099 上限行锁已审）。

1. 配置有界：borrow_limit (1,50) + 默认 10（B14）→ ✓ C-157 内
2. 双路径一致：borrow_book + borrow_from_reservation 行锁 → ✓ C-157 内（R31/C-099）
3. PRD 口径：10 本 ↔ B14 → ✓ C-157 内

**R64 进度**：完成，零发现 + clean C-157，累计 85 发现 / 154 clean。R64 完结（合法零发现轮）。

## 第六十五轮（R65）message 已读一致性复核对清单

> 消息已读双轨复核对（R22 已审）。

1. 双轨：个人 is_read 字段 + 共享 MessageReadStatus 表 → ✓ C-158 内
2. unread 计算：is_read=0 个人 + 未标记共享 → ✓ C-158 内
3. mark_as_read 一致性（L1048 已评估）→ ✓ C-158 内（复核对无退化）

**R65 进度**：完成，零发现 + clean C-158，累计 85 发现 / 155 clean。R65 完结（合法零发现轮）。

## 第六十六轮（R66）BookPage 读取/渲染链清单

> BookPage 读取/渲染（F-076 写入已报）。

1. get_book_pages 归属：GetOwnedChild → ✓ C-159 内
2. reader 渲染：text 组件（无 rich-text 无 XSS）→ ✓ C-159 内
3. buildSegments 分词处理 → ✓ C-159 内
4. F-076（写入唯一约束）→ 排重

**R66 进度**：完成，零发现 + clean C-159，累计 85 发现 / 156 clean。R66 完结（合法零发现轮）。

## 第六十七轮（R67）submit_answers 判分复核对清单

> submit 判分复核对（R8 C-101 已审）。

1. 判分逻辑：correct_answer == selected → ✓ C-160 内
2. score 计算 + C2 低龄规则 → ✓ C-160 内
3. already_counted 去重（C-101 已审）→ ✓ C-160 内
4. F-071（correct_answer 校验）→ 排重

**R67 进度**：完成，零发现 + clean C-160，累计 85 发现 / 157 clean。R67 完结（合法零发现轮）。

## 第六十八轮（R68）admin 配置写入链复核对清单

> 配置写入链（R9 C-073 TTL 已审，本轮值校验面）。

1. E3 三级管控（锁定/警告/自由）→ ✓ C-161 内
2. validate_config_value 数值范围校验（P2-4）→ ✓ C-161 内
3. TTL 双缓存失效（R9 C-073 已审）→ ✓ C-161 内
4. 小数位精度缺口（L661-664 deposit 1200.005 差 1 分）→ F-033 相关已报排重

**R68 进度**：完成，零发现 + clean C-161，累计 85 发现 / 158 clean。R68 完结（合法零发现轮）。

## 第六十九轮（R69）权益转移申请链清单

> 权益转移申请创建面（R35 执行/R41 审核已审）。

1. assert_no_pending_transfer → ✓ F-087（P3）pending 只查 source 不查 target——同一孩子可双申请链（_validate_transfer 兜底无资金损失，修复补 target pending 检查）
2. _validate_transfer 全维兜底（R35 已核）→ ✓ C-162 内
3. get_transfer_records：批量预取 + 状态映射 → ✓ C-162 内

**R69 进度**：完成，发现 F-087（P3）+ clean C-162，累计 86 发现 / 159 clean。R69 完结。

## 第七十轮（R70）银行转账确认链清单

> 银行转账确认（A5 对公转账/复用回调）。

1. 已支付守卫（PAID 拒绝重复确认）→ ✓ C-163 内
2. 复用 handle_payment_callback 幂等链（R1 F-037 + L1371 已核）→ ✓ C-163 内（复核对无退化）
3. trade_no 生成 + 回调内重复检查 → ✓ C-163 内
4. 操作日志 → ✓ C-163 内

**R70 进度**：完成，零发现 + clean C-163，累计 86 发现 / 160 clean。R70 完结（合法零发现轮）。

## 待甲方 / 需人工

（无）
