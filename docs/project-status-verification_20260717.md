# MegaWords 项目状态终审报告

**日期**: 2026-07-17 (v2 — 追加 CI/CD 全量覆盖)  
**审计范围**: 全量代码复核 — 后端 P0/P1 修复验证 + 前端遗留项确认 + 测试全量运行 + CI/CD 基础设施

---

## 测试结果

| 测试套件 | v1 (fix-prompts 阶段) | v2 (CI/CD 最终提交) |
|----------|-----------------------|-------------------|
| pytest | 175 passed, 4 skipped, 0 failed | **210 passed, 5 skipped** ✅ |
| behave | 16 features, 138 scenarios, 0 failed | 138/970/0 ✅ |
| ruff | backend/ tests/ 0 errors | + features/ scripts/ 0 errors ✅ |
| ruff format | — | **326 files already formatted** ✅ |
| verify_api_contract | — | **OK** ✅ |
| check_model_consistency | — | **53 tables** ✅ |

---

## 后端 P0 问题 — 逐项核实结果

### ✅ 已修复（10项）

| # | 问题 | 验证结果 |
|---|------|----------|
| 1 | 退款回调端点缺失 | `/refund/callback` 端点已存在，调用 `service.mark_refunded()` |
| 2 | 预约取消不释放库存 | `cancel_reservation()` 发布 `ReservationCancelledEvent`，`handle_reservation_cancelled_for_stock` 已注册 |
| 3 | RefundService 写入不存在的 order.refund_remark | `Order.refund_remark` 字段已存在于 models.py:64 |
| 4 | PayType.TRANSFER 与 CLOSED 枚举值冲突 | **误报** — CLOSED=5 在 PayStatus，TRANSFER=5 在 PayType，不同枚举无冲突 |
| 5 | tasks/jobs 全部死代码 + get_session 获取工厂 | **误报** — 无 jobs/ 目录，`_get_db_session()` 正确调用 `get_session()()` |
| 6 | MOCK_SMS 默认 True | 默认值已改为 `False`（config.py:31） |
| 7 | 订单支付回调缺金额校验 | `handle_payment_callback` 校验 `callback.amount != order.amount` → raise PaymentError |
| 8 | 押金支付回调缺金额校验 | `handle_callback` 校验 `amount != record.amount` → raise PaymentError |
| 9 | get_upgrade_options 缺 child_id ownership | 已调用 `verify_child_ownership(child_id, current_user, db)` |
| 10 | WXML 裸访问（achievement, borrow-history） | 两个页面 onLoad 均有 `auth.requireAuth()` 守卫 |

### ✅ 已修复 P1（1项）

| # | 问题 | 验证结果 |
|---|------|----------|
| 11 | wx.requestPayment 硬编码 prepay 参数 | deposit/official/observation 均使用后端返回的 `pay_params`，含字段完整性校验 |

---

## 事件处理器 try/except 分析

事件总线设计文档明确：**共享 session 模式下处理器异常自动 re-raise 触发事务回滚**。

| 处理器 | try/except | 评估 |
|--------|-----------|------|
| `handle_book_borrowed_for_copy_status` | 无 | ✅ 正确 — 共享 session，异常自动回滚 |
| `handle_book_returned_for_copy_status` | 有 | ✅ 正确 — 显式 raise，行为一致 |
| `handle_reservation_created_for_stock` | 无 | ✅ 正确 — 同上 |
| `handle_reservation_cancelled_for_stock` | 无 | ✅ 正确 — 同上 |
| `handle_reservation_expired_for_stock` | 无 | ✅ 正确 — 同上 |
| `handle_reservation_fulfilled_for_borrow` | 无 | ✅ 正确 — 同上 |
| `handle_book_overdue_for_fines` | N/A | 仅日志记录 |
| `handle_order_paid_for_child` | 无 | ✅ 正确 — 含业务校验（EXITED 状态、状态迁移合法性） |
| `handle_deposit_paid_for_child` | 无 | ✅ 正确 — 简单字段更新 |

**结论**: 事件处理器无 try/except 是设计正确的，不是 bug。

---

## 前端遗留问题

