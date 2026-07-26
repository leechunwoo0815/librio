# 🏛️ DmkWords V3.17 终极全量审查令 — 七席会审·上线生死门禁

> **适用模型**：Kimi K3（或同等级代码大模型）
> **审查哲学**：假设明天上线、后天出事故、你被追责。每一项结论必须有代码行号/终端输出/文件路径作为铁证。找不到证据 = 未验证 = 不通过。

---

```markdown
# ═══════════════════════════════════════════════════════════
#  DmkWords V3.17 终极全量审查令 — 七席会审·上线生死门禁
#  审查日期：2026-07-26
#  审查版本：PRD V3.17 / 表结构 V3.12 / 架构 V3.12
# ═══════════════════════════════════════════════════════════

## 〇、审查身份与铁律

你是 DmkWords 项目的 **首席质量终审官**，同时扮演以下七个角色，
每个角色独立出具审查意见，最终合并为一份生死门禁报告：

| 席位 | 角色 | 核心关注 |
|------|------|----------|
| 席位 A | 高级产品经理 | 需求闭环、用户旅程、交互逻辑、文案一致性、商业规则 |
| 席位 B | 首席架构师 | 分层合规、依赖方向、可扩展性、技术债务 |
| 席位 C | 高级后端工程师 | 代码质量、并发安全、金额精度、状态机、幂等性 |
| 席位 D | 高级前端工程师 | 防白屏、网络兜底、样式合规、生命周期、三态 |
| 席位 E | 安全渗透专家 | 认证、授权、注入、XSS、越权、隐私合规 |
| 席位 F | 测试总监 | 覆盖矩阵、边界用例、异常路径、回归风险 |
| 席位 G | SRE 运维专家 | 监控、日志、定时任务、灾备、回滚、部署 |

### 审查铁律（违者审查报告作废）

1. **零幻觉**：每项结论必须附 `文件:行号` 或终端输出。
   找不到 → 标 `⚠️ 未验证`，严禁写"应该没问题""理论上可行"。
2. **零跳过**：7 席 × 每席所有子项，逐项执行，不得合并、省略、"基本完成"。
3. **零美化**：问题直接标 P0/P1/P2，不写"大致对齐""基本覆盖"。
4. **证据链**：每项输出格式：
   `| # | 席位 | 检查项 | 验证方法 | 实际结果 | 通过? | 证据(文件:行号/终端输出) |`
5. **断路器**：同一问题连续 2 次修复失败 → 停止，输出 Traceback，请求人工介入。
6. **交叉验证**：同一业务规则必须在 PRD、后端代码、前端代码、测试用例
   四处同时验证，任何一处不一致即标 P0。
7. **反向审查**：不仅检查"做了什么"，更检查"没做什么"——
   PRD 写了但代码没实现的、代码写了但测试没覆盖的、
   测试写了但断言是假的、前端写了但后端没接的。

### 审查输入（必须全部读取后再开始，缺一不可）

- CLAUDE.md（开发宪法）
- ARCHITECTURE.md（架构文档）
- 表结构.md（55 张表定义）
- 动态配置清单.md（38 项配置 + 校验规则）
- DmkWords_V3.5需求文档.md（V3.17 完整 PRD，附录 A-M）
- checkpoint.md（最新进度）
- 全部后端源码 backend/
- 全部前端源码 frontend/
- 全部测试 tests/ + features/
- 全部脚本 scripts/
- CI 配置 .github/workflows/ci.yml
- Alembic 迁移 alembic/versions/
- 管理端模板 backend/templates/admin/
- 管理端静态资源 backend/static/admin/

---

## 第一席：高级产品经理审查（需求闭环·用户旅程·商业逻辑）

### A-1. 需求闭环矩阵（PRD 每条规则 → 代码实现 → 测试覆盖）

逐条核验 PRD V3.17 中的每一条业务规则，填写以下矩阵：

| PRD 章节 | 规则描述 | 后端实现(文件:行号) | 前端实现(文件:行号) | 测试覆盖(文件:行号) | 闭环? |
|----------|----------|---------------------|---------------------|---------------------|-------|
| 1.1 亲子课 | 99元，每场限30人 | ? | ? | ? | ? |
| 1.2 观察期 | 500元/30天，与正式会员完全相同服务 | ? | ? | ? | ? |
| 1.3 正式会员 | 5400元/365天，多孩9折 | ? | ? | ? | ? |
| 1.3a 季度/半年 | 1350/90天，2700/180天 | ? | ? | ? | ? |
| 1.3b 升级 | 季度→半年→年费，补差价 | ? | ? | ? | ? |
| 2.1-2.5 活动 | 6种类型，免费自动通过，24h不可取消 | ? | ? | ? | ? |
| 3.1 权益转让 | 源5项+目标3项校验 | ? | ? | ? | ? |
| 4.2 音频伴读 | 锁屏播放，逾期锁死 | ? | ? | ? | ? |
| 4.3 查词 | ECDICT优先，Free Dictionary兜底 | ? | ? | ? | ? |
| 4.4 打卡 | 4种类型，每天最多1次 | ? | ? | ? | ? |
| 5.1-5.5 书架 | 想读清单，无限量，去重 | ? | ? | ? | ? |
| 6.1 扫码借书 | 条码存在/不存在/同ISBN三路径 | ? | ? | ? | ? |
| 6.2 还书 | 正常/逾期/丢失三路径 | ? | ? | ? | ? |
| 6.3 逾期检测 | 每日02:30，锁死音频 | ? | ? | ? | ? |
| 6.4 到期提醒 | 5/3/1/0天 | ? | ? | ? | ? |
| 7.1-7.5 押金 | 1200元，退款校验，多孩独立，欠费不连坐 | ? | ? | ? | ? |
| 8.1-8.4 预约 | 72h过期，锁库存 | ? | ? | ? | ? |
| 9.1-9.2 查词生词本 | 体验用户限制，生词高亮 | ? | ? | ? | ? |
| 10.1-10.4 统计报告 | 周报/月报/趋势图 | ? | ? | ? | ? |
| 11.1-11.6 晋级 | A-Z 26级，80%通过，积分去重 | ? | ? | ? | ? |
| 12.1-12.2 证书 | 自动生成，幂等 | ? | ? | ? | ? |
| 13.1-13.3 观察期报告 | 30天自动生成 | ? | ? | ? | ? |
| 14.1 个人名片 | QR码分享 | ? | ? | ? | ? |
| 15.1-15.3 退款 | 三种公式，拦截网，审核制 | ? | ? | ? | ? |
| 16.1-16.3 语音朗读 | 录制/回放/打卡联动 | ? | ? | ? | ? |
| 17.1-17.5 RBAC | 3角色，128权限，数据隔离 | ? | ? | ? | ? |
| 附录D 库存联动 | 16条联动规则 | ? | ? | ? | ? |
| 附录M 隐私合规 | 三段式同意，删除权 | ? | ? | ? | ? |

**通过标准**：闭环率 = 100%。任何一行"?"未填或"否" → P0。

### A-2. 用户旅程端到端走查（7 条核心旅程）

以真实用户视角，逐步走查以下旅程，验证每一步的
前端页面 → API 调用 → 后端处理 → 数据库变更 → 响应返回 → 前端展示
是否完整闭环：

