# LOOP-2 强制闭环自审 · 执行协议（每会话必读 · 零自由裁量）

> 你是 librio 全闭环自检审查的执行器。**所有"通过/失败/完成"的裁决由脚本退出码做出，
> 不由你做出。** 你只负责干活、留证据、更新台账。本文件 + `audit_loop/loop2/LEDGER.md`
> 是你唯一的工作依据；其余文档只在条目指向上才读。

---

## §0 每次会话启动仪式（强制，禁止跳过任何一步）

1. 完整读本文件。
2. 完整读 `audit_loop/loop2/LEDGER.md`。
3. 找到表中**第一行** status ∉ {VERIFIED, BLOCKED, WAIVED} 的条目 → 这是你本会话唯一任务。
   禁止同时处理多项；禁止跳行；禁止"顺手"做别的。
4. 若不存在未闭环条目：运行 `venv/bin/python scripts/loop_check.py --mode full`，
   原样报告输出后结束会话。你无权宣布完成，只有该脚本退出码 0 才算完成。

## §1 状态机（唯一合法流转，违者本轮作废）

```
AUDIT ──完成审查──> VERIFIED
TODO ──复现成功──> REPRODUCED ──改完──> FIXED ──针对性绿──> GREEN ──批次门禁绿──> VERIFIED
任何非终态 ──断路器──> BLOCKED
```

- 每次流转前**先落证据**（§2/§3 指定路径），再改台账行，再 `git commit`（单主题，
  Conventional Commits）。没有证据的流转 = 无效，校验器会拦下。
- attempts 列：每尝试一次修复 +1。达到 3 仍不绿 → 必须 BLOCKED（§5）。

## §2 审查项（status=AUDIT）的执行

1. 按条目维度，用 `rg` **全库枚举**同类调用点/入口，逐个核对（防复发红线：同类漏改）。
   审查方法优先写一次性扫描脚本放 `audit_loop/`（先例：scan_commit_after_write.py）。
2. 每个疑点必须读代码或实测后定性，只有两种结论：**发现（F）** 或 **干净（C）**。
   证据要求：方法 / 证据（命令原始输出或 file:line）/ 核对明细 / 排重说明。
3. 轮次文件写入 `audit_loop/rounds2/L2-<id>.md`（格式仿 `audit_loop/rounds/R01*.md`）。
4. 每个发现 → 台账**追加一行**：id 取 L2-0NN 顺延，phase=fix，status=TODO，
   title 含严重级（P1/P2/P3），notes 写依据与定位（file:line）。
5. **零发现是合法结论**，但必须写明已查范围与证据；禁止为凑数硬报，也禁止偷懒不查。
6. 轮次文件提交后，将该 AUDIT 行 evidence 填轮次文件路径、status 改 VERIFIED、提交。

## §3 修复项（status=TODO→VERIFIED）的执行

1. **TODO→REPRODUCED**：先写失败测试（RED）或复现脚本并真跑，输出存
   `audit_loop/fix-evidence/L2-<id>-repro.txt`。**复现不了 → 直接走 §5 断路器，禁止盲改。**
2. **REPRODUCED→FIXED**：最小改动修复，只改与本条直接相关的文件；金额 Decimal、
   LIKE escape_like、时区应用侧 datetime.now（项目宪法口径）。
3. **FIXED→GREEN**：针对性测试转绿：
   `venv/bin/python -m pytest tests/ -q --tb=short -p no:cacheprovider -k "<相关测试>"`
4. **GREEN→批次门禁**：每完成 5 个修复项（或一个维度干完），运行
   `bash scripts/loop_gate.sh full`（约 12 分钟，勿中断；MySQL 未启动会 ABORT，先启动 MySQL）。
   退出码非 0 → 修好失败关再继续；**禁止带着红门禁推进下一项。**
5. 批次门禁绿 → 相关条目填 evidence（引用 `audit_loop/loop2/gate-runs/` 真实日志路径）与
   commit hash，status 改 VERIFIED，提交。

## §4 门禁命令（唯一裁决者）

| 场景 | 命令 |
|---|---|
| 单项快门禁（每次改完） | `bash scripts/loop_gate.sh quick`（可追加 `-k 测试名`） |
| 批次/收尾全量门禁 | `bash scripts/loop_gate.sh full` |
| 台账一致性 | `venv/bin/python scripts/loop_check.py --mode ledger` |
| 完工判定（唯一） | `venv/bin/python scripts/loop_check.py --mode full` |

- **退出码是唯一裁决**。禁止读输出文本后自行判定"其实过了"。
- 门禁日志自动落 `audit_loop/loop2/gate-runs/`；台账 evidence 必须引用真实存在的文件。
- 禁止以任何方式缩小门禁范围、跳过任何一关（含 MySQL-only 关）。

## §5 断路器（防死循环，强制）

同一项 attempts=3 仍不绿：
1. 台账该行 status 改 BLOCKED，notes 写：失败现象 + 关键 traceback 摘要 + 已试的 3 种方案。
2. 在 `audit_loop/loop2/ESCALATE.md` 追加一节（条目 id / 现象 / 已试方案 / 建议人工切入点）。
3. 提交后**跳到下一未完成条目**继续。禁止对 BLOCKED 项继续尝试、弱化断言、删测试绕过。
4. 若全部剩余项都是 BLOCKED：运行 `loop_check.py --mode ledger`（会输出"升级人工"并退出码 3），
   原样报告后结束会话，等待专家/用户处置。

## §6 禁止清单（违反 = 本轮作废 + 记入 ESCALATE.md 自查段）

1. 自行宣布某项/某批/整体"通过"或"完成"（唯一裁决 = 脚本退出码）。
2. 修改断言使其变宽松、删除失败测试、注释掉测试、伪造证据文件。
3. 缩小门禁命令范围或以任何理由跳过某一关。
4. 顺手重构/改名/格式化与本条无关的代码；修改本文件、`scripts/loop_gate.sh`、
   `scripts/loop_check.py`、`audit_loop/loop2/driver.sh`（认为工具有问题 → 写进 ESCALATE.md）。
5. 说"应该没问题"、"理论上可以"、"正常情况下"。
6. 一次性输出整文件全量代码（只输出 diff 与位置，防截断）。
7. 读取或打印 `.env`、私钥、令牌内容；`git push --force`；`reset --hard`。

## §7 收尾（全部条目 VERIFIED/WAIVED 后）

1. 写 `audit_loop/loop2/FINAL_REPORT.md`，必含：
   - 统计：审查维度数 / 发现总数（按级）/ 修复数 / BLOCKED 数 / WAIVED 数
   - 全量门禁最后一次 PASS 的 `gate-runs/` 日志路径 + pytest/behave/ruff 原始计数
   - **基线同步自查（E-09）**：pytest 数 / ruff files / alembic head / 迁移范围 / 配置数 /
     API 数 / 表数 / behave 数，逐项对比 checkpoint.md 与 专家意见/项目交接-20260809.md，
     有漂移 → 同步五件套文档（这也是一个台账条目，先登记再修）
   - BLOCKED/WAIVED 清单与理由（交付给专家复审）
2. `git add` 全部改动并提交；确保 `git status` 干净。
3. 运行 `venv/bin/python scripts/loop_check.py --mode full`，原样输出结果。退出码 0 = 允许停工。
