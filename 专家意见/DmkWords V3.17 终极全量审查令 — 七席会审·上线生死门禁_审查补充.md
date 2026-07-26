# 🔍 DmkWords V3.17 补充审查令 — 文档一致性·部署就绪·优化点闭环·状态机精审

> 本补充审查令与主审查令（七席会审）并行执行，聚焦主令未覆盖的 **6 大盲区**。
> 审查铁律与主令相同：零幻觉、零跳过、零美化、证据链、交叉验证。

---

```markdown
# ═══════════════════════════════════════════════════════════
#  DmkWords V3.17 补充审查令 — 六大盲区深扫
#  与主审查令（七席会审）并行，聚焦文档一致性/部署/优化点/状态机
# ═══════════════════════════════════════════════════════════

## 审查输入（在主令基础上追加）

- DEPLOY_CHECKLIST.md（生产部署检查清单）
- 优化点拆解与依赖关系表.md（64 项优化点 + 依赖关系图）
- 全流程核心业务状态流转图与异常状态处理.md（10 域 + 13 异常场景）
- UML-ER.md（9 张状态图 + 18 张 ER 子图）
- 表结构.md（55 张表 V3.12）

---

## 补充关 1：文档四方一致性精审（P0 致命级）

### 1.1 枚举值四方对齐（表结构 ↔ PRD 附录 F ↔ UML-ER ↔ 代码 types.py）

逐枚举逐值比对，任何不一致即 P0：

| 实体 | 表结构定义 | PRD 附录 F | UML-ER 状态图 | 代码 types.py | 一致? |
|------|-----------|-----------|--------------|--------------|-------|
| Child.status | 0-4（5 态） | F.1: 0-4（5 态） | 1.1: 5 态 | ? | ? |
| BookCopy.status | 0-5（6 态） | F.2: 0-5（6 态） | 7.1: 6 态 | ? | ? |
| BorrowRecord.status | 0=借出 1=已还 2=逾期 3=丢失 | F.3: 0-2（3 态，无丢失!） | 1.6: 4 态（含丢失） | ? | ⚠️ |
| Deposit.status | 0-6（7 态） | F.10: 0-3（4 态!） | 1.7: 7 态 | ? | ⚠️ |
| Reservation.status | 0=待取 1=已备 2=已取 3=取消 | F.11: 0-3（无"已备"!） | 1.8: 3 态（无"已备"） | ? | ⚠️ |
| Order.pay_status | 0-5（6 态） | F.9: 0-3（4 态!） | 1.2: 6 态 | ? | ⚠️ |
| Order.type | 1=亲子课 2=观察期 3=正式会员 | 1.3a: 4=季度 5=半年 | — | ? | ⚠️ |
| Activity.status | 0-3（4 态） | F.5: 0-5（6 态!） | 6.1: 6 态 | ? | ⚠️ |
| Activity.type | 1-6 | F.6: 1-6 | — | ? | ? |
| ActivityEnrollment.status | 0-4（5 态） | F.17: 0-2（3 态!） | 1.4: 5 态 | ? | ⚠️ |
| SystemMessage.msg_type | 1=系统 2=活动 3=借阅 4=老师 5=阅读 | F.7: 1=系统 2=提醒 3=成就 4=报告 5=到期 | — | ? | ⚠️⚠️ |
| SystemMessage.priority | 0=低 1=中 2=高 | F.8: 0=普通 1=重要 2=紧急 | — | ? | ⚠️ |
| RefundApplication.status | 0-3（4 态） | F.18: 0-3（4 态） | 1.5: 4 态 | ? | ? |
| Quiz.status | 0=进行中 1=已完成 2=已过期 | F.16: 0=待完成 1=已完成（2 态!） | — | ? | ⚠️ |
| DamageReport.status | 0=待申诉 1=已确认 2=申诉中 3=已冲正 | F.13: 0-4（5 态，含已驳回/已结案!） | — | ? | ⚠️ |
| DamageReport.damage_level | 1-3 | F.12: 1-3 | — | ? | ? |
| CheckIn.check_type | 1-4 | F.4: 1-4 | — | ? | ? |
| ReadingSubmission.status | 0-2 | F.15: 0-2 | — | ? | ? |
| UserVocabulary.status | 0-1 | F.14: 0-1 | — | ? | ? |

**⚠️ 已发现的高危不一致（必须逐项确认代码实际使用哪个版本）**：

1. **BorrowRecord.status**：表结构有 `3=丢失`，PRD 附录 F.3 只到 2（逾期），UML 有 4 态。
   → 验证代码 `backend/common/types.py` 中 BorrowRecordStatus 枚举实际值。

2. **Deposit.status**：表结构 7 态（含 5=支付中、6=退款待审核），PRD 附录 F.10 只有 4 态。
   → 验证代码枚举 + 押金服务实际使用的状态值。

3. **Reservation.status**：表结构有 `1=已备`，PRD 附录 F.11 和 UML 均无此状态。
   → 验证代码中是否存在 status=1 的使用，若已废弃则表结构需更新。

4. **Order.type**：表结构只列 1-3，PRD 1.3a 明确有 4=季度、5=半年。
   → 验证代码 OrderType 枚举是否包含 4/5。

5. **Activity.status**：表结构 0-3（4 态），PRD 附录 F.5 有 0-5（6 态，含草稿/报名截止/已取消）。
   → 验证代码 ActivityStatus 枚举。

6. **ActivityEnrollment.status**：表结构 0-4（5 态），PRD 附录 F.17 只有 0-2（3 态）。
   → 验证代码枚举。

7. **SystemMessage.msg_type**：表结构与 PRD 附录 F.7 定义**完全不同**！
   - 表结构：1=系统通知 2=活动通知 3=借阅通知 4=老师消息 5=阅读提醒
   - PRD F.7：1=系统通知 2=提醒消息 3=成就消息 4=报告消息 5=到期提醒
   → **P0 致命**：验证代码实际使用哪个定义，消息发送逻辑是否匹配。

8. **SystemMessage.priority**：表结构 0=低/1=中/2=高，PRD F.8 0=普通/1=重要/2=紧急。
   → 语义不同但数值相同，验证前端展示文案是否匹配。

9. **Quiz.status**：表结构 0=进行中/1=已完成/2=已过期（3 态），PRD F.16 只有 0=待完成/1=已完成（2 态）。
   → 验证代码是否有"已过期"状态的使用。

10. **DamageReport.status**：表结构 0-3（4 态），PRD F.13 有 0-4（5 态，含 REJECTED/CLOSED）。
    → 验证代码枚举。

### 1.2 字段类型一致性（表结构 ↔ 代码 Model ↔ Alembic 迁移）

逐表检查以下高危类型问题：

| # | 表 | 字段 | 表结构类型 | 问题 | 代码实际类型 | 通过? |
|---|-----|------|-----------|------|-------------|-------|
| 1 | assessment | ar_level_before | float | ⚠️ 金额/等级应用 Decimal | ? | ? |
| 2 | assessment | ar_level_after | float | ⚠️ 同上 | ? | ? |
| 3 | assessment | comprehension_score | float | ⚠️ 百分比应用 Decimal | ? | ? |
| 4 | book_damage_report | reviewed_at | varchar(30) | ⚠️ 应为 datetime | ? | ? |
| 5 | dead_letter_event | resolved_at | varchar(30) | ⚠️ 应为 datetime | ? | ? |
| 6 | child | deposit_status | smallint | 表结构 smallint，代码 tinyint? | ? | ? |
| 7 | observation_evaluation | reading_interest 等 | smallint | 表结构 smallint，代码 tinyint? | ? | ? |

```bash
# 验证 assessment 表字段类型
grep -rn 'ar_level_before\|ar_level_after\|comprehension_score' \
  backend/domain/ --include="*.py" | grep -v '__pycache__'

