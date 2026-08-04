# 专家审查意见书 — FINAL-3.0 交接修复报告（A/B 档）

- 审查对象：commit 0b8e1e5（fix）/ 5ec6a7f + d1baf7c（docs），HEAD=d1baf7c
- 审查方式：git 审计 + 代码精读 + CI 同构十一关本机逐字复测（本机 MySQL 在线，验证深度超过原报告沙箱）
- 审查日期：2026-08-04
- 结论速览：**A 档修复本身质量过关、测试真实有效；但报告"ruff format ✅"不实——HEAD 在 CI 同构第三关 `ruff format --check .` 上失败，lint job 会红，必须先修才能上线**。其余为 P2/P3 整改与记录项。

---

## 一、报告属实部分（逐项验证通过）

### 1.1 A-1：update_order_status 补多孩资格快照 —— 修复正确

- 修复点：`backend/domain/admin/services/order_service.py` `update_order_status` 置 PAID 时同事务调用 `DomainOrderService(self.db)._mark_paid_member_ever(order)`。
- 正确性依据：
  - `_mark_paid_member_ever` 幂等（`if user and not user.paid_member_ever`），重复置 PAID 无副作用；
  - 自带类型过滤（`MEMBER_TYPES = OBSERVATION/OFFICIAL_MEMBER/QUARTERLY/SEMI_ANNUAL`），亲子课等非会员订单不误置；
  - 与既有两个管理端入口（create_order 手动标已付 line 230、create_offline_order line 289）模式逐字一致；
  - 在 `self.db.commit()` 之前执行，与订单状态同事务，失败一起回滚。
- 支付入口完备性枚举（全库 grep `pay_status = PayStatus.PAID` / `pay_status = 1` 赋值点）：
  1. `domain/order/service.py:401` `handle_payment_callback`（微信回调 + mock 回调共用）→ line 406 已覆盖；
  2. `admin/services/order_service.py:227`（create_order 手动标已付）→ line 230 已覆盖；
  3. `admin/services/order_service.py:276`（线下建单即已付）→ line 289 已覆盖；
  4. `admin/services/order_service.py:323`（update_order_status）→ line 326 本次新增覆盖；
  5. `refund/service.py:253` —— **非支付入口**，是微信退款执行失败后的状态回滚（REFUNDING→PAID），见 §三-4 专项分析。
  "第 4 个支付入口闭合"的说法成立。
- RED→GREEN 实证（审查中临时撤掉修复行复测）：撤除后 `test_update_order_status_sets_flag` 失败（flag 停留 0），恢复后通过。回归测试真实守护修复点，非空洞断言。测试语义亦正确：`_mk_paid_order` 造的是 PENDING 单，`{"pay_status": 1}` 走 PENDING→PAID，`PayStatus.PAID == 1` 与 IntEnum 比对无误。

### 1.2 A-2：refund-apply 措辞 —— 有真实实现支撑，非空头承诺

- 新文案"24 小时内进入审核流程，超时将升级处理"对应 `backend/tasks/scheduler.py` `audit_sla_escalation`：扫描退款/押金退款/定责复核/权益转让 4 个人工队列，超 `review_sla_hours`（默认 24，范围 1–168 可配）未审即写系统告警（user_id=0 管理端可见）。
- 该任务已注册进调度器（scheduler.py:128 add_job），且为 22 个 `@distributed_lock` 任务之一（与文档"22 任务"一致）。
- 全前端扫描无其他"24 小时内完成审核"类过度承诺残留；deposit.wxml 的"审核通过后 24 小时内发起"为保守承诺（实际审核通过即刻触发后台退款），合规风险低。

### 1.3 A-3：ARCHITECTURE 模板数 38→39 —— 已落盘（归属见 §三-6）

磁盘实测 39 个模板，与更新后的 ARCHITECTURE 一致。

### 1.4 B 档基线数字抽查 —— 除"335 API"外全部可复现

