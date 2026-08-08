# R53 第五十三轮 refund 管理端补面（admin 直建退款/执行链）— 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-084 起 / C-146 起。

## 范围

R53 refund 管理端补面（R32 已审 refund 域本体 apply/audit）。本轮：admin create_refund（管理端直建退款单，
超管自动审核 + 网关执行）+ _execute_wechat_refund 执行链——订单状态校验、重复退款防、F38 单号语义。

## 结果

- **发现 1 项**：F-084（P2）admin create_refund 无订单状态校验 + _execute_wechat_refund 无状态守卫——已退款订单可重复打款
- **clean 1 项**：C-146 退款管理端其余面正常（F52 金额公式/操作日志/权限）

---

## [F-20260808-084] admin create_refund 无订单状态校验 + 执行链无状态守卫——已退款订单重复打款（F38 新单号不拦截） — P2

- **级别**: P2（资金面——重复退款多打款；需管理端操作 + 网关实证；F38 单号幂等不拦新单号）
- **维度**: R4 并发×资金补面（状态守卫缺失家族）
- **文件**: `backend/domain/admin/services/refund_service.py:89-130`（create_refund 无 pay_status/重复退款校验）/
  `backend/domain/refund/service.py:245-296`（_execute_wechat_refund 无状态守卫）/
  `backend/domain/admin/routers/admin_system_router.py:519-540`（端点直通打款）
- **事实**:
  - admin create_refund（refund_service.py:91-95）：order 查询**无 pay_status 校验、无"该订单已存在退款单"校验**——任意状态订单可建退款单
  - 超管（is_admin）自动 APPROVED（L109-115）+ admin_system_router.py:527-537 BackgroundTasks 直调 `_execute_wechat_refund` → **网关打款**
  - `_execute_wechat_refund`（refund/service.py:245-251）：只查 order 存在（无 pay_status/refund_status 守卫）→ 调 gateway.refund（L271-284）——**不检查订单是否已退款/退款中**
  - **重复打款链**：订单已退款（REFUNDED）→ 管理员误操作/重复点击再建退款单 → 新单新 out_refund_no（F38 申请时生成，新单号）→ 网关执行 → **再次打款**（F-005 已注明"微信幂等仅按单号，新单号不拦截"）
  - 对比：用户侧 apply_refund 有 `pay_status != PAID` 校验（refund/service.py:51）——**管理端 create_refund 无同类校验（不对称）**
- **证据**: ① refund_service.py:89-130 无状态校验；② refund/service.py:245-251 执行无守卫；③ admin_system_router.py:527-537 直通；④ 排重 grep：F-005（cancel_refund 时序）为用户侧取消面，本项为管理端直建 + 执行无守卫面；F38（单号幂等）不拦新单号（F-005 已注明）
- **触发**: 已退款/退款中订单 → 管理员（order.refund 权限）再发起退款 → 新退款单自动通过 → 网关再打款
- **影响**: **重复退款（多打款）**——资金面错误，需人工追回；无系统资金损失（打款后账上多退需追回）。管理端操作 + 权限（非匿名），P2
- **建议**: ① create_refund 加 `order.pay_status == PAID` + "无已存在 APPROVED/COMPLETED 退款单"校验（对齐 apply_refund L51）；② _execute_wechat_refund 执行前重查 `order.refund_status`/`refund.status`（已 COMPLETED 则跳过）；③ 或执行链加 order 行锁 + 状态守卫（F-053 修复模式）
- **排重**: 已 grep 确认不在 F-001~083 / C-001~145 中；F-005（cancel_refund 时序）不同面；F-053/F-080（无锁状态写）同家族

---

## [C-20260808-146] 退款管理端其余面（F52 金额/日志/权限） — clean

- **方法**: R53 定向纵深。读 admin refund_service.py（list_refunds/get_refund_and_order/create_refund）+
  admin_system_router.py:519-540 + refund/service.py 执行链 + 排重
- **证据**:
  - **F52 金额公式**：create_refund 用 OrderService.calculate_refund（L104-106，F52 修复，非死代码全额）✓
  - **操作日志**：write_operation_log（router L538-540）✓
  - **权限**：require_perm("order.refund")（L523）✓
  - **执行链**：F38 单号复用（L254-259）+ F37 原单实付额 + F2 元分转换（L276-283）——金额正确（R1 F-037 已确认全程同一来源 refund_amount）✓
  - **列表/详情**：分页 + 批量预取 ✓
- **排重**: R53 本轮退款管理端 clean 侧（F-084 状态守卫缺失为唯一缺口）；F-005/009/016/031/048 + R32 C-125 已报不重

---

## R53 完结汇总

- **范围**: refund 管理端（admin 直建退款/执行链）
- **结果**: 发现 1 项（**F-084 P2 重复打款**）+ clean 1 项（C-146）
- **关键结论**:
  - **F-084 第三个 P2 资金面**：admin create_refund 无订单状态校验 + 执行链无守卫——已退款订单可重复打款；F38 新单号不拦截；用户侧 apply_refund 有校验、管理端无（不对称）
  - 退款管理端其余面正常（F52 公式/日志/权限/单号复用）
  - 修复成本低（create_refund 加 pay_status + 已存在退款单校验；执行链加状态守卫）
- **累计**: 83 发现（P0:0 / P1:0 / **P2:13** / P3:70）+ 143 clean 记录
- **提交**: 见 git log（本轮 rounds/R53 文件 + progress 索引同步更新）
- **R53 收尾结论**: 五十三轮共 83 项发现无 P0/P1；**13 项 P2**（F-077/F-080/F-084 资金/身份面）。R54 候选：继续轮转新面。
