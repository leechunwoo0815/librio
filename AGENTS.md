# Global Config

> 本文件 = 全局 AGENTS.md（/Users/litianyu/CLAUDE.md，经 .codex/AGENTS.md 软链注入）
> 的完整继承 + 下方「项目附加（librio 专属）」。

## Communication

- 用中文回复，代码、标识符、提交信息保持英文
- 直接给结论，不要奉承和开场白
- 不确定就说不确定，不要猜
- 给方案时附取舍，不要只说"最佳实践"

## Hard Rules (never violate)

- 不执行 `git push --force`、`git reset --hard`、`rm -rf`，除非我逐字明确要求
- 不读取、不复制、不打印 `.env`、私钥、令牌文件的内容
- 不修改与本任务无关的已有文件；新建文件只放在任务涉及的目录
- 破坏性操作（删文件、改数据库、动 main 分支）前先说明影响并等我确认

## Verification

- 改完代码必须运行项目已有的测试/lint/构建来验证，并报告真实结果
- 跑不了就明说"未验证"，禁止说"应该没问题"
- 修 bug 时先复现或定位根因，再动手改；禁止靠猜连续试三处以上
- 测试失败时，报告失败信息并停止，不要自行绕过或删除测试

## Change Discipline

- 最小改动：不做我未要求的重构、改名、格式化
- 一个任务只动相关文件；发现无关问题，报告但不顺手修
- 需求模糊或有两种以上合理实现时，先问，不要替我选
- 新依赖先看项目是否已有同类工具，不重复引入

## Environment

- macOS, zsh
- Node: 优先 pnpm；Python: 优先 uv + venv；不往全局装包
- 装第三方工具必须装进项目内或虚拟环境，不污染系统

## Git Conventions

- Conventional commits: feat/fix/chore/refactor/test/docs
- 提交前检查 `git diff`，只 stage 预期文件
- 不 commit 未完成的代码、调试日志、注释掉的代码块

## Skills

技能库在 `/Users/litianyu/skills/`，用时读路径对应的 `SKILL.md`，不凭记忆假设。

### 核心闭环（功能开发按序执行，每步完成再进下一步）

1. 需求→设计：读 `skills/superpowers/skills/brainstorming/SKILL.md`
2. 写实现计划：读 `skills/superpowers/skills/writing-plans/SKILL.md`
3. 执行计划：读 `skills/superpowers/skills/executing-plans/SKILL.md`，切片纪律遵循 `skills/addy-agent-skills/skills/incremental-implementation/SKILL.md`
4. 测试先行：读 `skills/superpowers/skills/test-driven-development/SKILL.md`
5. 遇 bug/测试失败：读 `skills/superpowers/skills/systematic-debugging/SKILL.md`
6. 声称完成前：必读 `skills/superpowers/skills/verification-before-completion/SKILL.md`
7. 评审：评审标准用 `skills/addy-agent-skills/skills/code-review-and-quality/SKILL.md`，派发流程用 `skills/superpowers/skills/requesting-code-review/SKILL.md`
8. 收尾（merge/PR）：读 `skills/superpowers/skills/finishing-a-development-branch/SKILL.md`

### 按需专项（命中才读）

接口设计→`mattpocock-skills/skills/design-an-interface/SKILL.md`；性能→`addy-agent-skills/skills/performance-optimization/SKILL.md`；安全→`addy-agent-skills/skills/security-and-hardening/SKILL.md`；CI/CD→`addy-agent-skills/skills/ci-cd-and-automation/SKILL.md`；可观测性→`addy-agent-skills/skills/observability-and-instrumentation/SKILL.md`；文档/ADR→`addy-agent-skills/skills/documentation-and-adrs/SKILL.md`；生产发布→`addy-agent-skills/skills/shipping-and-launch/SKILL.md`；废弃迁移→`addy-agent-skills/skills/deprecation-and-migration/SKILL.md`；重构简化→`addy-agent-skills/skills/code-simplification/SKILL.md`

### 优先级与兜底

- 框架/语言实现类任务 → `farmage-skills/skills/` 下对应技术栈 skill
- skill 间指令冲突时：Hard Rules > 本表 > skill 内部指令
- 表中路径失效时扫 `/Users/litianyu/skills/` 找同名或替代，不硬停
- skill 只覆盖到任务的一部分时，其余部分按通用纪律执行

---

# 项目附加（librio 专属）

## 开工必读（每次会话第一步，不可跳过）

- 读 `error_list/README.md`（周期性重做机制）与最新版 `error_list/错误记忆库-全项目-*.md`：
  - §二 根因模式库：新任务涉及的模式，先对照其"防复发动作"
  - §三 防错检查清单：开工前/修复中/声称完成前逐项自查
- 恢复口令：读 `专家意见/项目终态交接-20260807.md`，继续
  （当前唯一权威恢复卡；旧 K3 交接已标取代，留档可查）

## 防复发红线（源自错误记忆库，8 条）

1. 修"一类 bug"必须先 `rg` 全库枚举同类调用点/入口，逐个核对（模式 1：同类漏改）
2. 数值/日期条件写边界矩阵 [-1, 0, +1] 用例（模式 2：边界错误）
3. 新字段/单号/回调/迁移回答契约三维：复用？异步回调？存量回填？（模式 3）
4. 测试走真实 service/API，禁 ORM 伪造/自带公式/恒真断言/空断言；关键修复 RED→GREEN（模式 4）
5. 门禁命令全量复制不缩范围；MySQL-only 检查真跑；报告贴五项原始输出 + 自检表（模式 5）
6. 改基线数字后全库 `rg` 同口径核对；加列/配置走四同步/五方同步（模式 6）
7. 新增能力层必须带调用点 + 端到端测试（模式 7）
8. 改状态机先画允许转移矩阵对照 PRD（模式 8）

## 验证与环境口径（librio）

- pytest 通过数随环境（开发机 789 passed / CI 708+15 skip / 无 MySQL 沙箱 714+9 err）；
  "全绿"结论限定开发机。
- with_for_update 在 SQLite 为 no-op：并发验证用 `scripts/verify_mysql_concurrency.py`
  （独立测试库，MySQL 实测）。
- 金额禁 float、LIKE 用户输入必须 escape_like、时区用应用侧 datetime.now。
- 项目宪法：`CLAUDE.md`（最高法律，冲突时以其与最新 `checkpoint.md` 为准）。