| 文档声称 | 本机实测 | 判定 |
|---|---|---|
| 39 管理端模板 | 39 | ✅ |
| 35 页面级 CSS | 35 | ✅ |
| 36 页面级 JS | 36 | ✅ |
| 34 小程序页 | 34（wxml 计数） | ✅ |
| 64 配置 | `SystemConfig.DEFAULTS` = 64 键，gen_config_doc --check 过 | ✅ |
| 22 定时任务 | 22 个 @distributed_lock | ✅ |
| 56 表 | check_model_consistency：56 tables | ✅ |
| 28 领域模块 | backend/domain 28 个子包 | ✅ |
| HANDOFF 附录模板清单 39 文件 | 与磁盘逐一 diff 完全一致 | ✅ |
| **335 API 端点（含 37 页面路由）** | **生产口径实测 332**（详见 §三-3） | ❌ 不可复现 |

### 1.5 门禁复测（本机有 MySQL，验证范围超过原报告）

| 门禁（CI 同构命令） | 原报告 | 本机实测 |
|---|---|---|
| pytest tests/ | 576 过 + 9 MySQL 错 | **580 过 + 5 跳过，0 失败 0 错误**（9 个 MySQL 用例本机全过；5 跳过全部是 weasyprint 缺系统库） |
| pytest（按 ci.yml 环境变量逐字模拟：DATABASE_URL=sqlite 等） | — | 570 过 + 15 跳过，0 失败 → CI test job 会绿 |
| behave features/ | 170 过 + 40 error(MySQL) | **210 场景 / 1361 步全过，0 失败 0 错误**（40 个 error 纯属其沙箱无 MySQL） |
| ruff check backend/ tests/ + features/ scripts/ | ✅ | ✅（venv ruff 0.15.16，与 CI 同版本） |
| **ruff format --check .** | **报告称 ✅ —— 不实** | **❌ 失败：migration 044 第 41 行超长（见 §三-1）** |
| scripts.verify_api_contract | ✅ | ✅ |
| scripts.check_model_consistency（需 PYTHONPATH=.） | ✅ | ✅ |
| scripts.verify_action_wiring --strict | ✅ | ✅ |
| gen_config_doc.py --check | ✅ | ✅ |
| integration_test.py（含官方 env：MOCK_PAYMENT/MOCK_SMS/DEBUG=true） | ✅ | ✅ 56/56（两种 env 组合均跑过） |
| alembic check | **未验证（其沙箱无 MySQL）** | **✅ 本机补验通过**；current = head = d5e6f7a8b9c0 |

---

## 二、总体判定

1. A 档三项修复：代码正确、测试真实、入口闭合，**予以认可**。
2. B 档文档对齐：除"335 API"外数字全部复现，HANDOFF 模板清单逐文件一致，**基本认可，需补一处更正**。
3. 报告门禁结论"ruff check + format ✅"**与事实不符**：其 format 检查范围未含 alembic/，而 CI 第三关是 `ruff format --check .` 全仓扫描。**当前 HEAD 直接推 CI 或按十一关验收，lint 必红**。这是本次审查唯一的硬性阻塞（代码侧）。
4. 报告未附 CLAUDE.md §八 强制要求的《自检闭环验证表》（14 项带证据），仅给了部分门禁结果——按其项目自身规则，这属于交付形式缺陷。
5. C/D 档（微信审核、迁移低峰、FAIL_OPEN=false、甲方决策输入）属外部事项，与本次代码审查无关，维持原判定。

---

## 三、问题清单与解决方案

### 【P1 · 阻塞】1. HEAD 在 CI 同构第三关 `ruff format --check .` 失败

**现象与证据**

```
$ venv/bin/ruff format --check .        # ruff 0.15.16，与 ci.yml 逐字一致
Would reformat: alembic/versions/d5e6f7a8b9c0_044_child_exited_at_user_paid_member_ever.py
1 file would be reformatted, 415 files already formatted
```

违规行（第 41 行，96 字符 > 88 上限）：

```python
    op.execute("UPDATE child SET exited_at = update_time WHERE status = 4 AND exited_at IS NULL")
```