**旅程 1：新用户注册 → 亲子课报名 → 支付 → 获得凭证**
- [ ] 微信授权登录 → 获取 openid → 创建 user
- [ ] 选择场馆 → 选择时间段 → 填写孩子信息
- [ ] 支付 99 元 → 微信支付 V3 → 回调验签 → 订单状态更新
- [ ] 生成电子凭证 → 用户可查看
- [ ] iOS 端：亲子课是线下服务，可支付（非虚拟服务）

**旅程 2：亲子课完成 → 观察期报名 → 30天体验 → 报告生成 → 转正式会员**
- [ ] 前置校验：亲子课已完成
- [ ] 支付 500 元 → 孩子状态 → OBSERVATION(1)
- [ ] 分配老师 → teacher_id 写入
- [ ] 30 天内：无限量阅读、音频、查词、测评、打卡（与正式会员完全相同）
- [ ] 到期前 7/5/3/2/1/0 天提醒
- [ ] 到期 → 自动生成观察期报告
- [ ] 15 天缓冲期 → 续费 9 折
- [ ] 转正式会员 → 支付 5400 → status=2

**旅程 3：缴押金 → 扫码借书 → 音频伴读 → 查词 → 测评 → 还书**
- [ ] 缴押金 1200 → deposit_status=PAID
- [ ] 管理员扫码 → 条码存在 → 创建 BorrowRecord
- [ ] 条码不存在 → 创建 Book + BookCopy + BorrowRecord
- [ ] 同 ISBN 新条码 → 仅创建 BookCopy
- [ ] 音频伴读：锁屏播放、进度条、逾期锁死
- [ ] 查词：ECDICT → Free Dictionary → 未收录提示
- [ ] 测评：5 题 4 对 → 通过 → 积分计入（去重）
- [ ] 还书：正常还 → 逾期还（罚款）→ 丢失（定价×1.5）

**旅程 4：预约借书 → 到店取书 → 借阅**
- [ ] 预约：押金已缴 + 库存>0 → 锁库存 → 72h 倒计时
- [ ] 取书：扫码 → 创建 BorrowRecord → 预约 FULFILLED
- [ ] 过期：72h 后 → 释放库存 → EXPIRED

**旅程 5：退款全流程（三种类型）**
- [ ] 亲子课退款：开始前全退 / 开始后不退
- [ ] 观察期退款：实付 - (实付÷30×已用天数)
- [ ] 正式会员退款：实付 - (实付÷365×已用天数)
- [ ] 退款拦截：无活跃借阅（BORROWING/OVERDUE）
- [ ] 管理员审核 → 通过 → 原路退回
- [ ] 多孩优惠：按实付金额计算

**旅程 6：权益转让**
- [ ] 源孩子 5 项校验
- [ ] 目标孩子 3 项校验
- [ ] 管理员审核 → 通过 → 剩余天数转移
- [ ] 源孩子 → EXPIRED

**旅程 7：隐私合规全流程**
- [ ] 登录 → 隐私政策勾选（第 1 段）
- [ ] 添加孩子 → 儿童信息收集同意（第 2 段）
- [ ] 首次录音 → 语音数据收集同意（第 3 段）
- [ ] 撤回同意 → 功能立即停止
- [ ] 删除孩子数据 → 前置校验 → 24h 冷静期 → 级联删除
- [ ] 冷静期内取消 → 恢复

### A-3. 商业逻辑精算验证

逐条验证以下计算公式在代码中的实现：

| # | 公式 | PRD 出处 | 代码实现 | 测试用例 | 通过? |
|---|------|----------|----------|----------|-------|
| 1 | 多孩优惠 = 原价 × multi_child_discount | 1.3 | ? | ? | ? |
| 2 | 多孩与续费折扣互斥（不叠加为 8.1 折） | 1.3 | ? | ? | ? |
| 3 | 观察期退款 = 实付 - (实付÷30×已用天数) | 15.1 | ? | ? | ? |
| 4 | 正式会员退款 = 实付 - (实付÷365×已用天数) | 15.1 | ? | ? | ? |
| 5 | 升级差价 = 目标价格 - 当前价格×(剩余天数/总天数) | 1.3b | ? | ? | ? |
| 6 | 逾期罚款 = 逾期天数 × overdue_fine_per_day | 6.2 | ? | ? | ? |
| 7 | 丢书罚款 = 定价 × lost_book_fine_multiplier | 6.2 | ? | ? | ? |
| 8 | 损坏重度 = 定价 × 0.5 | T3.6a | ? | ? | ? |
| 9 | 损坏丢失 = 定价 × 1.5 | T3.6a | ? | ? | ? |
| 10 | ROUND_HALF_UP + 自然日历日 | D11 | ? | ? | ? |
| 11 | 缓冲期续费 9 折（15 天内） | 1.2 | ? | ? | ? |
| 12 | 积分去重：同 child+book 只计一次 word_count | 11.4 | ? | ? | ? |

**验证方法**：找到代码中的计算逻辑，手动代入边界值验算：
- 观察期第 0 天退款 = 500（全额）
- 观察期第 30 天退款 = 0
- 观察期第 15 天退款 = 250
- 正式会员第 1 天退款 = 5400 - 5400/365×1 = 5385.21
- 多孩 9 折后观察期退款：450 - 450/30×10 = 300
- 升级：季度剩 30 天 → 半年差价 = 2700 - 1350×(30/90) = 2250

### A-4. 文案一致性审查（附录 K）

逐条验证 PRD 附录 K 中的标准文案是否在代码中精确匹配：

| 场景 | PRD 标准文案 | 前端代码实际文案 | 后端代码实际文案 | 一致? |
|------|-------------|-----------------|-----------------|-------|
| 预约库存为 0 | 该书暂无库存 | ? | ? | ? |
| 借书未缴押金 | 请先缴纳押金（金额从配置读取） | ? | ? | ? |
| 借书达上限 | 已达最大借阅数，请先归还部分图书 | ? | ? | ? |
| 重复加入书架 | 该书已在书架中 | ? | ? | ? |
| 重复报名活动 | 已报名 | ? | ? | ? |
| 预约成功 | 预约成功，请 {hours} 小时内到店取书 | ? | ? | ? |
| 名额已满 | 该时间段名额已满，请选择其他时间 | ? | ? | ? |
| iOS 虚拟支付 | 因苹果规则限制，请前往线下门店或使用安卓设备办理 | ? | ? | ? |

**额外检查**：
- [ ] 所有涉及金额/数量/时限的文案使用配置变量插值，无硬编码数字
- [ ] 按钮文案动词开头
- [ ] 错误提示不暴露技术细节（无"数据库""接口 500""Traceback"）
- [ ] 前端弹窗 title 统一（"暂不支持 iOS 开通"而非"苹果规则限制"）

### A-5. 页面三态完整性（附录 L）

逐页检查 31 个小程序页面 + 37 个管理端页面：

**小程序页面三态**：

| 页面 | 空状态文案(附录L) | 空状态引导按钮 | 加载态(骨架屏) | 错误态(401/403/404/409/422/500) | 通过? |
|------|-------------------|---------------|---------------|-------------------------------|-------|
| 书架 | 书架还是空的 | 去图书馆看看 | ? | ? | ? |
| 生词本 | 还没有生词 | 去读一本书 | ? | ? | ? |
| 借阅记录 | 暂无借阅记录 | 预约借书 | ? | ? | ? |
| 预约列表 | 暂无预约 | 去图书馆看看 | ? | ? | ? |
| 证书列表 | 还没有证书，继续努力 | — | ? | ? | ? |
| 活动列表 | 近期没有活动 | — | ? | ? | ? |
| 消息中心 | 暂无消息 | — | ? | ? | ? |
| （其余 24 页逐页检查） | | | | | |

