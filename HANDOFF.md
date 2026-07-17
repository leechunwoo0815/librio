# DmkWords (librio) 项目交接文档

> **生成时间**: 2026-07-17 GMT+8 (v10)
> **项目版本**: V3.10 — 零宕机审查 8/8 + fix-prompts 8 项修复完成
> **项目状态**: ✅ 零宕机审查 8/8 根因验证 + 修复 + 全绿回归 | fix-prompts 8 项: T4/T6/T7/T8 ✅, T1/T2/T3/T5 ⏳ | pytest 175/4/0 | ruff 0 | seeder 统一 DEFAULTS (37 键) | emoji 285→0 裸露 (31/31 文件) | deposit/borrow/advancement 测试修正 | COO 报告 3/3 | PRD 对齐 §11.5 | 施工指令 6/6 | 安全 7/7 + N+1 19 处 + 微信合规 + 日志全域 + 第三方终审 9 项 + 专家意见交付

---

## 一、项目概况

DmkWords 是 3-15 岁儿童英文阅读 OMO 平台：微信小程序 31 页 + PC 管理后台 36 模板 + FastAPI 后端 26 领域模块（49 张表 / 180+ API / 14 定时任务）。

## 二、本轮会话（2026-07-17 零宕机审查 + fix-prompts 修复轮次）

### 施工指令 6/6 执行完毕

基于专家审查的 `专家意见/~施工指令-给大模型.md`，完成 3 P1 + 5 P2 timer + 1 P2 样式修复：

| 项目 | 文件 | 修复内容 |
|------|------|---------|
| P1-1 observation-report 裸属性 | `frontend/pages/observation/pkg/report/report.js:113,138` | 5 处 `?.` 可选链防崩溃 |
| P1-2 levels.html 表单 loading | `backend/templates/admin/levels.html:100-108,167-175` | 保存/删除按钮 loading 状态 + 防重复提交 |
| P1-3 users.html 内联函数 | `backend/templates/admin/users.html:115-140` | 24 个 onclick="..." 外迁到 `users.js` |
| P2-1~5 timer 清理 | 5 页: `assessment.js, evaluation.js, reading-stats.js, stats.js, book-detail.js` | `setInterval`/`setTimeout` 在 `onUnload` 中 `clear` |
| P2-6 3 模板风格统一 | `observation-history.wxml, evaluation.wxml, reading-stats.wxml` | `bindsubmit` + `form-type` 统一 |
| P2 样式修复 | `backend/static/admin/css/pages/achievements.css` | `.level-btn-group.flex-wrap` → `.btn-group` + align 修复 |

### COO 报告审查（3 行动项已修复）

| 行动项 | 修复 |
|--------|------|
| Action 4: 会员续费重置 bug | `order_handlers.py:51-65` — `member_expire_time > now` 时延长 |
| Action 6: 优惠权益登记 | `common_steps.py:135-165` — coupons 多态处理（dict/list/None） |
| Action 16: 运营活动引导文案 | `frontend/pages/activity/activity.wxml` — 占位文案已填充示例 |

### PRD 对齐修正（§11.5）

`PRD/DmkWords_V3.5需求文档.md` 第 11.5 节时序图修正：prepay_id 获取 → wx.requestPayment → 异步回调 → 定时状态轮询（非同步等待支付结果）。

### 零宕机审查 8/8 根因验证 + 修复