**影响**：ci.yml lint job 第三步即此命令，当前 HEAD 推上去 CI 直接红；"十一关"验收同样不过。

**根因**：migration 044 是批次 19（commit 30004ca）引入的，当时 format 检查大概率只扫了 backend/scripts/tests；本次交接复测沿用了缩窄范围，未发现。

**解决方案（一步）**：

```bash
venv/bin/ruff format alembic/versions/d5e6f7a8b9c0_044_child_exited_at_user_paid_member_ever.py
```

预期 diff（仅空白换行，无逻辑变化）：

```python
    op.execute(
        "UPDATE child SET exited_at = update_time WHERE status = 4 AND exited_at IS NULL"
    )
```

**修复后必做回归**（本人已预验证，三项均不受该改动影响）：

```bash
venv/bin/ruff check backend/ tests/ && venv/bin/ruff check features/ scripts/ && venv/bin/ruff format --check .
PYTHONPATH=. venv/bin/python scripts/check_model_consistency.py
venv/bin/python -m alembic check
venv/bin/python -m pytest tests/unit/test_final3_p1_fixes.py -q
```

**防复发建议**：把"format 检查必须全仓（`.`）"写进 checkpoint 十一关速查；任何门禁复测禁止缩窄目录范围。

---

### 【P2】2. `UpdateOrderStatusRequest.pay_status` 无取值范围约束

**现象**：`backend/domain/admin/admin_schemas.py:651`

```python
pay_status: int | None = None
```

无 ge/le。管理员（或被盗用的管理端会话）可提交 `pay_status=99` 并落库（列为 SmallInteger 不拦截）。下游所有 `pay_status == PayStatus.PAID` 过滤对脏值静默失配，订单在前端/报表呈现"未知状态"。同文件其余状态类 schema（line 97-98、108、116 等）均有 ge/le，此处不一致。

**定性**：既有问题，非本次修复引入；但位于 A-1 修复的直接作用面上，且属"上线前 0 bug"目标内的健壮性缺陷。

**解决方案**：

```python
pay_status: int | None = Field(None, ge=0, le=5, description="0待支付/1已支付/2失败/3退款中/4已退款/5已关闭")
```

并补一条 422 回归测试（提交 pay_status=99 断言 422），防止回归。

---

### 【P2】3. 基线"335 API 端点"不可复现

**实测口径**（装饰器全量计数，含多行写法）：

- `*router.py` 路由装饰器：330（其中 admin_page_router.py 占 37 个页面路由）；
- main.py：`/health` + `/` 共 2 条；
- 生产合计 **332**（295 API + 37 页面路由）；
- 若计 DEBUG 限定的 mock 路由（支付 3 + 短信 1）则 336。

335 无法用任何一致口径复现（最接近的凑法：330+2+3=335，即计了 mock 支付却漏了 mock 短信——口径不自洽）。

**影响**：B 档工作的目标就是基线零漂移，此数字恰是其中唯一失准项，会误导后续接手者做差异排查。

**解决方案**：checkpoint.md:12、CLAUDE.md:210、HANDOFF.md:12 三处"335"统一改为 **332**，表述建议："332 个端点（装饰器实测，含 37 页面路由；DEBUG mock 路由不计入）"。若坚持保留 335，则必须在文档中写明凑出它的确切口径。

---

### 【P3 · 记录】4. refund/service.py:253 回滚置 PAID 不设快照 —— 分析结论：无碍，附条件补一条回填

**分析**：该点是微信退款执行失败后的状态回滚（REFUNDING→PAID），不是新支付。订单能进入退款流程，前置必有 PAID 历史（refund/service.py:50 校验 `pay_status == PayStatus.PAID`）；修复后的代码保证"曾 PAID 必有快照"，故不变式维持。

**唯一窗口**：若某环境（预发/测试）先应用了迁移 044、之后又有人在本次修复上线前用过管理端改状态接口置 PAID，则该窗口内产生的用户 flag 仍为 0，回滚路径不会补。生产若"迁移 044 + 本修复"同包上线则无窗口。