# 验证 reviewed_at 字段类型
grep -rn 'reviewed_at' backend/domain/ --include="*.py" | grep -v '__pycache__'
```

### 1.3 ER 图覆盖完整性

UML-ER.md 声明覆盖至 V3.8（49 表），以下 6 张新表缺 ER 图：

| 表 | 模块 | ER 图? | 字段定义对齐? | 通过? |
|----|------|--------|-------------|-------|
| consent_record | 隐私合规 | ❌ 缺失 | ? | ? |
| message_read_status | 消息 | ❌ 缺失 | ? | ? |
| teacher_message | 消息 | ❌ 缺失 | ? | ? |
| assessment | 评估 | ❌ 缺失 | ? | ? |
| audio_file | 音频 | ❌ 缺失 | ? | ? |
| book_damage_report | 图书损坏 | ❌ 缺失 | ? | ? |

- [ ] 6 张新表的字段定义与 `表结构.md` §17 一致
- [ ] 外键关系正确（consent_record.user_id → user.id 等）
- [ ] 索引存在（consent_record.user_id 索引、message_read_status 联合唯一索引）

### 1.4 状态流转图 ↔ 代码实现精审

逐个状态图验证代码中的状态转换是否完整且无非法路径：

**押金状态机（最复杂，7 态）**：

| 转换 | UML 定义 | 代码实现(文件:行号) | 非法转换拦截? | 通过? |
|------|---------|-------------------|-------------|-------|
| UNPAID(0) → PAYING(5) | 用户调起支付 | ? | ? | ? |
| PAYING(5) → PAID(1) | 支付成功回调 | ? | ? | ? |
| PAYING(5) → UNPAID(0) | 支付失败/超时 | ? | ? | ? |
| PAID(1) → REFUND_PENDING(6) | 用户申请退款 | ? | ? | ? |
| REFUND_PENDING(6) → REFUNDING(4) | 管理员审核通过 | ? | ? | ? |
| REFUND_PENDING(6) → PAID(1) | 管理员审核拒绝 | ? | ? | ? |
| REFUNDING(4) → REFUNDED(2) | 退款到账确认 | ? | ? | ? |
| PAID(1) → DEDUCTED(3) | 丢书/损坏扣除 | ? | ? | ? |
| DEDUCTED(3) → PAID(1) | 补缴押金 | ? | ? | ? |
| REFUNDED(2) → PAID(1) | 重新缴纳 | ? | ? | ? |
| **非法**：UNPAID → REFUNDED | 不允许 | 拦截? | ? | ? |
| **非法**：DEDUCTED → REFUNDED | 不允许 | 拦截? | ? | ? |
| **非法**：REFUNDED → DEDUCTED | 不允许 | 拦截? | ? | ? |

**预约状态机（注意"已备"状态）**：

| 转换 | 表结构定义 | PRD/UML 定义 | 代码实现 | 一致? |
|------|-----------|-------------|---------|-------|
| PENDING(0) → FULFILLED(2) | 有 | 有 | ? | ? |
| PENDING(0) → CANCELLED(3) | 有 | 有 | ? | ? |
| PENDING(0) → EXPIRED(3) | 有 | 有 | ? | ? |
| PENDING(0) → READY(1) | 表结构有"已备" | PRD/UML 无 | ? | ⚠️ |

→ 若代码中 status=1（已备）从未使用，标记为 P2（表结构文档需更新）。
→ 若代码中使用了 status=1，标记为 P0（PRD/UML 需补充）。

---

## 补充关 2：64 项优化点逐项闭环验证

### 2.1 依赖关系图验证

```
本地存储封装 (utils/storage.js)
   ├── MP-004 阅读进度本地缓存
   ├── MP-007 答题进度本地保存
   ├── MP-026 退款申请草稿缓存
   └── PC-003 表单草稿缓存