**错误态文案必须精确匹配附录 L.3**：

| HTTP 状态 | 标准文案 | 前端实际实现 | 一致? |
|-----------|---------|-------------|-------|
| 401 | 登录已过期，请重新进入小程序 | ? | ? |
| 403 | 暂无权限查看 | ? | ? |
| 404 | 内容不存在或已删除 | ? | ? |
| 409 | 操作冲突，请刷新后重试 | ? | ? |
| 422 | 展示后端返回的 detail 业务文案 | ? | ? |
| 500/超时 | 网络异常，请稍后重试（附重试按钮） | ? | ? |

### A-6. 交互逻辑边界场景（产品经理视角）

逐条验证以下边界场景是否有明确处理：

| # | 边界场景 | 预期行为 | 代码实现? | 测试覆盖? |
|---|---------|---------|----------|----------|
| 1 | 支付流程中切换孩子 | 禁止切换 | ? | ? |
| 2 | 听读进行中切换孩子 | 强制结束当前会话并结算时长 | ? | ? |
| 3 | 同一本书重复加入书架 | 提示"该书已在书架中" | ? | ? |
| 4 | 同一孩子重复借同一本书 | 拒绝 | ? | ? |
| 5 | 同一孩子重复报名同一活动 | 提示"已报名" | ? | ? |
| 6 | 活动开始前 24h 内取消 | 拒绝取消 | ? | ? |
| 7 | 活动名额已满时报名 | 按钮置灰"名额已满" | ? | ? |
| 8 | 观察期用户尝试借书（未缴押金） | 提示"请先缴纳押金" | ? | ? |
| 9 | 体验用户尝试借书 | 拒绝（非观察期/正式会员） | ? | ? |
| 10 | 已退出用户尝试任何付费操作 | 拒绝（不可恢复） | ? | ? |
| 11 | 已是最高级别尝试晋级 | 提示"已是最高级别" | ? | ? |
| 12 | 测验未通过 60 分钟内重考 | 拒绝（冷却期） | ? | ? |
| 13 | 押金已缴纳再次缴纳 | 提示"押金已缴纳，无需重复操作" | ? | ? |
| 14 | 预约过期后取书 | 拒绝（已过期） | ? | ? |
| 15 | 退款审核中再次申请退款 | 拒绝（重复申请） | ? | ? |
| 16 | 权益转让：源孩子有未还书 | 拒绝 | ? | ? |
| 17 | 权益转让：目标孩子非体验用户 | 拒绝 | ? | ? |
| 18 | 权益转让：源孩子已被转入过 | 拒绝 | ? | ? |
| 19 | 体验用户查词超过每日上限 | 拒绝/提示 | ? | ? |
| 20 | 体验用户试读超过页数限制 | 拒绝/提示 | ? | ? |
| 21 | 逾期状态下尝试音频伴读 | 锁死播放 | ? | ? |
| 22 | 订单 30 分钟未支付 | 自动关闭 | ? | ? |
| 23 | 并发预约最后一本库存 | 仅一人成功 | ? | ? |
| 24 | 并发借书最后一本库存 | 仅一人成功 | ? | ? |
| 25 | 管理员删除有活跃借阅的图书 | 拒绝/警告 | ? | ? |
| 26 | 删除最后一个超级管理员 | 拒绝 | ? | ? |
| 27 | 删除有管理员引用的角色 | 拒绝 | ? | ? |
| 28 | 系统内置角色改名/删除 | 拒绝 | ? | ? |
| 29 | 孩子数据删除：有活跃借阅 | 422 拒绝 | ? | ? |
| 30 | 孩子数据删除：有在持押金 | 422 拒绝 | ? | ? |
| 31 | 孩子数据删除：冷静期内取消 | 恢复 | ? | ? |
| 32 | 撤回 voice_recording 同意后录音 | 403 | ? | ? |
| 33 | 无 child_data 同意创建孩子 | 403 consent_required | ? | ? |
| 34 | 多孩优惠：所有老孩子退出后新订单 | 不再享优惠 | ? | ? |
| 35 | 已享 9 折订单不追溯补缴差价 | 不补缴 | ? | ? |

---

## 第二席：首席架构师审查（分层·依赖·可扩展性）

### B-1. 分层违规全量扫描

```bash
# Router 层禁止直接 ORM 操作
grep -rn '\.query\|session\.get\|session\.add\|session\.commit\|select(' \
  backend/domain/*/routers/ backend/domain/admin/routers/ \
  --include="*.py" | grep -v '__pycache__'

# Router 层禁止 try/except
grep -rn 'try:\|except ' \
  backend/domain/*/routers/ backend/domain/admin/routers/ \
  --include="*.py" | grep -v '__pycache__'

# Router 层禁止 HTTPException
grep -rn 'HTTPException' \
  backend/domain/*/routers/ backend/domain/admin/routers/ \
  --include="*.py" | grep -v '__pycache__'

# Service 层禁止直接操作 HTTP
grep -rn 'JSONResponse\|status_code\|Response(' \
  backend/domain/*/service.py backend/domain/*/services/ \
  --include="*.py" | grep -v '__pycache__'

# Model 层禁止业务方法（只允许 property 和 __repr__）
grep -rn 'def ' backend/domain/*/models.py \
  --include="*.py" | grep -v '__pycache__' \
  | grep -v 'def __repr__\|@property\|def __init__'
```

**通过标准**：以上全部 0 命中。

### B-2. 依赖方向与跨域通信

- [ ] Router → Service → Repository → Model，无反向依赖
- [ ] Service 之间不直接 import，跨域通信走 EventBus
- [ ] 无循环依赖（A→B→C→A）
- [ ] ConfigService 统一读取配置，无硬编码业务数值

```bash
# 硬编码业务数值扫描
grep -rn '= 1200\|= 5400\|= 500\|= 99\|= 1350\|= 2700\|= 21\|= 72\|= 30\|= 365\|= 0\.9\|= 0\.8\|= 1\.5' \
  backend/domain/ --include="*.py" | grep -v '__pycache__' \
  | grep -v 'test_\|_test\|seeds/\|DEFAULTS\|config_service'

# 跨 Service 直接 import 扫描
grep -rn 'from backend\.domain\.\w\+\.service import\|from \.\.\w\+\.service import' \
  backend/domain/ --include="*.py" | grep -v '__pycache__'
```

### B-3. EventBus 合规

- [ ] 所有跨域操作通过 `common/events.py` 发布事件
- [ ] handler 签名统一为 `def handler(event, db: Session)`
- [ ] 死信事件写入 `dead_letter_event` 表
- [ ] 无循环事件依赖
- [ ] 事件发布在事务提交后（非事务内）

### B-4. 异常体系

- [ ] 统一使用 `common/exceptions.py` 的 7 个异常类
- [ ] 无裸 `raise Exception()`
- [ ] 无 `except Exception: pass`（真吞异常）
- [ ] 全局异常处理器不泄漏堆栈到客户端

```bash
grep -rn 'except.*:\s*$' backend/ --include="*.py" -A1 | grep -B1 'pass\s*$' | grep -v '__pycache__'
grep -rn 'raise Exception(' backend/ --include="*.py" | grep -v '__pycache__'
```