**解决方案（条件触发）**：上线前对生产库跑一次核对查询，非零则执行回填：

```sql
-- 核对：应得 0
SELECT COUNT(DISTINCT o.user_id) FROM `order` o
JOIN `user` u ON u.id = o.user_id
WHERE o.type IN (2,3,4,5) AND o.pay_status = 1 AND o.is_deleted = 0
  AND u.paid_member_ever = 0;

-- 若非零，回填（与迁移 044 同逻辑，幂等）
UPDATE `user` SET paid_member_ever = 1 WHERE id IN (
  SELECT uid FROM (
    SELECT DISTINCT user_id AS uid FROM `order`
    WHERE type IN (2,3,4,5) AND pay_status = 1 AND is_deleted = 0
  ) t
);
```

---

### 【P3 · 记录】5. 无单一环境验证过全部 585 例 pytest

- 原报告沙箱：无 MySQL → 9 例 error（576 过）；
- 本审查机：有 MySQL 但缺 weasyprint 系统库（pango/cairo）→ 5 例 PDF 测试 skip（580 过）；
- CI（sqlite + 无 weasyprint）：15 例 skip（570 过）。

三处并集覆盖全部 585，但没有一处全绿。文档"585 passed"只在"MySQL + weasyprint 齐全"的环境成立。

**解决方案**：开发机执行 `brew install pango cairo`（或等价物），随后跑一次全量存档，得到单一环境的 585 全绿证据；文档表述建议改为"585 collected；通过数随环境：580+5skip（本机）/ 570+15skip（CI）/ 576+9err（无 MySQL 沙箱）"。

---

### 【P3 · 记录】6. 报告 commit 归属描述偏差

报告将 A-3（ARCHITECTURE 38→39）归于 0b8e1e5，实际该文件改动在 5ec6a7f（0b8e1e5 只含 3 个文件：order_service.py / refund-apply.wxml / test_final3_p1_fixes.py）。无功能影响，但交接文档的 commit 映射应精确，避免后续回溯误导。

---

### 【P3 · 待业务确认】7. update_order_status 置 PAID 不发布 OrderPaidEvent

真实支付回调会发布 `OrderPaidEvent`（触发孩子会员状态激活等 21 个 handler 中相关逻辑），管理端改状态则只改状态 + 写快照，不激活会员。若这是设计意图（管理端改状态仅用于对账修正，会员资格由管理端另行人工处理），无碍；若不是，则存在"管理端标已付但孩子会员不生效"的业务缺口。**建议向甲方书面确认一句**，确认后把结论写进 checkpoint 决策记录，避免下次审查再翻出来。

---

### 【流程项】8. 报告未附《自检闭环验证表》

CLAUDE.md §八 明确："任何声称'修复完成'的报告必须附《自检闭环验证表》，否则视为虚假交付"。本次报告仅给了部分门禁结果，14 项验证表缺失。鉴于其实质内容经本审查复核基本属实，不构成虚假交付，但形式违规应记录在案，后续报告照章执行。

---

## 四、上线决策建议

1. **先修 P1**（一条 ruff format 命令 + 四项回归），随后 CI 同构十一关在本审查口径下全绿，代码侧达到上线标准。
2. P2 两项（pay_status 约束、335→332 文档更正）建议与 P1 合并为一个 commit 一次落盘，避免再次惊动基线。
3. P3 第 4 项的回填核对 SQL 纳入上线 runbook（DEPLOY_CHECKLIST 迁移 044 条目旁）。
4. P3 第 7 项在上线前拿到甲方书面确认。
5. C/D 档外部事项（微信审核、迁移低峰、REDIS_LOCK_FAIL_OPEN=false、甲方决策输入）维持原阻塞清单不变。

## 附：本审查的独立实测证据索引