通用容错组件 (components/error-view + empty-state)
   ├── MP-020 全局网络异常处理
   ├── MP-021 列表空状态占位
   ├── MP-033 接口请求失败白屏
   └── PC-026 接口异常白屏

统一提交防重复 (utils/submit-lock)
   ├── MP-019 操作无反馈导致重复点击
   ├── MP-023 支付中断状态查询
   └── PC-027 表单提交防重复

统一 Toast/Loading 规范 (admin.js)
   ├── PC-005 操作反馈不统一
   └── PC-026 接口异常暴露报错
```

- [ ] `frontend/utils/storage.js` 存在且被 4 项引用
- [ ] `frontend/components/error-view/` 存在且被 4 项引用
- [ ] `frontend/components/empty-state/` 存在且被列表页引用
- [ ] `frontend/utils/submit-lock.js`（或等效实现）存在且被 3 项引用
- [ ] `backend/static/admin/js/admin.js` 统一 Toast/Loading 存在

```bash
# 验证依赖组件存在性
ls frontend/utils/storage.js 2>/dev/null && echo "✅ storage.js" || echo "❌ storage.js 缺失"
ls frontend/components/error-view/ 2>/dev/null && echo "✅ error-view" || echo "❌ error-view 缺失"
ls frontend/components/empty-state/ 2>/dev/null && echo "✅ empty-state" || echo "❌ empty-state 缺失"
ls frontend/utils/submit-lock.js 2>/dev/null && echo "✅ submit-lock" || echo "❌ submit-lock 缺失"