| Bug | 级别 | 文件 | 根因 | 修复 |
|-----|------|------|------|------|
| F6 阅读时长清零 | Fatal | `reader.js:450-454` + `api.js:35` + `schemas.py:57-58` | `endSession(sid)` 未传 0 值 → `s.minutes`/`s.words` 无默认值 → `background` `try` 无 `await` | `endSession(sid, 0, words, minutes)` + `async onUnload()` + try/await + 4 级错误吞咽全堵 |
| F5 无限转圈 | Fatal | `quiz.wxml:3-4` + `schemas.py:85-93` + `service.py:142-153` + `quiz.js:73-74` | 答题页无 error-view、loading 无取消按钮、`correct_answer` 从 API 响应中缺失 | error-view 含重试+返回、loading-cancel 按钮、`correct_answer` 补回 API |
| F3 无音频 | Fatal | `reader.wxml:38` + `reader.js:122-124,296` + `service.py:113-115` | `audio_url` 未从后端赋值、`bgAudioManager.play()` 未调用、缺无音频提示 | `wx:elif` 无音频提示、`audio_url` 后端赋值、`bgAudioManager.play()` |
| F2 提交白屏 | Fatal | `quiz-result.wxml:6` + `schemas.py:64-67` + `quiz.js:220-223` | `total===0` 时 `100%(0/0)` 分母零 + `is_correct`/`score` 字段名不匹配 | `total===0` fallback、对齐 request/response schema |
| F1 ¥NaN | Fatal | `official.js:75-78,98-102` + `order-history.js:70` | `rawPrice` 未初始化或 `null` 时 `Number(null)`=0→`toFixed(2)`→`NaN` | `(rawPrice != null && !isNaN(rawPrice)) ? Number(rawPrice) : 0` |
| F4 null.find() | Fatal | `child-manage.js/wxml:26,79` + `index.js:255` + `benefit-transfer.js/wxml:45-47` | API 返回 `null`/`undefined` 数组时 `.find()` 崩溃 | 5 处 `\|\| []` 保护 |
| S1 支付参数空 | Serious | `deposit/schemas.py` + `deposit/service.py:107` + 前端 3 页 | `DepositPayResponse` 缺 `pay_params` 字段 | `DepositPayResponse` 含 `pay_params`；前端校验 5 必填字段 |
| S2 回调丢失 | Serious | `order/router.py:164-168` + `pay_v3.py:241` + `deposit/router.py:104` + `mock_routes.py:46-51` | 回调 `amount` 字段缺失、分↔元转换、mock 实名字段 | 补 `amount` 字段；分转元；修 mock 字段名 |

### 风险升级

- **S2 回调丢失** 从 Serious → **Fatal**（微信回调全员丢失 = 资金链断裂）

### 测试更新

| 测试 | 变更 |
|------|------|
| `test_get_quiz_questions` | 断言从"不暴露 correct_answer"改为"返回 correct_answer=..." |
| `test_pay_deposit_with_mock_gateway` | `result.deposit.status` 断言修正 |
| `test_pay_deposit` | `result.deposit.status` 断言修正 |
| `test_pay_deposit_returns_pay_params` | 新增：`DepositPayResponse.pay_params` 非空校验 |

### 文档

| 文件 | 用途 |
|------|------|
| `专家意见/小程序零宕机审查.md` | 小程序 31 页 + 后端 180 API 全链路审查报告 |
| `专家意见/零宕机审查-根因验证.md` | 8 个 bug 的 root cause trace 文档 |

### Fix-Prompts 修复轮次（新增）

基于 `docs/fix-prompts_20260717.md` + 齐活林补充审查，完成 8 项任务中 4 项可执行修复，4 项需外部输入：

#### 任务总览

| # | 优先级 | 内容 | 状态 | 关键改动 |
|---|--------|------|------|---------|
| 7 | P1 | seeder 键名修复 + 统一 DEFAULTS | ✅ 超额完成 | `seed_default_configs` 重写为循环 `SystemConfig.DEFAULTS.items()`；死键 `observation_price`/`official_member_price` 软删除 |
| 8 | 低 | ruff lint 清理 | ✅ 完成 | 92→0 errors: 17 auto-fix (F401) + 72 E702 (分号) + 2 F841 + 1 E701 |
| 6 | P2 | 删除 premium-hero::before | ✅ 完成 | `official.wxss:425-433` 伪元素规则块删除 |
| 4 | P1 | iconfont 替换 emoji | ✅ 完成 | 285 emoji→62 icon 类, 31/31 WXML 文件部署, 0 裸露 emoji, 渐进增强降级 |
| 1 | P0 | 替换 appid 占位符 | ⏳ 待外部 | 需微信公众平台获取真实 appid |
| 2 | P0 | 补全服务协议页 | ⏳ 待法务 | 需法务/运营提供法律文本 |
| 3 | P0 | 填写隐私政策主体 | ⏳ 待运营 | 需与认证主体一致的全称 |
| 5 | P2 | reading-stats 折线图 | ⏳ 待产品 | 需产品决策 |

#### Task 7 详细 — seeder 统一 DEFAULTS

`backend/seeds/seed_rbac.py:300-335` 重写，核心逻辑：

```python
for key, (value, typ, desc) in SystemConfig.DEFAULTS.items():
    existing = db.query(SystemConfig).filter(
        SystemConfig.config_key == key,
        SystemConfig.is_deleted == 0,
    ).first()
    if not existing:
        db.add(SystemConfig(config_key=key, config_value=value, config_type=typ, description=desc))
db.flush()
```

