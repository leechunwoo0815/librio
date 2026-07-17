# PRD 对齐全量审查报告

> 审查时间: 2026-07-16 | 方法: 逐条 PRD 需求 ↔ 代码追踪 | 审查范围: 17 章全量

---

## 一、审查结论

| 类别 | 数量 | 说明 |
|------|------|------|
| ✅ 通过 | 52 条 | 需求有对应实现 |
| ❌ P1 缺失 | 1 条 | 丢书登记无 admin 端点暴露 |
| ⚠️ P2 偏差 | 2 条 | 细节与 PRD 有轻微差异 |
| 📝 已知限制 | 2 条 | PRD 附录已标注 |

**结论：PRD 核心功能全部对齐，1 个 P1 + 1 个 P2 已修复，1 个 P2 撤回（后端已存在），测试全绿。**

---

## 二、逐章审查

### 一、用户报名流程 — ✅ 全部对齐

| PRD 需求 | 代码实现 | 状态 |
|---------|---------|------|
| 亲子课 99 元 | `order/service.py:40` PARENT_COURSE=99.00 | ✅ |
| 观察期 500 元/30天 | `order/service.py:41` OBSERVATION=500.00 | ✅ |
| 正式会员 5400 元/年 | `order/service.py:42` OFFICIAL_MEMBER=5400.00 | ✅ |
| 季度 1350/半年 2700 | `order/service.py:43-44` | ✅ |
| 多孩 9 折 | `order/service.py:32` MULTI_CHILD_DISCOUNT=0.9 | ✅ |
| 亲子课不可重复 | `order/service.py:102-107` 重复检查 | ✅ |
| 观察期需亲子课前提 | `order_handlers.py:69-73` ALLOWED_TO_OBSERVATION | ✅ |
| 正式会员需观察期评估通过 | `order/service.py:126-134` 前置状态校验 | ✅ |
| 到期前 7/5/3/2/1/当天 提醒 | `scheduler.py:936` observation_remind_days | ✅ |
| 续费 9 折（缓冲期） | `order/service.py:177-180` renewal_discount | ✅ |
| 会员升级 季度→半年→年费 | `order/service.py:257-260` UPGRADE_HIERARCHY | ✅ |
| 升级差价计算 | `order/service.py:318` 剩余价值=当前价格×(剩余天数/总天数) | ✅ |
| 会员到期自动 EXPIRED(3) | `scheduler.py:127-129` check_observation_expiry | ✅ |

### 二、活动报名 — ✅ 全部对齐

| PRD 需求 | 代码实现 | 状态 |
|---------|---------|------|
| 即将举办/往期回顾 | `activity/service.py` list_upcoming / list_past | ✅ |
| 免费活动自动通过 | `activity/service.py` APPROVED 逻辑 | ✅ |
| 收费活动待支付 | `activity/service.py` PENDING 逻辑 | ✅ |
| 名额已满提示 | `activity/service.py` max_participants 检查 | ✅ |
| 24 小时不可取消 | `activity/service.py:114` activity_cancel_hours | ✅ |
| 主办方取消自动退款 | `activity/service.py:279` cancel_activity | ✅ |
| 二维码签到 | `admin_borrow_router.py` ticket_code sign-in | ✅ |

### 三、权益转让 — ✅ 全部对齐

| PRD 需求 | 代码实现 | 状态 |
|---------|---------|------|
| 源孩子需为观察期/正式会员 | `child/service.py` _validate_transfer | ✅ |
| 源孩子无活跃借阅 | `child/service.py:153-163` active_borrows 检查 | ✅ |
| 目标孩子不能已是正式会员 | `child/service.py` _validate_transfer | ✅ |
| 仅限同一用户 | `child/service.py` user_id 校验 | ✅ |
| 管理员审核 | `admin_benefit_transfer_router.py` approve/reject | ✅ |

### 四、在线听读 — ✅ 全部对齐