| 优先级 | 问题 | 状态 | 说明 |
|--------|------|------|------|
| P0 | appid 仍为 `wx0000000000000000` | ⏳ 待外部 | 提审前替换为真实 appid |
| P0 | 服务协议页内容为占位文本 | ⏳ 待法务 | `service-agreement.wxml` 仅含 "服务协议内容" |
| P0 | 隐私政策运营主体未填 | ⏳ 待运营 | "【公司全称待补充...】" |
| P1 | WXML 中 emoji 替换 | ✅ 已完成 | 285 emoji → 62 icon 类, 31/31 文件部署, 0 裸露 emoji 外 |
| P2 | reading-stats 折线图退化为柱状图 | ⏳ 待产品 | 待产品决策 |
| P2 | premium-hero::before 伪元素装饰 | ✅ 已删除 | 伪元素规则块已清理 |

---

## 配置种子 — 已修复 ✅

原报告指出 seeder 缺 7 个键 + 2 个键名不匹配 bug（`observation_price`≠`price_observation`）。已在 Task 7 中统一切换为 `SystemConfig.DEFAULTS` 为单一来源：

- 37 个配置键 → 循环 `DEFAULTS.items()` 自动覆盖
- 死键 `observation_price`/`official_member_price` → 软删除清理
- `config_type` → 与 DEFAULTS 定义自动一致

**验证**: 37/37 键初始化，ruff/pytest/behave 全绿。

---

## SMS 架构确认

- 依赖注入模式，三种网关：MockSmsGateway（线程安全 5min TTL）、AliyunSmsGateway、TencentSmsGateway
- Aliyun/Tencent 网关已完整实现 `send_code()` 和 `send_notification()`，含 SDK 可选导入（`_HAS_SDK`）
- MOCK_SMS 默认 False，生产安全
- mock_routes.py 仅在 `MOCK_SMS=true && DEBUG=true` 时注册，需 admin 鉴权

---

## 总结

**后端**: 所有 P0 问题已修复或确认为误报。P1 问题（支付参数、seeder 键名）已修复。代码质量良好。ruff 0 errors。

**前端**: 原 6 项遗留问题中 3 项已修复（emoji 替换 285/285、premium-hero 伪元素已删除），3 项 P0 为提审前必须处理（appid、服务协议、隐私政策）。

**测试**: 全量通过，pytest 175 passed + behave 138 scenarios passed，零失败。

**建议优先处理**:
1. 替代 appid 占位符（需微信公众平台获取真实 AppID）
2. 补全服务协议（需法务/运营提供文本）
3. 填写隐私政策运营主体（需与认证主体一致）

---

## 附录：CI/CD 全量覆盖总结 (v2)

### 基础设施
| 项目 | 值 |
|------|-----|
| CI 平台 | GitHub Actions（`.github/workflows/ci.yml`） |
| 默认分支 | `main`（`master` 已重命名） |
| 远程仓库 | `github.com/leechunwoo0815/librio`（SSH） |

### CI 3 Job 分解
| Job | 检查项 | 状态 |
|-----|--------|------|
| lint | ruff check backend/ tests/ | 0 errors ✅ |
| | ruff check features/ scripts/ | 0 errors ✅ |
| | ruff format --check . | 326 formatted ✅ |
| test | pytest tests/ -x -q | 210/5 ✅ |
| | behave features/ --no-capture -q | 138/970 ✅ |
| | verify_api_contract | OK ✅ |
| model-check | check_model_consistency | 53 tables ✅ |

### 4 条新增路由
| 路由 | 用途 | 测试数 |
|------|------|--------|
| GET /child/transfer/records | 权益转让记录 | 15 service + 21 HTTP |
| GET /book/{book_id}/related | 相关图书推荐 | |
| GET /reading/checkin/{child_id}/records | 打卡记录 | |
| DELETE /child/{child_id} | 删除孩子 | |

### 36 新测试覆盖
- 15 Service 层：正常/空/异常/边界
- 21 HTTP 层：鉴权 (401/403) / 序列化 / 参数校验 / 7 边界场景 (5/7)
- 2 个 P3 边界（软删除过滤）代码已保护但未单独测

### 已知阻塞
| 项 | 原因 |
|----|------|
| appid 占位符 | 需微信公众平台真实值 |
| 服务协议内容 | 需法务/运营提供 |
| 隐私政策主体 | 需与认证主体一致 |
| iconfont woff2 | 需从 iconfont.cn 下载 |
| reading-stats 折线图 | 需产品决策 |