# 验证引用关系
grep -rn 'storage\|setStorageSync\|getStorageSync' frontend/pages/ --include="*.js" | head -10
grep -rn 'error-view\|empty-state' frontend/pages/ --include="*.wxml" | head -10
grep -rn 'submit-lock\|submitWithLock\|submitLock' frontend/ --include="*.js" | head -10
```

### 2.2 第一批 P0 核心容错（15 项小程序 + 14 项 PC）

逐项验证：

| # | 编号 | 标题 | 验证方法 | 通过? | 证据 |
|---|------|------|---------|-------|------|
| 1 | MP-020 | 全局网络异常处理 | request.js 统一 fail 回调 + error-view 渲染 | ? | ? |
| 2 | MP-021 | 列表空状态占位 | 所有列表页有 empty-state 组件 | ? | ? |
| 3 | MP-033 | 接口请求失败白屏 | 500/超时渲染 error-view 而非白屏 | ? | ? |
| 4 | MP-001 | 音频加载状态反馈 | bgAudioManager.onWaiting/onCanplay 监听 | ? | ? |
| 5 | MP-002 | 中断续播确认 | onHide 暂停 + onShow 弹窗确认 | ? | ? |
| 6 | MP-003 | 逾期锁定引导 | 逾期页插画 + 引导文案 + 按钮 | ? | ? |
| 7 | MP-004 | 阅读进度本地缓存 | wx.setStorageSync 缓存进度 | ? | ? |
| 8 | MP-007 | 答题进度本地保存 | wx.setStorageSync 缓存答案 | ? | ? |
| 9 | MP-008 | 提交失败保留答案 | 失败不清 answers + 重试按钮 | ? | ? |
| 10 | MP-009 | 题库为空引导 | 空题库占位页 + 引导 | ? | ? |
| 11 | MP-012 | 查词失败兜底 | 失败提示 + 重试 + 自动加入生词本 | ? | ? |
| 12 | MP-015 | 打卡即时反馈 | 全屏动画 + 音效 + 震动 | ? | ? |
| 13 | MP-019 | 操作反馈防重复 | 按钮 disable + loading + 震动 | ? | ? |
| 14 | MP-018 | 触控区域规范 | 全局最小 88rpx | ? | ? |
| 15 | MP-034 | iOS 支付适配验证 | 统一 pay-button 组件，4 场景全适配 | ? | ? |
| 16 | PC-001 | 软删除+回收站 | 所有列表有回收站 Tab | ? | ? |
| 17 | PC-002 | 表单实时校验 | onblur 校验 + 红字提示 | ? | ? |
| 18 | PC-005 | 操作反馈统一 | admin.js 统一 Toast/Loading | ? | ? |
| 19 | PC-006 | 操作日志查看 | 操作日志页面存在 | ? | ? |
| 20 | PC-012 | 扫码借还异常提示 | 针对性错误引导 | ? | ? |
| 21 | PC-013 | 孩子选择搜索框 | 姓名/手机号模糊搜索 | ? | ? |
| 22 | PC-014 | 扣除二次确认 | 确认弹窗 + 姓名校验 | ? | ? |
| 23 | PC-018 | 退款审核自动校验 | 自动展示校验结果 | ? | ? |
| 24 | PC-021 | 用户管理页面 | 完整用户列表+详情 | ? | ? |
| 25 | PC-023 | 配置展示默认值 | 默认值列+恢复按钮 | ? | ? |
| 26 | PC-024 | 重要配置强提醒 | 二次确认+通知 | ? | ? |
| 27 | PC-026 | 接口异常统一处理 | 统一错误状态组件 | ? | ? |
| 28 | PC-027 | 表单防重复提交 | submitWithLock 工具 | ? | ? |
| 29 | PC-028 | 列表统一分页 | 统一分页组件 | ? | ? |

### 2.3 第二批 P0 业务闭环 + P1 高价值（20 项）

| # | 编号 | 标题 | 验证方法 | 通过? |
|---|------|------|---------|-------|
| 30 | MP-023 | 支付中断订单查询 | 支付中断后重新进入可查询订单状态 | ? |
| 31 | MP-024 | 报名前置条件展示 | 报名页展示所有前置条件及满足状态 | ? |
| 32 | MP-027 | 退款条件前置说明 | 退款页展示退款条件及满足状态 | ? |
| 33 | MP-028 | 关键节点醒目入口 | 借阅/预约/押金入口醒目 | ? |
| 34 | MP-013 | 查词弹窗不打断音频 | 查词浮层不影响音频播放 | ? |
| 35 | MP-005 | 倍速切换反馈 | 0.75x/1x/1.25x/1.5x 切换有反馈 | ? |
| 36 | MP-006 | 锁屏播放适配 | getBackgroundAudioManager 锁屏可用 | ? |
| 37 | MP-025 | 退款金额明细展示 | 展示计算公式和明细 | ? |
| 38 | MP-026 | 退款草稿缓存 | 退款表单草稿本地缓存 | ? |
| 39 | MP-029 | 预约倒计时 | 72h 倒计时显示 | ? |
| 40 | MP-030 | 多孩子切换便捷化 | 首页顶部孩子头像切换 | ? |
| 41 | MP-031 | 分享失败兜底 | 分享失败有提示 | ? |
| 42 | MP-032 | 下拉刷新上拉加载 | 列表页支持下拉刷新+上拉加载 | ? |
| 43 | PC-003 | 表单草稿缓存 | 管理端表单草稿缓存 | ? |
| 44 | PC-004 | 批量操作 | 列表支持批量选择+操作 | ? |
| 45 | PC-008 | ISBN 批量导入 | 图书 ISBN 批量导入 | ? |
| 46 | PC-009 | 批量生成条码 | 馆藏条码批量生成 | ? |
| 47 | PC-010 | 文件上传进度 | 上传进度条 | ? |
| 48 | PC-016 | 题目批量导入 | 题库批量导入 | ? |
| 49 | PC-020 | 批量导出/签到 | 活动批量导出+签到 | ? |

### 2.4 第三批 P1 体验打磨（15 项）

| # | 编号 | 标题 | 验证方法 | 通过? |
|---|------|------|---------|-------|
| 50 | MP-010 | 答题触控区域优化 | 选项最小触控区域 | ? |
| 51 | MP-011 | 答题进度条动画 | 进度条有动画 | ? |
| 52 | MP-014 | 复习进度激励 | 生词复习有进度激励 | ? |
| 53 | MP-016 | 晋级仪式感 | 晋级有动画/特效 | ? |
| 54 | MP-017 | 徽章展示优化 | 徽章彩色/灰色区分 | ? |
| 55 | MP-022 | 图标+语音引导 | 关键操作有语音引导 | ? |
| 56 | PC-007 | 权限入口隐藏 | 无权限菜单不可见 | ? |
| 57 | PC-011 | 上下架库存提示 | 上下架有库存提示 | ? |
| 58 | PC-015 | 批量逾期提醒 | 批量发送逾期提醒 | ? |
| 59 | PC-017 | 测验成绩导出 | 测验成绩导出 | ? |
| 60 | PC-019 | 多状态筛选导出 | 订单多状态筛选+导出 | ? |
| 61 | PC-022 | 孩子多条件筛选 | 孩子列表多条件筛选 | ? |
| 62 | PC-025 | 配置分类展示 | 配置按分类 Tab 展示 | ? |
| 63 | PC-029 | 骨架屏 | 管理端首屏骨架屏 | ? |
| 64 | PC-030 | 全局搜索 | 管理端全局搜索 | ? |

**通过标准**：64/64 全部通过。任何一项"❌ 缺失"或"未实现" → 列出并标 P1/P2。

---

## 补充关 3：异常处理全量精审（10 域 × 13 场景）

### 3.1 异常处理矩阵（全流程核心业务状态流转图）

逐条验证代码中的异常处理是否与文档一致：

| # | 域 | 异常场景 | 文档定义的处理方式 | 代码实现(文件:行号) | 前端提示文案 | 一致? |
|---|-----|---------|------------------|-------------------|-------------|-------|
| 1 | 会员 | 支付成功但状态未更新 | 检查支付回调，重试 | ? | ? | ? |
| 2 | 会员 | 续费后会员状态未更新 | 定时任务修复 | ? | ? | ? |
| 3 | 订单 | 重复支付 | 订单已支付直接返回 | ? | ? | ? |
| 4 | 订单 | 退款 7 天未到账 | 定时任务告警 | ? | ? | ? |
| 5 | 晋级 | 题库为空 | 提示"该书暂无测评题目，完成后请联系管理员" | ? | ? | ? |
| 6 | 晋级 | 同一本书重复测评 | 不重复计分，但允许再做一次 | ? | ? | ? |
| 7 | 书架 | 重复加入同一本书 | 提示"该书已在清单中" | ? | ? | ? |
| 8 | 书架 | 预约时库存不足 | 提示"暂无库存，可到店咨询" | ? | ? | ? |
| 9 | 观察期 | 用户中途退出 | 按天数扣费退款 | ? | ? | ? |
| 10 | 活动 | 活动取消 | 自动全额退款，无需用户申请 | ? | ? | ? |
| 11 | 副本 | 扫码时副本不存在 | 提示"该书未入库，请先扫描入库" | ? | ? | ? |
| 12 | 副本 | 扫码时副本已借出 | 提示"该书已被借出，预计归还日期：{date}" | ? | ? | ? |
| 13 | 副本 | 扫码时副本在维修 | 提示"该书正在维修中，暂时无法借阅" | ? | ? | ? |
| 14 | 副本 | 扫码时副本已报废 | 提示"该书已报废，无法借阅" | ? | ? | ? |
| 15 | 押金 | 退押金时有未还书 | 拦截，提示"请先归还所有图书" | ? | ? | ? |
| 16 | 押金 | 退押金时有未缴罚款 | 拦截，提示"请先缴清罚款" | ? | ? | ? |
| 17 | 押金 | 重复支付押金 | 订单已支付直接返回，不重复扣款 | ? | ? | ? |
| 18 | 预约 | 预约时库存不足 | 提示"暂无库存，可预约" | ? | ? | ? |
| 19 | 预约 | 预约时已有相同书未归还 | 提示"您已借阅此书，请先归还" | ? | ? | ? |
| 20 | 预约 | 72 小时超时未取 | 定时任务自动取消，释放库存 | ? | ? | ? |
| 21 | 预约 | 已取时副本状态异常 | 拦截，提示"该副本状态异常，请联系工作人员" | ? | ? | ? |
| 22 | 权益转让 | 审核中不能重复提交 | 提示"已有待审核的转让申请，请耐心等待" | ? | ? | ? |
| 23 | 权益转让 | 驳回后可重新提交 | 允许修改后重新申请 | ? | ? | ? |
| 24 | 权益转让 | 押金不能转让 | 押金独立管理，不随会员转移 | ? | ? | ? |
| 25 | 权益转让 | 源孩子有未归还图书 | 提示"有未归还图书，请先归还后再转让" | ? | ? | ? |
| 26 | 权益转让 | 目标孩子已是正式会员 | 提示"目标孩子已是正式会员，无需转让" | ? | ? | ? |
| 27 | 借阅 | 借阅时库存不足 | 提示"暂无库存，可预约" | ? | ? | ? |
| 28 | 借阅 | 借阅时押金未付 | 提示"请先缴纳押金 ¥{deposit_amount}" | ? | ? | ? |
| 29 | 借阅 | 借阅时已达上限 | 提示"已达最大借阅数，请先归还部分图书" | ? | ? | ? |
| 30 | 归还 | 归还时逾期 | 显示逾期天数 + 罚款金额 | ? | ? | ? |
| 31 | 归还 | 归还时图书损坏 | 提示"图书损坏，需缴纳维修费" | ? | ? | ? |
| 32 | 归还 | 归还时图书丢失 | 扣除押金（定价 × 1.5），标记副本"丢失" | ? | ? | ? |

### 3.2 逾期还书"先还后罚"（D8 决策）

- [ ] 逾期还书流程：先创建还书记录（status=RETURNED）→ 再计算罚款 → 再更新 outstanding_fines
- [ ] 非"先罚款后还书"（防止罚款失败导致书还不了）
- [ ] 罚款计算使用 `overdue_fine_per_day` 配置值
- [ ] 罚款金额 = 逾期天数 × 配置值（非硬编码 1 元）

### 3.3 亲子课 30 人上限（D9 决策）

- [ ] `parent_course_time.max_participants` 默认 10（表结构）vs PRD 说 30 人
- [ ] 验证代码中实际上限值
- [ ] 名额已满时按钮置灰 + 提示"该时间段名额已满，请选择其他时间"

```bash
grep -rn 'max_participants' backend/domain/ --include="*.py" | grep -v '__pycache__'
```

---

## 补充关 4：部署就绪全量验证（DEPLOY_CHECKLIST.md）

### 4.1 外部依赖就绪

| # | 检查项 | 状态 | 阻塞上线? | 验证方法 |
|---|--------|------|----------|---------|
| 1 | 微信小程序真实 appid | ⬜ | 是 | `grep appid frontend/project.config.json` |
| 2 | 短信签名审核通过 | ⬜ | 是（上线需） | 腾讯云/Aliyun 控制台 |
| 3 | 短信模板 ID 就绪 | ⬜ | 是（上线需） | `.env` 中 SMS_TEMPLATE_CODE |
| 4 | 微信支付商户号开通 | ⬜ | 是 | 商户平台 |
| 5 | APIv3 证书下载 | ⬜ | 是 | PEM 文件存在 |
| 6 | 隐私保护指引提交 | ⬜ | 是 | 微信公众平台 |

### 4.2 环境变量安全

```bash
# 生产环境必须全部为 false
grep -n 'DEBUG\|ENABLE_TEST_TOKEN\|MOCK_PAYMENT\|MOCK_SMS' .env .env.example 2>/dev/null
```

- [ ] `DEBUG=false`
- [ ] `ENABLE_TEST_TOKEN=false`
- [ ] `MOCK_PAYMENT=false`
- [ ] `MOCK_SMS=false`
- [ ] `SECRET_KEY` 已改为随机值（非默认值）
- [ ] 微信支付私钥权限 `chmod 600`

### 4.3 WeasyPrint PDF 生成

```bash
# 冒烟测试
python -c "import weasyprint; print('WeasyPrint OK:', weasyprint.__version__)"
```

- [ ] 系统包已安装（libpango/libpangocairo/libgdk-pixbuf/libffi）
- [ ] 中文字体已安装（fonts-noto-cjk / fonts-wqy-microhei）
- [ ] 观察期报告 PDF 生成正常
- [ ] 晋级证书 PDF 生成正常

### 4.4 HTTPS + 域名 + 回调

- [ ] 域名已解析
- [ ] SSL 证书已配置
- [ ] Nginx/Caddy 反向代理到 `127.0.0.1:8002`
- [ ] 微信支付回调可达：`https://<domain>/order/payment-callback`
- [ ] 押金回调可达：`https://<domain>/deposit/callback`
- [ ] 微信登录可达：`https://<domain>/user/wx-login`