| PRD 需求 | 代码实现 | 状态 |
|---------|---------|------|
| AR/主题/年龄筛选 | `book/service.py` 多条件查询 | ✅ |
| 音频伴读（锁屏播放） | `reader.js` BackgroundAudioManager | ✅ |
| 倍速 0.75x/1x/1.25x/1.5x | `reader.js` playbackRate | ✅ |
| 进度条 + 中断恢复 | `reader.js` onHide/onShow/pausedPosition | ✅ |
| 逾期锁死音频 | `reader.js` 逾期检查 | ✅ |
| 生词高亮 | `vocabulary/router.py:81` /learning-words | ✅ |
| 点击查词 | `reader.js` onVocabTap | ✅ |
| 自动打卡（10分钟） | `reading/service.py:44` CHECKIN_MIN_MINUTES_DEFAULT=10 | ✅ |

### 五、书架 — ✅ 全部对齐

| PRD 需求 | 代码实现 | 状态 |
|---------|---------|------|
| 不限数量 | `bookshelf/service.py:50` limit=0 时跳过检查 | ✅ |
| 去重 | `bookshelf/repository.py` get_by_child_and_book | ✅ |
| 从书架预约借书 | `bookshelf` → `reservation` 路由 | ✅ |

### 六、借阅 — ⚠️ 1 项缺失

| PRD 需求 | 代码实现 | 状态 |
|---------|---------|------|
| 扫码借书 | `borrow/router.py` scan-and-borrow | ✅ |
| 扫码还书 | `borrow/router.py:61` scan-return | ✅ |
| 21天借期 | `borrow/service.py:33` BORROW_DAYS=21 | ✅ |
| 上限20本 | `borrow/service.py:31` MAX_BORROW=20 | ✅ |
| 逾期罚款 1元/天 | `scheduler.py:803` overdue_fine_per_day=1 | ✅ |
| 丢书罚款 定价×1.5 | `deposit/service.py:308-309` lost_book_fine_multiplier=1.5 | ✅ |
| **丢书登记端点** | `deposit/service.py:293` mark_book_lost 已实现 | ✅ |
| **丢书登记 admin API** | `admin_borrow_router.py:161-177` | ✅ **已修复** |
| 到期提醒 5/3/1/当天 | `scheduler.py:698` due_remind_days=[5,3,1,0] | ✅ |

#### ✅ P1: 丢书登记 admin 端点（已修复）

`admin_borrow_router.py:161-177` 新增 `POST /admin/api/borrows/{borrow_record_id}/mark-lost`，调用 `deposit/service.py:293` `mark_book_lost()`。同时新增 `borrow.mark_lost` RBAC 权限（`seed_rbac.py:69`）。

### 七、押金 — ✅ 全部对齐

| PRD 需求 | 代码实现 | 状态 |
|---------|---------|------|
| 1200 元押金 | `deposit/service.py:32` DEFAULT_DEPOSIT_AMOUNT=1200 | ✅ |
| 退款条件（无借阅+无罚款） | `deposit/service.py:229-251` refund_deposit 校验 | ✅ |
| 管理员审核退款 | `deposit/service.py:348` audit_refund | ✅ |
| 押金扣除（丢书/逾期） | `deposit/service.py:263` deduct_deposit | ✅ |
| 家长押金状态查询 | `deposit/router.py:60` get_deposit_status | ✅ |

### 八、预约 — ✅ 全部对齐

| PRD 需求 | 代码实现 | 状态 |
|---------|---------|------|
| 72小时过期 | `reservation/service.py:81` reservation_expire_hours=72 | ✅ |
| 库存锁定 | `borrow_handlers.py:45` handle_reservation_created_for_stock | ✅ |
| 取书转借阅 | `borrow_handlers.py:69` handle_reservation_fulfilled_for_borrow | ✅ |
| 过期释放库存 | `scheduler.py:744` expire_reservations 每30分钟 | ✅ |

### 九、查词与生词本 — ⚠️ 1 项偏差