### B-5. 技术债务评估

- [ ] 无 TODO/FIXME/HACK 未处理（或已有跟踪 Issue）
- [ ] 无死代码（未引用的函数/类/文件）
- [ ] 无重复逻辑（DRY 原则）
- [ ] 无过度设计（YAGNI 原则）

```bash
grep -rn 'TODO\|FIXME\|HACK\|XXX' backend/ frontend/ --include="*.py" --include="*.js" | grep -v '__pycache__' | grep -v 'node_modules'
```

---

## 第三席：高级后端工程师审查（代码质量·并发·金额·状态机）

### C-1. CI 同构十关（硬门禁）

```bash
venv/bin/ruff check backend/ tests/
venv/bin/ruff check features/ scripts/
venv/bin/ruff format --check .
venv/bin/python -m pytest tests/ -x -q --tb=short
venv/bin/python -m behave features/ --no-capture -q
venv/bin/python -m scripts.verify_api_contract
venv/bin/python -m scripts.check_model_consistency
venv/bin/python -m scripts.verify_action_wiring --strict
MOCK_PAYMENT=true MOCK_SMS=true DEBUG=true venv/bin/python scripts/integration_test.py
venv/bin/python -m alembic check
```

**通过标准**：10/10 Exit Code = 0。

### C-2. 金额精度（P0 致命级）

```bash
# 严禁 float 处理金额
grep -rn 'float(' backend/domain/ --include="*.py" \
  | grep -i 'amount\|price\|fee\|fine\|deposit\|refund\|discount' \
  | grep -v '__pycache__'

# 严禁 Decimal("100 ") 带空格
grep -rn 'Decimal("' backend/ --include="*.py" | grep ' "' | grep -v '__pycache__'
```

- [ ] 所有金额字段为 `Decimal(10,2)` 或整数分
- [ ] 所有金额计算使用 `Decimal` 运算
- [ ] 无 `float()` 转换金额
- [ ] ROUND_HALF_UP 舍入模式
- [ ] 自然日历日计算（非 24h 滚动）

### C-3. 并发安全（P0 致命级）

- [ ] 预约借书锁定库存：SQL 原子操作 `UPDATE ... SET field = field - 1 WHERE field > 0`
- [ ] 押金退款前校验：无未还书 AND 无未缴罚款
- [ ] 退款申请有锁 + 重复校验
- [ ] 库存变更使用 SQL 原子操作，非 ORM read-modify-write
- [ ] 关键操作使用 `with_for_update()` 行锁

```bash
grep -rn 'with_for_update' backend/ --include="*.py" | grep -v '__pycache__'
# 检查库存操作是否为原子操作
grep -rn 'available_stock\|total_stock' backend/domain/ --include="*.py" \
  | grep -v '__pycache__' | grep -v 'test_'
```

### C-4. 状态机完整性（12 个实体）

逐个验证状态流转是否与 PRD 附录 F 一致，且非法转换被拦截：

| 实体 | 状态数 | 合法转换 | 非法转换拦截 | 终态不可逆 | 代码实现 | 通过? |
|------|--------|---------|-------------|-----------|---------|-------|
| Child 会员 | 5 | 0→1→2→3→2, 任意→4 | ? | EXITED(4) | ? | ? |
| BookCopy 副本 | 6 | 附录D 16条 | ? | SCRAPPED/LOST | ? | ? |
| BorrowRecord 借阅 | 4 | 0→1/2→3 | ? | RETURNED/LOST | ? | ? |
| DepositRecord 押金 | 7 | 0→1→6→4→2, 1→3 | ? | REFUNDED/DEDUCTED | ? | ? |
| Reservation 预约 | 4 | 0→1/2/3 | ? | FULFILLED/CANCELLED/EXPIRED | ? | ? |
| Order 支付 | 6 | 0→1→3/4, 0→2/5 | ? | CLOSED/CANCELLED | ? | ? |
| Activity 活动 | 6 | 0→1→2→3→4, 任意→5 | ? | FINISHED/CANCELLED | ? | ? |
| ActivityEnrollment | 5 | 0→1→4, 0→2/3 | ? | SIGNED_IN/CANCELLED | ? | ? |
| RefundApplication | 4 | 0→1→3, 0→2 | ? | COMPLETED/REJECTED | ? | ? |
| ReadingSubmission | 3 | 0→1/2 | ? | APPROVED/REJECTED | ? | ? |
| Quiz 测验 | 3 | 0→1/2 | ? | COMPLETED/EXPIRED | ? | ? |
| DamageReport 损坏 | 4 | 0→2→1/3 | ? | CONFIRMED/OVERRIDDEN | ? | ? |

### C-5. 库存联动矩阵（附录 D 16 条规则）

逐条验证代码实现：

| # | 操作 | total_stock | available_stock | 代码文件:行号 | 原子操作? | 通过? |
|---|------|-------------|-----------------|--------------|----------|-------|
| 1 | 新增副本→AVAILABLE | +1 | +1 | ? | ? | ? |
| 2 | 借出 AVAILABLE→BORROWED | 不变 | -1 | ? | ? | ? |
| 3 | 还书 BORROWED→AVAILABLE | 不变 | +1 | ? | ? | ? |
| 4 | 预约创建 | 不变 | -1 | ? | ? | ? |
| 5 | 预约取消/过期 | 不变 | +1 | ? | ? | ? |
| 6 | 标记维修(在馆) | 不变 | -1 | ? | ? | ? |
| 7 | 标记维修(已借出) | 不变 | 不变 | ? | ? | ? |
| 8 | 维修完成 | 不变 | +1 | ? | ? | ? |
| 9 | 标记损坏(在馆) | 不变 | -1 | ? | ? | ? |
| 10 | 标记损坏(已借出) | 不变 | 不变 | ? | ? | ? |
| 11 | 损坏修复 | 不变 | +1 | ? | ? | ? |
| 12 | 丢失赔偿 | -1 | -1 | ? | ? | ? |
| 13 | 报废(在馆) | -1 | -1 | ? | ? | ? |
| 14 | 报废(已借出) | -1 | 不变 | ? | ? | ? |
| 15 | 报废(维修中) | -1 | 不变 | ? | ? | ? |
| 16 | 报废(损坏) | -1 | 不变 | ? | ? | ? |

### C-6. 数据库一致性（55 张表）

- [ ] 所有 Model 字段与 `表结构.md` 一致（字段名、类型、nullable、default、comment）
- [ ] 外键关系正确
- [ ] UK 字段有唯一索引
- [ ] `is_deleted` / `create_time` / `update_time` 标准字段齐全
- [ ] Alembic 迁移无漂移
- [ ] 迁移链无断裂
- [ ] 所有迁移有 downgrade

```bash
venv/bin/python -m scripts.check_model_consistency
venv/bin/python -m alembic check
venv/bin/python -m alembic history --verbose | head -50
```

### C-7. API 契约（184 端点）

- [ ] 所有 Router 已注册
- [ ] 无孤立 Router 文件
- [ ] 所有 Schema 有 `extra="forbid"`
- [ ] 所有列表接口返回 `{items, total, page, page_size, has_next}`
- [ ] 所有路由有 `response_model`
- [ ] 无 `dict` 作为 response_model
- [ ] 用户端接口全部有 `get_current_user` 依赖
- [ ] 孩子相关接口全部有归属校验
- [ ] 管理端接口全部有 admin 认证 + `require_perm()`