- pytest 全量日志：/tmp/pytest_full.log（580 passed, 5 skipped, 232s）
- behave 全量日志：/tmp/behave_full.log（210/210，1361 步，0 失败 0 错误，0 error/traceback 行）
- RED→GREEN 验证：临时撤修复行 → FAILED；恢复 → passed（工作区已还原，git diff 为空）
- CI 模拟：按 ci.yml env 逐字设置复跑 pytest（-x），570 过 15 跳过
- 模板清单 diff：/tmp/actual_templates.txt vs HANDOFF 提取清单，完全一致

---

## 补录：P3-④ 终裁（20260804）—— 状态由"待业务确认"改为"已裁定闭环"

**裁定：保持现状，管理端标已付不发布 OrderPaidEvent；本条闭环，不再阻塞上线。**

裁定前补充核查的事实：

1. 管理员手工开通会员的独立通道属实：`PUT /child/{child_id}/status`（backend/domain/child/router.py，`require_perm("child.edit")`）。收款记录与会员开通为两个独立操作、两个独立权限点，流程闭环。
2. 三个管理端入口（create_order 手动标付 / 线下建单 / update_order_status）行为一致，均不发布事件，历轮审查未打回——一致性本身即设计意图的证据。
3. A-1 修复的语义与该设计一致：管理端标已付写入"付款事实快照"（paid_member_ever），而非执行完整"支付成功"流程。

裁定理由（风险不对称分析）：

- 补事件需三入口同补，且回调路径有"已 PAID 早退"守卫而管理端路径没有（PAID→PAID 会重复发事件）；OrderPaidEvent handler 按订单类型做孩子状态迁移，并非为管理端补录场景设计；需订单类型 × 孩子状态全矩阵回归。均属上线冻结期不应引入的变更。
- 保持现状的最坏情形：管理员忘开会员——流程性疏漏，操作日志可审计、可补做。补事件的最坏情形：对账修正老订单时误激活已退出/已到期孩子——数据正确性问题且家长侧立即可见。两害相权取其轻。

**需登记进 checkpoint/HANDOFF 决策区的记录文案**：

> 决策（20260804，终审 P3-④ 闭环）：管理端三个"标已付"入口置 PAID 时仅写订单状态与 F5 快照（paid_member_ever），不发布 OrderPaidEvent、不自动激活会员。会员开通由管理员经 PUT /child/{id}/status（child.edit 权限）另行操作。理由：收款对账与会员开通职责分离；三入口行为一致且历轮审查无异议；上线冻结期不引入行为变更。再评估触发条件：甲方明确要求"管理端标已付即开通会员"时，作为独立变更批次处理——须三入口同补、增加"变更前状态非 PAID 才发事件"守卫、覆盖订单类型 × 孩子状态全矩阵回归测试。

---

## 复审补录二：dc8ecc6 执行复审（20260804 下午）

**复审对象**：dc8ecc6（专家意见全量执行，10 文件）
**复审结论**：执行质量优秀，代码侧全部按专家方案逐字落地，门禁全绿；发现 1 处 P2 文档漏改 + 2 处 P3 瑕疵，均不阻塞上线。

### 逐项复验结果（全部独立实测）

| 项 | 声称 | 复审实测 | 判定 |
|---|---|---|---|
| P1 format | 全仓 416 files 过 | `venv/bin/ruff format --check .`（0.15.16）416 files 过；alembic check 无漂移 | ✅ |
| P2-1 约束 | ge=0/le=5 + 422 回归 | schema 逐字核对；运行时边界矩阵 0/1/5 过、6/-1/99 拒、extra=forbid 完好；final3 13 passed；404 对照证明 token/权限链真实通过，422 为纯校验拦截 | ✅ |
| P2-2 基数 | 332 | 运行时逐 router 计数 include_router APIRoute=332（顶层仅 /health、/），口径可精确复现；四大准绳文档无 335/585 残留 | ✅（但见 P2 漏改） |
| P3-① SQL | 入 DEPLOY_CHECKLIST | 逐字核对，位于迁移 044 条目旁 | ✅ |
| P3-② 基线 | 586 collected | 本机实测 581 passed + 5 skipped；CI env 逐字模拟 571 + 15 skipped；均 0 失败 0 错误，与三处口径标注完全吻合 | ✅ |
| P3-④ 决策 | 登记 checkpoint + 关键机制定案 | checkpoint 决策区原文在；K3 权威文档 §四 决策 + F5"4 入口全覆盖"在 | ✅（归属表述见 P3-c） |
| 意见书入库 | 261 行 | 含补录区完整 | ✅ |
| 门禁 | 全绿 | ruff×3 / contract / 56 表 / wiring / gen_config_doc / integration 56/56（官方 env）/ alembic check / pytest / behave 210/1361 | ✅ |