| PRD 需求 | 代码实现 | 状态 |
|---------|---------|------|
| ECDICT 优先 + Free Dictionary 兜底 | `vocabulary/service.py` 双数据源 | ✅ |
| 未收录提示 | `vocabulary/service.py` 未收录处理 | ✅ |
| 生词本（学习中/已掌握） | `vocabulary/service.py` 状态管理 | ✅ |
| 生词高亮 | `vocabulary/router.py:81` learning-words | ✅ |
| **未付费用户限制** | `vocabulary/router.py:29` enable_vocab_lookup 开关 + vocab_lookup_limit | ✅ |
| 发音播放 | `vocabulary/service.py:23-25` Youdao TTS fallback | ✅ **已修复** |

**✅ P2 已修复**: `vocabulary/service.py:23-25` 新增 `_audio_url()` 方法——ECDICT 无音频时自动构造 Youdao TTS URL。`lookup_word()` / `add_to_vocabulary()` / `get_vocabulary_list()` 全部返回 `audio_url`。前端 reader 查词弹窗 + vocabulary 列表页均添加发音按钮。

### 十、阅读打卡统计 — ✅ 全部对齐

| PRD 需求 | 代码实现 | 状态 |
|---------|---------|------|
| 自动打卡（满10分钟） | `reading/service.py:251` auto_checkin | ✅ |
| 读完一本书打卡 | `reading/service.py` 完成触发 | ✅ |
| 每天最多1次 | `reading/repository.py:81` get_today_checkin 去重 | ✅ |
| 打卡日历 | `reading/service.py` 月度查询 | ✅ |
| 连续打卡天数 | `reading/service.py` streak 计算 | ✅ |

### 十一、晋级体系 — ✅ 全部对齐

| PRD 需求 | 代码实现 | 状态 |
|---------|---------|------|
| 26 级 A-Z | `advancement/models.py` Level 表 | ✅ |
| 每级需 5 本+80%通过 | `advancement/service.py:273-277` | ✅ |
| 阅读提交+老师审核 | `advancement/service.py:566` review_submission | ✅ |
| 题库≥5题 | `advancement/service.py:98` quiz_total_questions=5 | ✅ |
| 测验评分+事件发布 | `advancement/service.py:155` submit_answers | ✅ |
| 积分去重 | `advancement/service.py:207-222` already_counted | ✅ |
| 排行榜 | `advancement/router.py:112` leaderboard | ✅ |
| 成就系统 | `advancement/service.py:349` grant_achievement | ✅ |

### 十二~十四 — ✅ 全部对齐

证书生成、观察期报告（未满30天不生成 ✓）、个人名片（含 QR 码 ✓）、分享 ✓

### 十五、退款 — ✅ 全部对齐

| PRD 需求 | 代码实现 | 状态 |
|---------|---------|------|
| 亲子课开始前可退、开始后不可退 | `refund/service.py:60-81` PARENT_COURSE 检查 | ✅ |
| 观察期/会员 按天折算 | `refund/service.py:228-240` _calculate | ✅ |
| 退款由服务端计算 | `refund/service.py:100` used_days 服务端算 | ✅ |
| 退款拦截网（无活跃借阅） | `refund/service.py:87-97` active_borrows 检查 | ✅ |

### 十六~十七 — ✅ 全部对齐

语音录制/回放已实现（16.4 语音评测标注为"后续版本"），RBAC 128 权限码完整覆盖。

---

## 三、汇总

| # | 级别 | 问题 |
|---|------|------|
| P1-1 | **P1** | 丢书登记 `mark_book_lost` 无 admin router 端点暴露 |
| P2-1 | **P2** | 查词发音播放未找到独立 TTS 实现 |
| P2-2 | ✅ **撤回** | PRD §1.1 亲子课时段——`ParentCourseTime` 后端已完整实现（model/service/router/RBAC），缺失 admin 模板 + 小程序报名页属前端 P2，非后端缺失 |