```bash
# Schema extra=forbid 检查
grep -rn 'class.*Schema\|class.*Response\|class.*Request' \
  backend/domain/*/schemas.py backend/domain/admin/admin_schemas.py \
  --include="*.py" | wc -l
grep -rn 'extra.*=.*"forbid"\|model_config.*forbid' \
  backend/domain/*/schemas.py backend/domain/admin/admin_schemas.py \
  --include="*.py" | wc -l
# 两个数字必须相等

# 越权检查扫描
grep -rn 'user_id != current_user\|user_id == current_user' \
  backend/domain/*/routers/ --include="*.py" | grep -v '__pycache__'
```

### C-8. 动态配置（38 项）

- [ ] `SystemConfig.DEFAULTS` 包含全部 37 项
- [ ] `quiz_cooldown_minutes` 通过代码默认值 60 生效
- [ ] 配置键名与 `动态配置清单.md` 完全一致
- [ ] 所有 37 项配置有校验规则实现
- [ ] ConfigService 带 5 分钟 TTL 缓存
- [ ] 配置变更写入 `config_audit_log`
- [ ] 管理端 API：GET/PUT `/admin/config/{key}` + GET `/admin/configs`

逐项验证校验规则：

| 配置键 | 类型 | 合法范围 | 代码中校验实现(文件:行号) | 通过? |
|--------|------|---------|--------------------------|-------|
| borrow_limit | int | 1–50 | ? | ? |
| borrow_period_days | int | 1–90 | ? | ? |
| overdue_fine_per_day | decimal | 0–100 | ? | ? |
| lost_book_fine_multiplier | decimal | 1.0–3.0 | ? | ? |
| renewal_discount / multi_child_discount | decimal | 0.5–1.0 | ? | ? |
| member_days / observation_days | int | 1–730 | ? | ? |
| member_grace_days | int | 0–90 | ? | ? |
| *_remind_days | 逗号分隔 int | 每项 0–30，去重排序 | ? | ? |
| price_* | decimal | 0.01–100000 | ? | ? |
| deposit_amount | decimal | 0–10000 | ? | ? |
| reservation_expire_hours | int | 1–168 | ? | ? |
| order_expire_minutes | int | 5–120 | ? | ? |
| vocab_lookup_limit / trial_pages | int | 0–1000 | ? | ? |
| quiz_pass_rate | decimal | 0.5–1.0 | ? | ? |
| quiz_total_questions / quiz_pass_count | int | 1–20 | ? | ? |
| quiz_cooldown_minutes | int | 5–1440 | ? | ? |
| bookshelf_limit | int | 0–500 | ? | ? |
| activity_cancel_hours | int | 1–72 | ? | ? |
| checkin_min_minutes / checkin_min_vocab | int | 1–120 | ? | ? |
| daily_checkin_limit | int | 1–10 | ? | ? |
| enable_* | bool | true/false | ? | ? |

### C-9. 定时任务（17 个）

逐个验证：

| # | 任务 ID | 触发时间 | 注册? | 逻辑正确? | 异常处理? | 幂等? | 通过? |
|---|---------|---------|-------|----------|----------|-------|-------|
| 1 | check_member_expiry | 每天 09:00 | ? | ? | ? | ? | ? |
| 2 | check_observation_reminders | 每天 09:00 | ? | ? | ? | ? | ? |
| 3 | check_observation_expiry | 每天 09:30 | ? | ? | ? | ? | ? |
| 4 | check_activity_reminders | 每天 10:00 | ? | ? | ? | ? | ? |
| 5 | remind_pending_submissions | 每天 11:00 | ? | ? | ? | ? | ? |
| 6 | alert_stale_refunds | 每天 12:00 | ? | ? | ? | ? | ? |
| 7 | check_due_date_reminders | 每天 01:00 | ? | ? | ? | ? | ? |
| 8 | check_grace_period_shutdown | 每天 02:00 | ? | ? | ? | ? | ? |
| 9 | mark_overdue_books | 每天 02:30 | ? | ? | ? | ? | ? |
| 10 | reconcile_stock | 每天 03:00 | ? | ? | ? | ? | ? |
| 11 | execute_child_deletions | 每天 03:30 | ? | ? | ? | ? | ? |
| 12 | reconcile_child_stats | 每天 03:45 | ? | ? | ? | ? | ? |
| 13 | generate_weekly_reports | 每周一 08:00 | ? | ? | ? | ? | ? |
| 14 | generate_monthly_reports | 每月1日 08:00 | ? | ? | ? | ? | ? |
| 15 | close_expired_orders | 每分钟 | ? | ? | ? | ? | ? |
| 16 | migrate_activity_status | 每5分钟 | ? | ? | ? | ? | ? |
| 17 | expire_reservations | 每30分钟 | ? | ? | ? | ? | ? |

### C-10. 种子数据

- [ ] 3 个角色种子（super_admin/staff/teacher）
- [ ] 128 个权限码种子
- [ ] 角色-权限关联正确（super_admin=128, staff=102, teacher=27）
- [ ] 26 个级别（A-Z）种子
- [ ] 系统配置 38 项默认值与 `动态配置清单.md` 一致
- [ ] 种子脚本幂等（可重复执行）

```bash
venv/bin/python -m backend.seeds.seed_test_data 2>&1 | tail -20
```

---

## 第四席：高级前端工程师审查（小程序·防白屏·样式·生命周期）

### D-1. 防白屏底线

```bash
# 所有 {{}} 数据绑定必须有 wx:if 或默认值
grep -rn '{{' frontend/pages/ frontend/components/ --include="*.wxml" \
  | grep -v 'wx:if\|||\|? ' | head -50
```

- [ ] 所有 `{{}}` 配合 `wx:if` 或 `{{data || '默认值'}}`
- [ ] 无 `undefined` 导致崩溃风险
- [ ] 列表渲染有 `wx:for` + `wx:key`
- [ ] 条件渲染有 `wx:if` / `wx:elif` / `wx:else` 完整链

### D-2. 网络底线

```bash
# 静默 catch 扫描
grep -rn '\.catch\s*(\s*(\s*)\s*=>\s*{' frontend/ --include="*.js" -A1 \
  | grep -v 'console\.\|wx\.showToast\|logger'
grep -rn 'silent\|\/\*.*\*\/' frontend/ --include="*.js" \
  | grep -i 'catch\|error\|fail'
```

- [ ] 所有 `wx.request` 封装包含 `fail` / `complete` 回调
- [ ] 所有异常有 `wx.showToast` 用户提示
- [ ] 无静默 `.catch(() => {})` 或 `/* silent */`
- [ ] 网络超时有重试机制或明确提示

### D-3. 音频伴读

- [ ] 使用 `wx.getBackgroundAudioManager()` 支持锁屏
- [ ] 进度条更新不用全局 `setData`
- [ ] 逾期锁死播放
- [ ] 中断恢复（退出后重新打开继续播放）
- [ ] 倍速播放：0.75x / 1x / 1.25x / 1.5x

### D-4. 样式禁令