**效果**: 37/37 键自动初始化；死键 `observation_price`/`official_member_price` 已软删除；config_type 与 DEFAULTS 定义自动一致。不再需要手动维护 seeder 键列表。

#### Task 4 详细 — iconfont 优雅降级

285 emoji 全部包裹为 `<text class="icon icon-xxx">回退字符</text>`。@font-face 注释在 `app.wxss` 中待真实 woff2 文件。当前回退链：iconfont 字体不存在 → 回退到原生 emoji（零用户感知变化）。

```css
/* app.wxss — TODO: 上线前从 iconfont.cn 下载真实字体文件 */
/* @font-face { font-family: 'iconfont'; src: url('/static/iconfont/iconfont.woff2'); } */
.icon { font-family: 'iconfont', 'Apple Color Emoji', 'Segoe UI Emoji', sans-serif; }
```

#### 零宕机审查测试修复（git checkout 回滚恢复）

`git checkout -- tests/` 在执行 ruff 自动修复时意外回滚了零宕机审查的 5 个测试变更，已重新恢复：

| 测试 | 修复内容 |
|------|---------|
| `test_deposit_service.py` (8 个测试) | `current_user=` 参数补回；`AsyncMock` gateway 包装；`REFUND_PENDING` 状态；`test_pay_deposit_returns_pay_params` 新增 |
| `test_borrow_service.py::test_get_child_borrows` | 断言从 flat list 改为 `records, total = svc.get_child_borrows(...)` 元组解包 |
| `test_advancement_service.py::test_get_quiz_questions` | 断言从"不暴露 correct_answer"改为"返回 `correct_answer=...`" |

#### 全局配置键状态

37 个配种键在 `SystemConfig.DEFAULTS` 中定义（`backend/domain/admin/models.py:77-140`）：
- 6 个价格键 (`price_observation`/`price_official_member`/`deposit_amount` 等)
- 5 个时间窗口 (`borrow_period_days`/`reservation_expire_hours`/`observation_days`/`member_days`/`quiz_pass_count`)
- 3 个罚款/分数键 (`overdue_fine_per_day`/`lost_book_fine_multiplier`/`quiz_pass_rate`)
- 2 个约束键 (`borrow_limit`/`checkin_min_minutes`)
- 2 个提醒键 (`due_remind_days`/`member_expire_remind_days`)
- 19 个其他运营/评估/报告配置

---

## 三、前次会话（2026-07-15 v4）

### 第三方终审修复（9 项）

| # | 等级 | 问题 | 修复 |
|---|------|------|------|
| P0-1 | 架构 | `child/router.py:98` Router ORM | 下沉 Service |
| P0-2 | 架构 | `admin_activities_router.py:169` Router ORM | 下沉 Service |
| P0-3 | 业务 | 押金退款缺审核 | `REFUND_PENDING` + `audit_refund` + 端点 + 迁移 |
| P0-4 | 合规 | 运营主体占位符 | `COMPANY_NAME` env var |
| P0-5 | 合规 | 缺办学资质 | WXML §九 展示区 |
| P1-12 | 业务 | 押金校验不一致 | 统一 `(PAID,REFUNDING,REFUND_PENDING)` |
| P1-5,6 | 运维 | JSON 日志 + trace_id | `JSONFormatter` + `X-Trace-Id` |
| P1-10 | 安全 | innerHTML XSS 9 处 | `escapeHtml()` 补防 |

### 日志覆盖审计（两批）

| 批次 | 范围 | 改动 |
|------|------|------|
| 第一批（5 项） | 安全路径日志补齐 | `app.js` 全局错误捕获 + `rate_limit.py`/`ownership.py`/`admin_rbac.py` warning 日志 + `admin_auth_router.py` 登录失败记录 |
| 第二批（10 处） | 真吞异常排查 | `order_service.py` 日期解析 warning + `wechat/auth.py` 手机号获取 warning + 前端 7 处静默 catch 加 console.error + 2 处 silent try/catch 加 console.error + `main.py` 全局 handler 增加 path 上下文 |
| 日志配置 | 轮转策略 | `request_log.py` 裸 `FileHandler` → `RotatingFileHandler` 10MB × 30 份 |

### 微信小程序合规审计（3 批 10 项修复）