### 4.5 进程保活与健康检查

- [ ] systemd / supervisor 配置存在
- [ ] `GET /health` 返回 `{"status": "ok", "version": "0.1.0"}`
- [ ] 异常告警已配置（企业微信/Slack/邮件）

### 4.6 回滚方案

| 层 | 回滚方式 | 验证? |
|----|---------|-------|
| 数据库 | `alembic downgrade -1` | ? |
| 代码 | `git revert <last-deploy-commit>` | ? |
| 小程序 | 微信公众平台 → 版本管理 → 历史版本 | ? |
| 服务器 | 保留上一版本快照/容器镜像 | ? |

### 4.7 真实网关冒烟测试

```bash
# 微信支付证书可读性
venv/bin/python -c "
from backend.integrations.wechat.pay_v3 import WeChatPayV3
p = WeChatPayV3()
assert p.private_key is not None, '商户私钥未加载'
assert p.platform_cert is not None, '平台证书未加载'
print('WeChatPayV3 OK')
"

# 短信网关配置合法
venv/bin/python -c "
from backend.common.dependencies import get_sms_gateway
print(type(get_sms_gateway()).__name__)
"
```

---

## 补充关 5：数据库 55 表全量字段精审

### 5.1 标准字段齐全性

逐表检查 `create_time` / `update_time` / `is_deleted` 三个标准字段：