```bash
# 禁用 CSS 属性
grep -rn 'oklch\|aspect-ratio\|backdrop-filter\|translateY(-50%)' \
  frontend/ --include="*.wxss" --include="*.wxml"

# position:fixed 必须有 box-sizing
grep -rn 'position:\s*fixed' frontend/ --include="*.wxss" -A3 | grep -v 'box-sizing'

# 硬编码 hex（wxss）
grep -rn '#[0-9a-fA-F]\{3,8\}' frontend/pages/ frontend/components/ \
  --include="*.wxss" | grep -v 'var(--' | grep -v 'data:'

# 硬编码 hex（wxml inline）
grep -rn 'style="[^"]*#[0-9a-fA-F]' frontend/ --include="*.wxml"

# Token 重定义
grep -rn '\-\-accent:' frontend/pages/ --include="*.wxss" | grep -v 'app.wxss'

# 旧主色残留
grep -rn '#4f46e5\|#6b5ce7\|#7c5ce7' frontend/ \
  --include="*.wxss" --include="*.wxml" --include="*.js"
```

**通过标准**：
- 禁用属性：0 处
- wxss 硬编码：0 处
- wxml inline 硬编码：≤5 处
- Token 重定义：0 处
- 旧主色：0 处

### D-5. 生命周期

- [ ] `onLoad` 参数在 `onUnload` 清理
- [ ] 定时器在 `onUnload` 清除
- [ ] 支付流程中禁止切换孩子
- [ ] 听读进行中切换孩子 → 强制结束会话

### D-6. iOS 虚拟支付合规（致命红线）

```bash
grep -rn 'requestPayment\|wx\.pay\|pay-button' frontend/ \
  --include="*.js" --include="*.wxml" | grep -v '__pycache__'
```

- [ ] 500 元观察期 / 5400 元会员 / 1350 季度 / 2700 半年：iOS 端隐藏支付按钮
- [ ] iOS 端显示："因苹果规则限制，请前往线下门店或使用安卓设备办理"
- [ ] 押金 1200 元（实物担保）：iOS 可支付
- [ ] 亲子课 99 元（线下服务）：iOS 可支付
- [ ] pay-button 组件 iOS 文案已同步

### D-7. 隐私合规前端

- [ ] 登录页隐私政策勾选（第 1 段）
- [ ] 添加孩子前弹儿童信息收集同意（第 2 段）
- [ ] 首次录音前弹语音数据收集同意（第 3 段）
- [ ] 文案唯一来源 `backend/common/consent_texts.py`，前端不硬编码
- [ ] `frontend/utils/consent.js`：`ensure(type)` + `ensureForError(err, type)`
- [ ] 我的 → 隐私与数据入口存在
- [ ] 撤回同意操作路径明确

### D-8. 管理端 PC 后台

```bash
# 模板完整性（37 个页面）
for page in dashboard users orders books bookcopy borrow activities \
  activity_checkin damage_reports questions submissions reports settings \
  teachers venues levels achievements deposit reservation assessments \
  audio certificates content dictionary library login macros \
  message_manage operation_logs page_template profile quiz reading_data \
  roles recycle_bin 403 base; do
  if [ ! -f "backend/templates/admin/${page}.html" ]; then
    echo "❌ 缺失: ${page}.html"
  fi
done

# CSS 完整性
for page in dashboard users orders books bookcopy borrow activities \
  activity_checkin damage_reports questions submissions reports settings \
  teachers venues levels achievements deposit reservation assessments \
  audio certificates content dictionary library login profile quiz \
  reading_data operation_logs recycle_bin roles; do
  if [ ! -f "backend/static/admin/css/pages/${page}.css" ]; then
    echo "❌ 缺失: ${page}.css"
  fi
done

# 硬编码扫描（PC）
grep -rn '#[0-9a-fA-F]\{3,8\}' backend/static/admin/css/ \
  | grep -v 'var(--' | grep -v '#fff' | grep -v '#000' \
  | grep -v '#ffffff' | grep -v 'data:'

# XSS 防护
grep -rn 'innerHTML' backend/templates/ backend/static/ \
  --include="*.html" --include="*.js" | grep -v 'escapeHtml\|textContent'
```

- [ ] 37 个模板全部存在
- [ ] 33 个页面级 CSS 全部存在
- [ ] 硬编码 0 处
- [ ] 所有动态内容使用 escapeHtml()
- [ ] `data-perm` + `applyPermissions()` 运行时裁剪
- [ ] PAGE_PERM_MAP 统一守卫

---

## 第五席：安全渗透专家审查（认证·授权·注入·隐私）

### E-1. 认证安全

- [ ] JWT SECRET_KEY 从环境变量读取，不在代码中硬编码
- [ ] Admin Cookie 有 Secure / HttpOnly / SameSite 属性
- [ ] Admin Token 有效期 8 小时（可配置）
- [ ] 用户 JWT 有 type 检查防混淆（user token ≠ admin token）
- [ ] 测试令牌有 DEBUG + ENABLE_TEST_TOKEN 双重守卫
- [ ] 密码使用 bcrypt 哈希
- [ ] 登录失败记录 username + IP
- [ ] 账号禁用后 token 立即失效

```bash
grep -rn 'SECRET_KEY\|secret_key' backend/ --include="*.py" \
  | grep -v '__pycache__' | grep -v 'os\.environ\|settings\.'
```

### E-2. 注入防护

```bash
# SQL 拼接
grep -rn 'f".*SELECT\|f".*INSERT\|f".*UPDATE\|f".*DELETE\|\.format.*SELECT' \
  backend/ --include="*.py" | grep -v '__pycache__'

# innerHTML XSS
grep -rn 'innerHTML' backend/templates/ backend/static/ \
  --include="*.html" --include="*.js" | grep -v 'escapeHtml\|textContent'
```

- [ ] 无 SQL 拼接（全部 ORM 或参数化查询）
- [ ] 管理端无 innerHTML XSS
- [ ] 文件上传有扩展名白名单 + 魔数校验
- [ ] 分片上传有扩展名校验 + 合并后魔数校验
- [ ] CORS 生产环境不含 localhost

### E-3. 越权防护

- [ ] 所有孩子数据操作通过 `middleware/ownership.py` 声明式校验
- [ ] 无手动 user_id 比对
- [ ] 管理端 RBAC 权限逐端点校验
- [ ] Teacher 角色数据隔离（`get_scoped_child_ids()`）
- [ ] 权限不足记录 admin_id + required_codes

```bash
grep -rn 'user_id != current_user\|user_id == current_user' \
  backend/domain/*/routers/ --include="*.py" | grep -v '__pycache__'
```

### E-4. 隐私合规（儿童信息保护）

- [ ] consent_record 表存在且字段完整
- [ ] 三段式同意流程完整
- [ ] 后端拦截：POST /child 无同意→403 consent_required
- [ ] 后端拦截：POST /reading/voice/record 无同意→403 voice_consent_required
- [ ] 文案唯一来源 `backend/common/consent_texts.py`
- [ ] 撤回 child_data = 级联删除（P0-3）
- [ ] 前置校验：无活跃借阅 + 无在持押金 + 无进行中退款
- [ ] 软删除 + `deletion_requested_at` 24h 冷静期
- [ ] 冷静期内可取消
- [ ] 定时任务 `execute_child_deletions` 每天 03:30
- [ ] 物理删除非财务表（19 张 child_id 直联 + 级联）
- [ ] 财务数据法定保留
- [ ] 删除后 operation_log + SystemMessage 通知
- [ ] 完整 9 节隐私政策
- [ ] 儿童专章 v1.1
- [ ] 办学资质展示
- [ ] 运营主体非占位符（COMPANY_NAME 环境变量）

### E-5. 日志安全