| 批 | 修复项 | 涉及文件 |
|----|--------|---------|
| 1 | 删 app.js 静默同意 else 分支 + firstDay undefined 崩溃 + 删 store.js.bak + sitemap 精细化 | `app.js`, `checkin.js`, `sitemap.json` |
| 2 | 登录页隐私勾选（双按钮 disabled）+ 押金删 amount + 押金放开 iOS 支付 + observation/official 文案统一 | `login.*`, `api.js`, `deposit.*`, `observation.*`, `official.*` |
| 3 | 完整 9 节隐私政策写入 privacy-policy.wxml | `privacy-policy.wxml` |

### 全量终审 + 中危修复

| 中危 | 问题 | 修复 |
|------|------|------|
| #1 | 文件上传魔数校验仅 warn 不拦截 | `validate_file_content`: `raise ValidationError`，删除 `application/octet-stream` 绕过 |
| #2 | 分片上传缺校验 | `save_chunk` 入口加扩展名白名单 + `complete_upload` 合并后 32 字节魔数校验，不通过删文件 |

### 二次审查补丁（3 低危）

| 遗漏 | 修复 |
|------|------|
| pay-button 组件文案未同步 | `pay-button.wxml:10` |
| 弹窗 title "苹果规则限制" → "暂不支持 iOS 开通" | `observation.js`, `official.js` |
| 隐私政策撤回同意权操作路径不明确 | 补充清除小程序数据/联系客服路径 |

### 第三方专家审查交付（`专家意见/`）

3 位专家（架构师 + QA + 产品经理）并行审查 12 维度，产出 4 份可执行交付：

| 文件 | 用途 |
|------|------|
| `专家意见/README.md` | 审查总览、结论、施工顺序、验证清单 |
| `专家意见/P0-修复指南.md` | 2 项资金安全修复（押金假退款 + 退款双重审核），含 before/after 完整代码 |
| `专家意见/P1-修复指南.md` | 17 项并发锁 + API 修复，按统一模板逐项标注文件路径行号 |
| `专家意见/P2-优化建议.md` | 6 项优化 + 3 项系统级改进方向 |

**施工顺序**: P0（1-2h）→ P1 第一部分: 15 项 `with_for_update()` 锁（3-4h）→ P1 第二部分: `response_model` + `get_db`（1h）→ P2 后续

### 全量文件清理

删除 `deliverables/` / `docs/superpowers/` / `docs/compose/` / `specs/` / 5 个 AUDIT_PROMPT_* / `AUDIT_REPORT.md` / `TASK_PLAN.md` 等历史审计产物。保留 `专家意见/` / ARCHITECTURE.md / HANDOFF.md / checkpoint.md / overview.md / DEPLOY_CHECKLIST.md / PRD/ / .ai/context/。

### 安全审计修复 7/7

| # | 修复 | 文件 |
|---|------|------|
| P0-1 | 删 `POST /questions`（越权） | `advancement/router.py:78-86` |
| P0-2 | `GET /enrollments` → `require_perm("activity.enrollment")` | `activity/router.py:65-72` |
| P0-3 | `phone[-6:]` → `secrets.token_urlsafe(12)` | `admin/services/order_service.py:223,266` |
| P0-4 | `POST /checkin` → `require_perm("activity.checkin")` | `activity/router.py:75-82` |
| P1-1 | 移除 DEBUG 跳过支付签名分支 | `order/router.py:112-152` |
| P1-2 | 文件魔数 MIME 检测（warn only） | `upload_service.py:46-66` |
| P1-3 | `rate_limit` 3 处重端点 | `book/search`(30/60s), `bulk-import`(5/60s), `export`(10/60s) |

### PRD 功能

| 功能 | 关键变更 |
|------|---------|
| QR 码 | `profile-card.js:238` 下载 + `profile-card.wxml:72` `<image src="{{qrUrl}}">` + `show-menu-by-longpress` |
| 生词高亮 | `GET /vocabulary/{child_id}/learning-words` 端点 → `reader.js` 文本面板 + 音频驱动翻页 + 分段高亮 + 点击查词 |
| 季度/半年 | `/order/tiers` 补 type=5(¥2700)/type=4(¥1350)；种子补价格；**修复续费重置到期日 bug**（延长而非重置） |
| 权益转让 | ✅ 已验证存在 PENDING + admin review 流 |

### 前端打磨

- `buildSegments` 正则增加 Unicode 弯引号 \u2018\u2019 支持 + 归一化
- 文本面板增加空内容兜底提示

### 性能 N+1 修复（19 处）

v5 原有 8 处：