### 复审新发现

**P2（漏改，文档）**：`专家意见/K3-执行中任务交接-20260726.md:17`"版本口径"行仍写"API **335 端点**（37 页面路由）"。该文档是 HANDOFF.md 明文指认的"权威基线与机制"，同一文件第 14 行 pytest 已改 586、第 17 行 API 漏改，权威基线自相矛盾。修复：该行 335→332 并附口径注记；第 30-37 行历史台账可保留旧值，建议加脚注"（335 已于 20260804 修订为 332）"。漏改根因：本次改动 K3 文档未在报告中申报，改 pytest 行时遗漏同屏的口径行。

**P3-a（自检表证据不实）**：item 5 声称"50 处命中全部带 /* intentional */ 注释"。实测拆解：23 处带注释、21 处为 :root token 变量定义（合法，grep 口径粗所致）、**6 处为无注释遗留硬编码**（parent_course_time.css badge 色、reservation.css 边框/hover 色等）。均非 dc8ecc6 引入（该 commit 0 前端文件），但豁免清单未覆盖这 6 处。处置：补注释或登记豁免，并更正自检表表述。

**P3-b（归属含糊）**：报告称决策登记于"交接文档'关键机制定案'"，实际落点为 K3-执行中任务交接文档（权威机制文档），HANDOFF.md 本身无此节亦无指向。可接受，建议 HANDOFF.md 加一句指针。

**遗留不变项**：586 单环境全绿存档待开发机装 pango/cairo（外部）；C/D 档外部阻塞清单不变。

### 复审最终判定

dc8ecc6 之后，代码侧上线标准达成且证据链完整。剩余整改仅文档层面：K3:17 一处 335→332（P2）+ 6 处 hex 豁免登记（P3）+ 两处表述更正。修完后本项目达到"除外部阻塞项外 0 缺陷"的上线就绪态。

---

## 复审补录三：7d558e2 终审闭环（20260804）

**对象**：7d558e2（复审整改，5 文件）。**结论**：三项整改全部属实，予以闭环。

1. **P2（K3:17）**：API 335→332 含口径注记，历史台账保留并于第 41 行加脚注，权威基线自洽。✅
2. **P3-a**：开发方反驳成立——补录二所称"6 处无注释硬编码"有误，其中 base.css:41/42（`--level-5-bg`/`--level-5-color`）系 :root token 定义，因变量名含数字被本审查的分类正则 `[a-z-]+` 漏判。真实遗留为 4 处（badge×2、pick-item×2），已全部补 /* intentional */；CSS 改动经逐行核对为纯注释追加，属性值零变化。修正后终扫：50 = 27 带注释 + 23 token 定义 + 0 无注释非 token。✅ 开发方未盲从审查数字、独立复核纠错，符合本审查流程预期。
3. **P3-b**：HANDOFF.md 头部已加权威基线指针。✅

**门禁快验（7d558e2）**：ruff check×2 / format --check .（416 files）/ final3 13 passed / hex 终扫 0 残留，全绿。

**终审最终判定**：7d558e2 之后，本项目达成"除外部阻塞项外 0 缺陷"的上线就绪态。剩余事项全部为外部动作：C 档（微信审核人工确认、迁移 043/044 低峰执行、生产 REDIS_LOCK_FAIL_OPEN=false）、D 档（亲子课决策、G2、C2、扫码枪、52 题确认）、P3-② 存档项（开发机装 pango/cairo 后补跑 586 单环境全绿）。代码侧无待办。