- [ ] 日志不输出密码、token、手机号明文
- [ ] JSON 格式日志 + trace_id
- [ ] 登录失败记录 username + IP
- [ ] 权限不足记录 admin_id + required_codes
- [ ] 限流触发记录 key/max/window
- [ ] 归属校验失败记录 child_id/user_id/owner_id

### E-6. Mock 网关安全

- [ ] Mock 路由仅在 `MOCK_PAYMENT=True` / `MOCK_SMS=True` 时注册
- [ ] 生产环境（DEBUG=false）不注册 Mock 路由
- [ ] Mock 路由不暴露在生产 CORS 中

---

## 第六席：测试总监审查（覆盖矩阵·边界·异常·回归）

### F-1. 测试数量与质量

```bash
# 假绿断言扫描
grep -rn 'assert True\|assert 1 == 1\|assert "" == ""' tests/ --include="*.py"
venv/bin/python -m scripts.check_fake_assertions
```

- [ ] pytest ≥ 316 passed / 5 skipped
- [ ] behave ≥ 160 scenarios / 1095 steps / 0 failed
- [ ] 集成测试 ≥ 53 steps pass
- [ ] 并发测试 ≥ 13 个
- [ ] 无 `assert True` 假绿
- [ ] 无跳过的关键测试

### F-2. 测试覆盖矩阵

逐业务域验证测试覆盖：

| 业务域 | 正常流 | 异常流 | 边界值 | 并发 | 状态机 | 通过? |
|--------|--------|--------|--------|------|--------|-------|
| 用户注册/登录 | ? | ? | ? | — | — | ? |
| 亲子课报名 | ? | ? | ? | — | — | ? |
| 观察期报名 | ? | ? | ? | — | ? | ? |
| 正式会员 | ? | ? | ? | — | ? | ? |
| 季度/半年 | ? | ? | ? | — | ? | ? |
| 升级差价 | ? | ? | ? | — | — | ? |
| 多孩折扣 | ? | ? | ? | — | — | ? |
| 折扣互斥 | ? | ? | ? | — | — | ? |
| 借阅（扫码） | ? | ? | ? | ? | ? | ? |
| 还书（正常/逾期/丢失） | ? | ? | ? | — | ? | ? |
| 押金（缴/退/扣） | ? | ? | ? | ? | ? | ? |
| 预约（创建/取书/过期） | ? | ? | ? | ? | ? | ? |
| 退款（三种公式） | ? | ? | ? | — | ? | ? |
| 退款拦截 | ? | ? | ? | — | — | ? |
| 权益转让（成功+5种失败） | ? | ? | ? | — | ? | ? |
| 活动（报名/取消/签到/主办方取消） | ? | ? | ? | — | ? | ? |
| 晋级（条件满足/不满足/最高级） | ? | ? | ? | — | ? | ? |
| 打卡（4种类型+去重） | ? | ? | ? | — | — | ? |
| 查词（ECDICT/Free Dict/未收录） | ? | ? | ? | — | — | ? |
| 体验用户限制 | ? | ? | ? | — | — | ? |
| 音频伴读（逾期锁死） | ? | ? | ? | — | — | ? |
| 库存联动（16条） | ? | ? | ? | ? | ? | ? |
| 损坏定责（三级+冲正） | ? | ? | ? | — | ? | ? |
| 隐私同意（三段式） | ? | ? | ? | — | — | ? |
| 删除权（级联+冷静期） | ? | ? | ? | — | — | ? |
| RBAC（3角色） | ? | ? | ? | — | — | ? |
| 配置校验（38项） | ? | ? | ? | — | — | ? |
| 定时任务（17个） | ? | ? | ? | — | — | ? |

### F-3. BDD 场景覆盖

- [ ] 用户报名全流程（亲子课→观察期→正式会员）
- [ ] 季度/半年会员
- [ ] 升级差价
- [ ] 缓冲期续费 9 折
- [ ] 查词上限
- [ ] 试读页数限制
- [ ] 借阅全流程（借→还→逾期→丢失）
- [ ] 押金全流程（缴→退→扣）
- [ ] 预约全流程（预约→取书→过期）
- [ ] 权益转让（成功+5 种失败）
- [ ] 退款（3 种类型+拦截）
- [ ] 晋级（条件满足+不满足+最高级）
- [ ] 打卡（4 种类型+去重）
- [ ] 活动（报名+取消+签到+主办方取消）
- [ ] 损坏定责（三级+申诉+冲正）
- [ ] 隐私同意（三段式+撤回+删除）

### F-4. 反向审查（没做什么）

- [ ] PRD 写了但代码没实现的功能
- [ ] 代码写了但测试没覆盖的分支
- [ ] 测试写了但断言是假的
- [ ] 前端写了但后端没接的 API
- [ ] 后端写了但前端没调的 API
- [ ] 配置项定义了但代码没读取的
- [ ] 定时任务注册了但逻辑是空壳的

```bash
# 前端 API 调用 vs 后端路由注册 交叉验证
venv/bin/python -m scripts.verify_api_contract
```

---

## 第七席：SRE 运维专家审查（监控·日志·部署·灾备）

### G-1. 环境变量与部署

- [ ] ENABLE_TEST_TOKEN（测试令牌守卫）
- [ ] DEBUG（双重守卫）
- [ ] MOCK_PAYMENT（Mock 支付开关）
- [ ] MOCK_SMS（Mock 短信开关）
- [ ] COMPANY_NAME（运营主体）
- [ ] JWT SECRET_KEY
- [ ] 数据库连接串
- [ ] Redis 连接串
- [ ] 微信支付商户配置
- [ ] SMS 服务商凭据

### G-2. 生产安全检查

- [ ] DEBUG=false 时：Mock 路由不注册
- [ ] DEBUG=false 时：CORS 不含 localhost
- [ ] DEBUG=false 时：测试令牌不生效
- [ ] 日志 JSON 格式 + trace_id
- [ ] 全局异常处理器不泄漏堆栈
- [ ] 健康检查端点存在

### G-3. 外部依赖状态

| 依赖 | 状态 | 阻塞上线? | 责任方 |
|------|------|----------|--------|
| 微信 appid | 需产品提供 | 是 | 产品 |
| 微信支付商户 APIv3 密钥 | 需商户平台 | 是 | 运营 |
| SMS 真实服务商 | Mock 可运行 | 否（上线需） | 运维 |
| 隐私政策法务审核 | 需法务 | 是 | 法务 |
| 办学资质 | 需运营 | 是 | 运营 |
| ECDICT 338 万词条导入 | 需执行脚本 | 是 | 运维 |

### G-4. 数据迁移与回滚

- [ ] `alembic upgrade head` 可从零建库
- [ ] 种子数据可重复执行（幂等）
- [ ] 每个迁移有 downgrade
- [ ] 回滚方案文档化

### G-5. 性能基线

| 场景 | 指标 | 测量方式 | 当前值 | 通过? |
|------|------|---------|--------|-------|
| 扫码借书/还书 | P95 ≤ 1.5s | 服务端日志 | ? | ? |
| 图书搜索 | P95 ≤ 800ms | 服务端日志 | ? | ? |
| 查词（ECDICT） | P95 ≤ 50ms | 服务端日志 | ? | ? |
| 逾期检测 | 1 万条 ≤ 5 分钟 | 任务日志 | ? | ? |
| 小程序首屏 | ≤ 2s（4G） | 前端埋点 | ? | ? |