| # | 文件 | 模式 | 修复方式 |
|---|------|------|---------|
| 1 | bookshelf/repository.py:38 | 书架 e.book 懒加载 | `joinedload(Bookshelf.book)` |
| 2 | bookshelf/repository.py:70 | 收藏 f.book 懒加载 | `joinedload(Favorites.book)` |
| 3 | advancement/repository.py:88 | 成就 ca.achievement 懒加载 | `joinedload(ChildAchievement.achievement)` |
| 4 | advancement/service.py:170 | submit_answers 逐题查 QuestionBank | 批量 `QuestionBank.id.in_(qids)` |
| 5 | activity/service.py:194 | get_enrollments 逐人查 Child+User | 批量 `Child.id.in_()` + `User.id.in_()` |
| 6 | activity/service.py:221 | batch_checkin 逐人查报名 | `ActivityEnrollment.child_id.in_()` |
| 7 | activity/service.py:308,329 | cancel_activity 逐人查 Child | 批量 `Child.id.in_()` 预加载 |
| 8 | report/service.py:429 | get_trend 逐天聚合 | 单次 `GROUP BY func.date(start_time)` |

新增 11 处：

| # | 文件 | 模式 | 修复方式 |
|---|------|------|---------|
| 9 | message_service.py:185-198 | 双重 N+1（Child+Book） | 批量 `id.in_()` 预加载 |
| 10 | benefit_transfer_service.py:32-35 | 每次循环 3 个独立查询 | 批量 `id.in_()` + dict 映射 |
| 11 | profile/service.py:51-56 | Achievement 逐条查询 | 批量 `id.in_()` 加载 |
| 12 | user_service.py:148-158 | list_children 查 BorrowRecord | `GROUP BY` 一次性聚合 |
| 13 | user_service.py:196-206 | search_children 查 BorrowRecord | `GROUP BY` 一次性聚合 |
| 14 | borrow_service.py:206-228 | `_child_to_dict` 逐个查计数 | 批量 `_batch_borrow_counts()` |
| 15 | book_service.py:111-122 | bulk_import_books 逐条查 ISBN | 一次性 `ISBN.in_()` |
| 16 | book_service.py:152-159 | bulk_import_questions 逐条查 ISBN | 一次性 `ISBN.in_()` |
| 17 | book_service.py:200-210 | search_questions_by_book | `QuestionBank.book_id.in_()` |
| 18 | book_service.py:258-262 | batch_generate_copies 逐条查条码 | 一次性 `barcode.in_()` |
| 19 | report/service.py:141-148 | generate_due_reports | `ObservationReport.child_id.in_()` |

### SMS SDK

| 文件 | 说明 |
|------|------|
| `backend/integrations/sms/tencent.py` | 腾讯云 SDK（`tencentcloud-sdk-python`），`asyncio.to_thread` 包装，凭据缺失 fallback 到 mock |
| `backend/integrations/sms/aliyun.py` | 阿里云 SDK（`alibabacloud-dysmsapi20170525`），`asyncio.to_thread` 包装 |
| `requirements.txt:36-39` | SDK 依赖（注释状态，部署时取消注释） |

两个 SDK 均需真实凭据才能生产使用。`try/except ImportError` 兜底避免缺失 SDK 时崩溃。

### 生产就绪

- `.env`: `DEBUG=false` + 真实 `SECRET_KEY` + `MOCK_SMS=true` + 补齐 36 变量
- 启动时 `MOCK_SMS` warning 日志（`main.py:68-70`）
- 生产模式启动 ✅（health 200 OK, 14 定时任务）

### 测试覆盖

| 文件 | 新增 |
|------|------|
| `tests/unit/test_admin_services.py` | 10 个测试（批量导入去重、借阅计数批量加载、逾期提醒批量加载、权益转让列表等） |
| `tests/unit/test_profile.py` | `test_get_profile_multiple_achievements_batch` 成就批量加载测试 |

---

## 四、关键文件索引

### 后端核心

| 文件 | 说明 |
|------|------|
| `backend/config.py` | 36 env vars, SECRET_KEY 守卫（`DEBUG=false` 时检查） |
| `backend/database.py` | `echo=settings.DEBUG` 控制 SQL 日志 |
| `backend/common/gateways/payment/mock.py:99-100` | Mock 支付网关 `verify_callback_signature` 始终 True |
| `backend/common/gateways/sms/` | Mock SMS 网关 |
| `backend/integrations/sms/tencent.py` | 腾讯云 SMS 网关（已实现） |
| `backend/integrations/sms/aliyun.py` | 阿里云 SMS 网关（已实现） |
| `backend/common/distributed_lock.py` | Redis 分布式锁 + `ConnectionError` → `yield True` fallback |
| `backend/common/config_service.py` | 系统配置服务（TTL 缓存） |
| `backend/middleware/rate_limit.py` | 内存滑动窗口限流（单 worker 适用） |