```bash
# 扫描所有 Model 文件，检查标准字段
for model_file in backend/domain/*/models.py backend/domain/admin/models.py; do
  echo "=== $model_file ==="
  grep -c 'create_time\|update_time\|is_deleted' "$model_file" 2>/dev/null
done
```

- [ ] 55 张表全部有 `create_time`（datetime, 默认 CURRENT_TIMESTAMP）
- [ ] 55 张表全部有 `update_time`（datetime, ON UPDATE）
- [ ] 55 张表全部有 `is_deleted`（tinyint, 默认 0）
- [ ] 主键全部为 `id`（bigint, 自增）

### 5.2 外键关系完整性

逐表验证外键是否指向正确的表：

| 表 | 外键字段 | 应指向 | 代码中指向 | 通过? |
|----|---------|--------|-----------|-------|
| child | user_id | user.id | ? | ? |
| child | teacher_id | teacher.id | ? | ? |
| child | venue_id | venue.id | ? | ? |
| child | current_level_id | level.id | ? | ? |
| book_copy | book_id | book.id | ? | ? |
| book_damage_report | borrow_record_id | borrow_record.id | ? | ? |
| book_damage_report | book_copy_id | book_copy.id | ? | ? |
| book_damage_report | child_id | child.id | ? | ? |
| bookshelf | child_id | child.id | ? | ? |
| bookshelf | book_id | book.id | ? | ? |
| borrow_record | child_id | child.id | ? | ? |
| borrow_record | book_id | book.id | ? | ? |
| deposit_record | child_id | child.id | ? | ? |
| reservation | child_id | child.id | ? | ? |
| reservation | book_id | book.id | ? | ? |
| reservation | borrow_record_id | borrow_record.id | ? | ? |
| order | user_id | user.id | ? | ? |
| order | child_id | child.id | ? | ? |
| refund_application | order_id | order.id | ? | ? |
| refund_application | child_id | child.id | ? | ? |
| refund_application | user_id | user.id | ? | ? |
| benefit_transfer_application | source_child_id | child.id | ? | ? |
| benefit_transfer_application | target_child_id | child.id | ? | ? |
| benefit_transfer_application | user_id | user.id | ? | ? |
| activity_enrollment | activity_id | activity.id | ? | ? |
| activity_enrollment | child_id | child.id | ? | ? |
| quiz | child_id | child.id | ? | ? |
| quiz | book_id | book.id | ? | ? |
| quiz | submission_id | reading_submission.id | ? | ? |
| quiz_answer | quiz_id | quiz.id | ? | ? |
| quiz_answer | question_id | question_bank.id | ? | ? |
| quiz_question | quiz_id | quiz.id | ? | ? |
| quiz_question | question_id | question_bank.id | ? | ? |
| child_level | child_id | child.id | ? | ? |
| child_level | level_id | level.id | ? | ? |
| child_achievement | child_id | child.id | ? | ? |
| child_achievement | achievement_id | achievement.id | ? | ? |
| level_certificate | child_id | child.id | ? | ? |
| level_certificate | level_id | level.id | ? | ? |
| observation_report | child_id | child.id | ? | ? |
| learning_report | child_id | child.id | ? | ? |
| consent_record | user_id | user.id | ? | ? |
| message_read_status | message_id | system_message.id | ? | ? |
| message_read_status | user_id | user.id | ? | ? |
| admin | admin_role_id | role.id | ? | ? |
| admin | teacher_id | teacher.id | ? | ? |
| admin | venue_id | venue.id | ? | ? |
| role_permission | role_id | role.id | ? | ? |
| teacher_schedule | teacher_id | teacher.id | ? | ? |
| parent_course_time | venue_id | venue.id | ? | ? |
| audio_file | book_id | book.id | ? | ? |
| book_page | book_id | book.id | ? | ? |
| user_vocabulary | child_id | child.id | ? | ? |
| user_vocabulary | word_id | dictionary_word.id | ? | ? |
| user_vocabulary | book_id | book.id | ? | ? |