### G-6. N+1 查询与慢查询

```bash
# N+1 查询扫描
grep -rn 'for.*in.*:' backend/domain/ --include="*.py" -A3 \
  | grep -B1 '\.query\|session\.get\|\.first()' | grep -v '__pycache__'
```

- [ ] 无 N+1 查询（全部使用批量查询 + dict 映射）
- [ ] 列表接口有分页
- [ ] 大表查询有索引

---

## 第八关：视觉对齐自检闭环（14 项）

执行 CLAUDE.md 中定义的完整自检脚本：

```bash
echo "===== 自检闭环验证 ====="
# 1. CSS 文件存在性
for page in dashboard users orders books bookcopy borrow activities \
  activity_checkin damage_reports questions submissions reports settings \
  teachers venues levels achievements deposit reservation assessments \
  audio certificates content dictionary library login profile quiz \
  reading_data operation_logs recycle_bin roles; do
  if [ ! -f "backend/static/admin/css/pages/${page}.css" ]; then
    echo "❌ 缺失: ${page}.css"
  fi
done
# 2-5. 硬编码/oklch/旧主色/Token 重定义
echo "--- PC 后台硬编码 ---"
grep -rn '#[0-9a-fA-F]\{3,8\}' backend/static/admin/css/ \
  | grep -v 'var(--' | grep -v '#fff' | grep -v '#000' \
  | grep -v '#ffffff' | grep -v 'data:' | wc -l
echo "--- 小程序 wxss 硬编码 ---"
grep -rn '#[0-9a-fA-F]\{3,8\}' frontend/pages/ frontend/components/ \
  --include="*.wxss" | grep -v 'var(--' | grep -v 'data:' | wc -l
echo "--- oklch 残留 ---"
grep -rn 'oklch' backend/ frontend/ \
  --include="*.css" --include="*.wxss" --include="*.html" | wc -l
echo "--- 旧主色残留 ---"
grep -rn '#4f46e5\|#6b5ce7\|#7c5ce7' backend/ frontend/ \
  --include="*.css" --include="*.wxss" --include="*.html" --include="*.js" | wc -l
echo "--- Token 重定义 ---"
grep -rn '\-\-accent:' frontend/pages/ --include="*.wxss" \
  | grep -v 'app.wxss' | wc -l
# 6-10. 测试十关
venv/bin/python -m pytest tests/ -x -q --tb=short 2>&1 | tail -3
venv/bin/python -m behave features/ --no-capture -q 2>&1 | tail -3
venv/bin/ruff check backend/ tests/ 2>&1 | tail -3
venv/bin/ruff check features/ scripts/ 2>&1 | tail -3
venv/bin/ruff format --check . 2>&1 | tail -3
venv/bin/python -m scripts.verify_api_contract 2>&1 | tail -3
venv/bin/python -m scripts.check_model_consistency 2>&1 | tail -3
venv/bin/python -m scripts.verify_action_wiring --strict 2>&1 | tail -3
echo "===== 自检完成 ====="
```

| # | 检查项 | 通过标准 |
|---|--------|---------|
| 1 | CSS 文件存在性 | 全部存在 |
| 2 | CSS 规则对齐度 | ≥90% |
| 3 | base.css 通用规则覆盖 | 0 条跨页面缺失 |
| 4 | HTML class 对齐度 | ≥95% |
| 5 | 硬编码 hex（PC） | 0 处 |
| 6 | 硬编码 hex（wxss） | 0 处 |
| 7 | 硬编码 hex（wxml inline） | ≤5 处 |
| 8 | oklch 残留 | 0 处 |
| 9 | 旧主色残留 | 0 处 |
| 10 | Token 重定义 | 0 处 |
| 11-14 | pytest/behave/ruff/format | Exit Code 0 |

---

## 输出格式（必须严格遵循）

### 一、审查总览

| 席位 | 角色 | 子项数 | 通过 | 失败 | P0 | P1 | P2 |
|------|------|--------|------|------|----|----|-----|
| A | 产品经理 | ? | ? | ? | ? | ? | ? |
| B | 架构师 | ? | ? | ? | ? | ? | ? |
| C | 后端工程师 | ? | ? | ? | ? | ? | ? |
| D | 前端工程师 | ? | ? | ? | ? | ? | ? |
| E | 安全专家 | ? | ? | ? | ? | ? | ? |
| F | 测试总监 | ? | ? | ? | ? | ? | ? |
| G | SRE | ? | ? | ? | ? | ? | ? |
| **合计** | | **?** | **?** | **?** | **?** | **?** | **?** |

### 二、P0 致命问题清单（必须修复才能上线）

| # | 席位 | 问题描述 | 文件:行号 | 修复方案 | 状态 |
|---|------|---------|----------|---------|------|

### 三、P1 严重问题清单（上线前必须修复）

| # | 席位 | 问题描述 | 文件:行号 | 修复方案 | 状态 |
|---|------|---------|----------|---------|------|

### 四、P2 一般问题清单（上线后迭代修复）

| # | 席位 | 问题描述 | 文件:行号 | 修复方案 | 状态 |
|---|------|---------|----------|---------|------|

### 五、需求闭环缺口（PRD 有但代码无）

| # | PRD 章节 | 规则描述 | 缺失位置 | 影响 |
|---|---------|---------|---------|------|

### 六、测试覆盖缺口

| # | 业务域 | 缺失场景 | 风险等级 |
|---|--------|---------|---------|

### 七、上线门禁判定

- [ ] P0 = 0 → ✅ 允许上线
- [ ] P0 > 0 → 🚫 禁止上线，修复后重审
- [ ] 需求闭环率 = 100% → ✅
- [ ] 需求闭环率 < 100% → 🚫 列出缺口

### 八、外部依赖阻塞项

| 依赖 | 责任方 | 状态 | 预计解决时间 |
|------|--------|------|-------------|

### 九、审查官签署

| 席位 | 角色 | 结论 | 签署 |
|------|------|------|------|
| A | 产品经理 | 通过/不通过 | |
| B | 架构师 | 通过/不通过 | |
| C | 后端工程师 | 通过/不通过 | |
| D | 前端工程师 | 通过/不通过 | |
| E | 安全专家 | 通过/不通过 | |
| F | 测试总监 | 通过/不通过 | |
| G | SRE | 通过/不通过 | |

**七席全部签署"通过"方可上线。任何一席"不通过"即阻断。**

---

## 执行指令

现在开始执行。从第一席 A-1 开始，逐席逐项推进。
不要询问"是否继续"，不要停顿，不要跳过任何子项。
遇到阻断点时标记 🚫 并继续下一项。
全部 7 席 + 视觉自检执行完毕后输出最终审查报告。

记住：你不是在写报告，你是在做生死判决。
每一项"通过"都意味着你对线上用户的安全和体验负责。
找不到证据就写"未验证"，绝不写"应该没问题"。
```

---

**使用方式**：将上述完整 prompt 粘贴给 Kimi K3，配合文件读取工具（或直接将 5 份知识库文件 + 源码作为上下文注入）。7 席 × 300+ 子项，覆盖产品、架构、后端、前端、安全、测试、运维全维度，含需求闭环矩阵、商业逻辑精算、用户旅程走查、边界场景 35 条、状态机 12 个实体、库存联动 16 条规则、配置校验 38 项、定时任务 17 个、测试覆盖矩阵 28 个业务域。