### 最近改动

| 文件 | 改动 |
|------|------|
| `frontend/pages/reading-pkg/reader/reader.js` | 文本面板 + 音频翻页 + 分段高亮 + 点击查词 + 弯引号支持 |
| `frontend/pages/reading-pkg/reader/reader.wxml` | `<text>` 分段渲染 + `onVocabTap` + 空内容兜底 |
| `frontend/pages/member-pkg/profile-card/profile-card.js` | QR 码下载→`setData({qrUrl})` |
| `backend/domain/vocabulary/router.py:81-88` | `GET /{child_id}/learning-words` |
| `backend/domain/order/router.py:77-99` | 季度/半年 Tier 加入 |
| `backend/events/order_handlers.py:51-65` | 续费延长到期日（非重置） |
| `backend/integrations/sms/tencent.py` | 腾讯云 SMS 网关实现 |
| `backend/integrations/sms/aliyun.py` | 阿里云 SMS 网关实现 |
| `tests/unit/test_admin_services.py` | 新增 10 个管理端服务测试 |
| `backend/.env` | 生产配置（DEBUG=false + 真实 SECRET_KEY） |

---

## 五、验证命令

```bash
venv/bin/ruff check backend/ tests/          # 0 errors ✅
venv/bin/python -m pytest tests/ -x -q       # 175 passed, 4 skipped ✅
venv/bin/python -m behave features/ -q       # 138 scenarios / 970 steps ✅
MOCK_PAYMENT=true MOCK_SMS=true DEBUG=true venv/bin/python scripts/integration_test.py  # 53/53 ✅
venv/bin/python -m alembic check             # No new upgrade operations ✅
venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8002  # 生产模式启动 ✅
```

### SMS SDK 导入验证

```bash
PYTHONPATH=. venv/bin/python -c "from backend.integrations.sms.tencent import TencentSmsGateway; print('OK:', TencentSmsGateway.__name__)"
PYTHONPATH=. venv/bin/python -c "from backend.integrations.sms.aliyun import AliyunSmsGateway; print('OK:', AliyunSmsGateway.__name__)"
```

---

## 六、已知未决项

### P0 — 提审前必须处理（3 项，需外部输入）

| # | 项 | 阻塞原因 | 处理者 |
|---|----|---------|--------|
| T1 | 替换 appid 占位符 | `project.config.json` 中 `wx0000000000000000` | 运营（从微信公众平台获取） |
| T2 | 补全服务协议页 | `service-agreement.wxml` 仅含占位文本 | 法务/运营 |
| T3 | 填写隐私政策运营主体 | `privacy-policy.wxml:16` 公司全称待补充 | 运营（与认证主体一致） |

### P1 — 上线前可完成

| 项 | 阻塞原因 | 处理时机 |
|----|---------|---------|
| iconfont woff2 文件 | 需从 iconfont.cn 下载真实字体，当前 @font-face 已注释 | 上线前（纯打包操作，5 分钟）|

### 非阻塞

| 项 | 阻塞原因 | 处理时机 |
|----|---------|---------|
| 微信支付真实配置 | 无商户号/appid/证书 | 有真实凭证后 |
| SMS SDK 真实凭据 | 需签名审批 + 腾讯云/阿里云密钥 | 生产部署前 |
| 证书自动轮换 | pay_v3.py:99 TODO | 上线前 |
| Docker 构建 | 本地无 Docker | staging 环境 |
| 语音评测（16.4） | 标注"后续版本" | 未来迭代 |
| 性能审计剩余项 | 需 SQLALCHEMY_ECHO 证据 | 有 SQL 日志后 |

---

## 七、CLAUD.md 宪法速查

- **红线**: iOS 禁 wx.requestPayment、金额禁 float、归属禁手动写、库存禁无锁
- **分层**: Router(参数/DI) → Service(业务/事务) → Repository(数据) → Model(ORM)
- **样式禁令**: 禁 oklch()、aspect-ratio、backdrop-filter、translateY(-50%)、position:fixed 缺 box-sizing