### 5.3 唯一索引完整性

| 表 | UK 字段 | 索引存在? | 通过? |
|----|--------|----------|-------|
| user | phone | ? | ? |
| user | openid | ? | ? |
| book | isbn | ? | ? |
| book_copy | barcode | ? | ? |
| dictionary_word | word | ? | ? |
| level | name | ? | ? |
| activity_enrollment | ticket_code | ? | ? |
| order | order_no | ? | ? |
| level_certificate | certificate_no | ? | ? |
| role | code | ? | ? |
| permission | code | ? | ? |
| admin | username | ? | ? |
| system_config | config_key | ? | ? |

### 5.4 表结构文档 ↔ 代码 Model 逐字段对齐

抽检以下 10 张核心表（每张表逐字段）：

| 表 | 字段数(文档) | 字段数(代码) | 差异 | 通过? |
|----|------------|------------|------|-------|
| child | 22 | ? | ? | ? |
| book | 27 | ? | ? | ? |
| book_copy | 7 | ? | ? | ? |
| book_damage_report | 17 | ? | ? | ? |
| borrow_record | 10 | ? | ? | ? |
| deposit_record | 8 | ? | ? | ? |
| reservation | 8 | ? | ? | ? |
| order | 15 | ? | ? | ? |
| refund_application | 14 | ? | ? | ? |
| consent_record | 10 | ? | ? | ? |

```bash
venv/bin/python -m scripts.check_model_consistency
```

---

## 补充关 6：交叉验证与反向审查

### 6.1 PRD ↔ 表结构 ↔ UML-ER 三方不一致汇总

| # | 不一致项 | PRD 定义 | 表结构定义 | UML-ER 定义 | 代码实际 | 严重程度 |
|---|---------|---------|-----------|------------|---------|---------|
| 1 | Reservation "已备"状态 | 无 | status=1 已备 | 无 | ? | P0/P2 |
| 2 | SystemMessage.msg_type | F.7: 系统/提醒/成就/报告/到期 | 系统/活动/借阅/老师/阅读 | — | ? | P0 |
| 3 | Order.type 季度/半年 | 4=季度 5=半年 | 只列 1-3 | — | ? | P0 |
| 4 | Activity.status 6 态 | F.5: 0-5 | 0-3 | 6 态 | ? | P0 |
| 5 | Deposit.status 7 态 | F.10: 0-3 | 0-6 | 7 态 | ? | P0 |
| 6 | BorrowRecord 丢失态 | F.3: 0-2 | 0-3（含丢失） | 4 态 | ? | P0 |
| 7 | ActivityEnrollment 5 态 | F.17: 0-2 | 0-4 | 5 态 | ? | P0 |
| 8 | Quiz.status 3 态 | F.16: 0-1 | 0-2 | — | ? | P1 |
| 9 | DamageReport.status | F.13: 0-4 | 0-3 | — | ? | P1 |
| 10 | parent_course_time 人数 | PRD: 30 人 | 默认 10 | — | ? | P1 |
| 11 | assessment float 类型 | — | float | — | ? | P1 |
| 12 | reviewed_at varchar | — | varchar(30) | — | ? | P2 |

