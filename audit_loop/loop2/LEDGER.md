# LOOP-2 台账（唯一数据源 · 全闭环自检审查）

> 规则：本表是 LOOP-2 的唯一事实源。任何会话开工先读本表，从第一行未闭环条目干起。
> 状态词表（仅这些合法）：`AUDIT`（审查项）/ `TODO` / `REPRODUCED` / `FIXED` / `GREEN` /
> `VERIFIED`（闭环）/ `BLOCKED`（断路器，升级人工）/ `WAIVED`（仅专家/用户可豁免）
> 格式铁律：表格 9 列，一行一项，禁止合并/换行/删列。校验器 `scripts/loop_check.py` 机器解析，
> 格式损坏 = 全员停工先修表。
> evidence 列：从仓库根起算的相对路径，必须真实存在且非空（VERIFIED 硬性要求）。

| id | phase | dimension | title | status | attempts | evidence | commit | notes |
|----|-------|-----------|-------|--------|----------|----------|--------|-------|
| A-01 | audit | 全维复审 | 事务/锁/先查后改/事件自commit/死信（原维度1）——重点复核 118 项修复引入的回归 | AUDIT | 0 | | | 产出 rounds2/L2-A-01.md + 发现入台账 |
| A-02 | audit | 全维复审 | 五状态机矩阵+前置校验（原维度2）——对照状态转移矩阵逐台核对 | AUDIT | 0 | | | 同上 |
| A-03 | audit | 全维复审 | 金额 float/元分转换/回调幂等/退款公式（原维度3） | AUDIT | 0 | | | 同上 |
| A-04 | audit | 全维复审 | API 契约/response_model/api.js 对齐（原维度4） | AUDIT | 0 | | | 同上 |
| A-05 | audit | 全维复审 | 小程序绑定/生命周期/网络兜底/iOS 虚拟支付（原维度5） | AUDIT | 0 | | | 同上 |
| A-06 | audit | 全维复审 | 注入/data-action/权限码种子（原维度6） | AUDIT | 0 | | | 同上 |
| A-07 | audit | 全维复审 | 定时任务锁/时区/大表/错峰（原维度7） | AUDIT | 0 | | | 同上 |
| A-08 | audit | 全维复审 | 慢查询/索引/软删/迁移漂移（原维度8） | AUDIT | 0 | | | 同上 |
| A-09 | audit | 全维复审 | 文档漂移/DEFAULTS/TTL缓存审计（原维度9） | AUDIT | 0 | | | 同上 |
| A-10 | audit | 全维复审 | 测试真实性：假断言/业务含义/RED守护（原维度10） | AUDIT | 0 | | | 同上 |
| A-11 | audit | 全维复审 | 敏感日志/trace_id/ exc_info（原维度11） | AUDIT | 0 | | | 同上 |
| A-12 | audit | 全维复审 | 上传路径遍历/文件删除穿越（原维度12） | AUDIT | 0 | | | 同上 |
| A-13 | audit | 全维复审 | N+1/无 limit 查询（原维度13） | AUDIT | 0 | | | 同上 |
| A-14 | audit | 全维复审 | 隐私合规/reload 等（原维度14） | AUDIT | 0 | | | 同上 |
| A-15 | audit | 基线一致性 | pytest/ruff/配置/API/表/迁移 数字全库 grep 同口径（原维度15，E-09 专项） | AUDIT | 0 | | | 同上 |
| A-16 | audit | 交叉维度 | 定时任务×状态机 / 定时任务×资金 / 配置×退款公式（原 X.1-X.3）+ R2+ 攻击面换面抽检 | AUDIT | 0 | | | 同上 |
| A-17 | audit | 增量面 | R160 封卷后全部新提交（bb03e3d..HEAD）逐提交审查 + monitor_gates 返工后复审 | AUDIT | 0 | | | 同上 |
| L2-001 | fix | 门禁工具 | monitor_gates.py 过 ruff format（P1-1）：format 后 check×2+format --check . 全绿 | VERIFIED | 1 | 专家意见/门禁监控工具返工复审-20260809.md | d4c5c23 | 专家复审亲验三关全绿 |
| L2-002 | fix | 门禁工具 | monitor_gates.py 半行缓冲（P2-1）：残行回退缓冲+3条新测试（半行计数/DONE/段名） | VERIFIED | 1 | 专家意见/门禁监控工具返工复审-20260809.md | d4c5c23 | 对抗 C1/C2/C3 专家重跑转绿 |
| L2-003 | fix | 门禁工具 | monitor_gates.py 同 inode 截断重开（P2-2）：size 变化检测+截断测试 | VERIFIED | 1 | 专家意见/门禁监控工具返工复审-20260809.md | d4c5c23 | 对抗 E 专家重跑转绿 |
| L2-004 | fix | 门禁工具 | monitor_gates.py 段名正则收紧+小写 error 判定（P2-3）+测试 | VERIFIED | 1 | 专家意见/门禁监控工具返工复审-20260809.md | d4c5c23 | 对抗 H 专家重跑转绿；补强裁决见复审 §二 |
| L2-005 | fix | 文档 | 更正报告/checkpoint 的 13+5→14+4 与"ruff 0 告警"表述；交接卡 HEAD 机制化处理（P3 簇） | VERIFIED | 1 | 专家意见/门禁监控工具返工复审-20260809.md | d4c5c23 | 复审 §一 逐项亲验 |