### 6.2 代码写了但文档没写的功能

```bash
# 扫描代码中所有路由端点
grep -rn '@router\.\|@app\.' backend/domain/ backend/main.py --include="*.py" \
  | grep -v '__pycache__' | wc -l
# 与 PRD 附录 C 的 93 个端点对比
```

- [ ] 代码中的每个端点在 PRD 中有对应描述
- [ ] PRD 附录 C 的每个端点在代码中有实现
- [ ] 无"幽灵端点"（代码有但 PRD 无）
- [ ] 无"僵尸端点"（PRD 有但代码无）

### 6.3 测试写了但断言是假的

```bash
# 假绿断言
grep -rn 'assert True\|assert 1 == 1\|assert "" == ""' tests/ features/ --include="*.py"
# 空断言
grep -rn 'assert$\|assert None$' tests/ --include="*.py"
# 永远通过的断言
grep -rn 'assert .* is not None' tests/ --include="*.py" | head -20
```

### 6.4 前端调了但后端没接的 API

```bash
# 前端 API 调用
grep -rn 'wx\.request\|api\.\|request(' frontend/ --include="*.js" \
  | grep -o "'/[a-z/-]*'" | sort -u > /tmp/frontend_apis.txt

# 后端路由注册
grep -rn '@router\.\(get\|post\|put\|delete\|patch\)' backend/ --include="*.py" \
  | grep -o '"[^"]*"' | sort -u > /tmp/backend_apis.txt

# 对比
diff /tmp/frontend_apis.txt /tmp/backend_apis.txt
```

### 6.5 配置项定义了但代码没读取的

```bash
# 动态配置清单中的 38 个键
for key in trial_pages vocab_lookup_limit enable_trial_reading enable_vocab_lookup \
  observation_days member_days member_grace_days renewal_discount multi_child_discount \
  borrow_limit borrow_period_days due_remind_days overdue_fine_per_day \
  lost_book_fine_multiplier deposit_amount reservation_expire_hours \
  default_required_books quiz_pass_rate quiz_total_questions quiz_pass_count \
  require_teacher_review quiz_cooldown_minutes checkin_min_minutes checkin_min_vocab \
  daily_checkin_limit bookshelf_limit venue_name venue_address order_expire_minutes \
  price_parent_course price_observation price_official_member price_quarterly \
  price_semi_annual admin_token_expire_hours activity_cancel_hours \
  member_expire_remind_days observation_remind_days; do
  count=$(grep -rn "$key" backend/domain/ backend/common/ backend/tasks/ \
    --include="*.py" | grep -v '__pycache__' | grep -v 'DEFAULTS\|seeds/' | wc -l)
  if [ "$count" -eq 0 ]; then
    echo "❌ 未使用: $key"
  fi
done
```

---

## 输出格式（补充报告）

### 补充审查总览

| 关 | 名称 | 子项数 | 通过 | 失败 | P0 | P1 | P2 |
|----|------|--------|------|------|----|----|-----|
| 1 | 文档四方一致性 | ? | ? | ? | ? | ? | ? |
| 2 | 64 项优化点闭环 | 64 | ? | ? | ? | ? | ? |
| 3 | 异常处理精审 | 32 | ? | ? | ? | ? | ? |
| 4 | 部署就绪验证 | ? | ? | ? | ? | ? | ? |
| 5 | 55 表字段精审 | ? | ? | ? | ? | ? | ? |
| 6 | 交叉验证与反向审查 | ? | ? | ? | ? | ? | ? |
| **合计** | | **?** | **?** | **?** | **?** | **?** | **?** |

### 文档不一致清单（必须修复）

| # | 不一致项 | 文档 A | 文档 B | 代码实际 | 修复方案 | 优先级 |
|---|---------|--------|--------|---------|---------|--------|

### 优化点缺失清单

| # | 编号 | 标题 | 缺失原因 | 影响 | 优先级 |
|---|------|------|---------|------|--------|

### 部署阻塞项

| # | 检查项 | 状态 | 责任方 | 预计解决时间 |
|---|--------|------|--------|-------------|

### 与主审查令合并判定

- [ ] 主令 P0 = 0 AND 补充令 P0 = 0 → ✅ 允许上线
- [ ] 任一 P0 > 0 → 🚫 禁止上线

---

## 执行指令

现在开始执行。从补充关 1 的 1.1 枚举值四方对齐开始，逐项推进。
不要询问"是否继续"，不要停顿，不要跳过任何子项。
遇到阻断点时标记 🚫 并继续下一项。
全部 6 关执行完毕后输出补充审查报告，与主审查令报告合并。

记住：文档不一致 = 线上事故。
枚举值对不上 = 状态机崩溃。
类型用错 = 金额精度丢失。
部署检查遗漏 = 上线即回滚。
```

---

**与主令的关系**：本补充令覆盖主令的 6 大盲区——**文档四方一致性**（枚举值/字段类型/ER 图）、**64 项优化点闭环**、**32 条异常处理精审**、**部署就绪全量验证**（WeasyPrint/HTTPS/回滚/冒烟）、**55 表字段级精审**（外键/索引/标准字段）、**交叉反向审查**（幽灵端点/僵尸端点/假绿断言/未使用配置）。两份报告合并后，七席 + 六关全部通过方可上线。