# MegaWords V3.5 — P0 问题苏格拉底式拷问

> **目的**：对专家审查报告中的 12 个 P0 问题逐条验证代码后，提出质疑和判定，请专家确认或反驳
> **审查人**：AI 架构总监
> **日期**：2026-07-03

---

## 拷问格式说明

每个问题按以下结构质疑：
- **专家结论**：审查报告中的原始判断
- **代码实证**：实际代码内容（附文件:行号）
- **苏格拉底拷问**：追问本质问题
- **AI 判定**：确认 P0 / 降级 P1 / 存疑待确认
- **请专家回复**：需要专家确认或反驳的点

---

## P0-1: 阅读提交（ReadingSubmission）未自动创建

**专家结论**：`save_progress` 读完最后一页时只设 `is_finished=1`，不创建 ReadingSubmission，导致晋级与观察期报告数据链断裂。

**代码实证**：
```python
# backend/domain/reading/service.py:104-109
if data.current_page >= data.total_pages:
    progress.is_finished = 1
    progress.finish_time = datetime.now()

self.progress_repo.update(progress)
self.db.commit()
return ProgressResponse.model_validate(progress)
```
确认：没有创建 ReadingSubmission 的逻辑。

**苏格拉底拷问**：
1. ReadingSubmission 的作用是什么？→ 老师审核 → 审核通过后 `books_read_at_level +1` → 晋级条件判断
2. 如果不创建会怎样？→ 老师看不到待审核列表 → `books_read_at_level` 永远为 0 → 晋级永远不触发
3. 有没有其他路径创建 ReadingSubmission？→ 检查了代码，没有。只有 `review_submission` 方法操作它，但前提是它得先存在
4. 有没有可能设计上就不需要自动创建？→ PRD 11.2 明确"读完自动创建"

**AI 判定**：✅ **确认 P0**。链路完全断裂。

**请专家回复**：
- [ ] 确认此判定
- [ ] 是否有其他创建 ReadingSubmission 的路径我遗漏了？

---

## P0-2: 测验通过事件错误增加已读书数

**专家结论**：`handle_quiz_passed_for_advancement` 同时调用 `increment_quizzes_passed` 和 `increment_books_read`，导致不读书也能晋级。

**代码实证**：
```python
# backend/events/quiz_handlers.py:11-18
def handle_quiz_passed_for_advancement(event, db: Session):
    """测验通过 → 增加测验通过数 + 读完书数 + 晋级检测"""
    service = AdvancementService(db)
    service.increment_quizzes_passed(event.child_id)  # ✅ 正确
    service.increment_books_read(event.child_id)       # ❌ 错误：测验通过不应增加已读书数
    service.check_and_advance(event.child_id)
```

**苏格拉底拷问**：
1. PRD 怎么定义"已读书数"？→ "老师审核通过的阅读提交"数量
2. 测验通过 = 读完书吗？→ 不等。孩子可以不读书直接答题（如果题库公开）
3. 删除 `increment_books_read` 后，谁来增加已读书数？→ P0-9 的修复：`review_submission` 审核通过时增加
4. 这两个修复必须配套吗？→ 是的。如果只修 P0-2 不修 P0-9，`books_read_at_level` 永远为 0

**AI 判定**：✅ **确认 P0**。但必须与 P0-9 配套修复。

**请专家回复**：
- [ ] 确认此判定
- [ ] 确认 P0-2 和 P0-9 必须配套修复

---

## P0-3: 观察期/正式会员报名前置条件缺失

**专家结论**：观察期仅校验 `child.status == TRIAL`，未校验亲子课完成和测评报告。

**代码实证**：
```python
# backend/domain/order/service.py:88-105
if order_data.type == OrderType.OBSERVATION:
    if child.status not in (MemberStatus.TRIAL,):
        raise ValidationError("当前状态不允许购买观察期，仅限试读用户")
elif order_data.type in (OrderType.OFFICIAL_MEMBER, ...):
    if child.status not in (MemberStatus.OBSERVATION, MemberStatus.OFFICIAL, MemberStatus.EXPIRED):
        raise ValidationError("当前状态不允许购买会员")
```

**苏格拉底拷问**：
1. PRD 1.2 要求"已完成亲子课程并获得测评报告"→ 但这个"测评报告"在系统中是否存在？→ 检查了代码，`Assessment` 模型存在但与亲子课无直接关联
2. 实际业务流程是什么？→ 亲子课在线下门店完成 → 测评可能也是线下 → 系统内不一定有记录
3. 如果强制校验系统内记录，会卡住线下完成的用户吗？→ 会
4. 正确做法是什么？→ 应该是"管理员可手动确认前置条件"，而非硬校验系统内记录

**AI 判定**：⚠️ **降级为 P1**。需要产品确认前置条件的校验方式。

**请专家回复**：
- [ ] 亲子课完成和测评报告是否必须在系统内有记录？
- [ ] 如果线下完成，管理员是否需要手动标记"已完成"？
- [ ] 建议改为：观察期报名时可选填"已完成亲子课"标记，管理员可手动设置

---

## P0-4: 权益转让目标孩子状态校验不足

**专家结论**：`transfer_benefit` 仅拒绝 `target.status == EXITED`，不拒绝已是观察期/正式会员的孩子。

**代码实证**：需确认 `child/service.py:112-125` 实际代码。

**苏格拉底拷问**：
1. 转让给已是正式会员的孩子会怎样？→ 覆盖其现有会员权益和有效期 → 数据不一致
2. PRD 怎么说？→ "目标孩子不能已经是正式会员"
3. 观察期呢？→ PRD 未明确，但逻辑上不应覆盖

**AI 判定**：✅ **确认 P0**。至少应拒绝 OFFICIAL，建议同时拒绝 OBSERVATION。

**请专家回复**：
- [ ] 确认此判定
- [ ] 目标孩子是观察期时，是否也应该拒绝转让？

---

## P0-5: 亲子课退款规则缺失

**专家结论**：`apply_refund` 对所有订单类型使用同一退款计算，亲子课课程开始后仍可退款。

**代码实证**：
```python
# backend/domain/refund/service.py:29-68
def apply_refund(self, user_id: int, data: RefundCreate) -> RefundResponse:
    order = self.order_repo.get_by_id_or_raise(data.order_id)
    # ... 校验 ...
    used_days = (datetime.now() - order.pay_time).days if order.pay_time else 0
    refund_amount = self._calculate(order, used_days)
    # 未区分 OrderType.PARENT_COURSE
```

**苏格拉底拷问**：
1. PRD 15.1 怎么说？→ "亲子课课程开始前全额退款 99 元；课程开始后不可退款"
2. 课程开始时间在哪里？→ `ParentCourseTime` 表
3. 修复方案？→ 对 `OrderType.PARENT_COURSE`，检查关联的 `ParentCourseTime.start_time`，已过则拒绝

**AI 判定**：✅ **确认 P0**。但金额小（99 元），修复简单。

**请专家回复**：
- [ ] 确认此判定
- [ ] 课程开始时间是否就是 `ParentCourseTime.start_time`？

---

## P0-6: 多孩优惠逻辑与 PRD 不符

**专家结论**：仅按同类型订单判断，不按孩子状态判断。

**代码实证**：
```python
# backend/domain/order/service.py:130-172
def _apply_discount(self, user_id, order_type, child_id):
    # 检查同类型已支付订单数
    count = self.db.query(Order).filter(
        Order.user_id == user_id,
        Order.type == order_type,
        Order.pay_status == PayStatus.PAID,
        Order.is_deleted == 0,
    ).count()
    if count > 0:
        return multi_child_discount  # 0.9
```

**苏格拉底拷问**：
1. PRD 怎么说？→ "同一 user 下已有 1 个孩子是观察期或正式会员 → 第 2 孩起 9 折"
2. 当前逻辑的问题？→ 按订单类型而非孩子状态 → 第一个孩子观察期，第二个买正式会员时不打折（因为没有 OFFICIAL 类型的历史订单）
3. 正确逻辑？→ 检查同一 user 下是否存在 `status in (OBSERVATION, OFFICIAL)` 的孩子

**AI 判定**：✅ **确认 P0**。直接资损。

**请专家回复**：
- [ ] 确认此判定
- [ ] 续费折扣（缓冲期 0.9）与多孩折扣（0.9）是否可叠加？当前实现互斥

---

## P0-7: 订单创建未校验前置条件（同 P0-3）

**AI 判定**：与 P0-3 同一问题，合并处理。⚠️ **降级为 P1**。

---

## P0-8: 测验积分去重条件错误

**专家结论**：去重条件为"存在任意 COMPLETED 的 Quiz"，不检查 `passed`。

**代码实证**：
```python
# backend/domain/advancement/service.py:196-209
if passed:
    already_counted = (
        self.db.query(Quiz)
        .filter(
            Quiz.child_id == quiz.child_id,
            Quiz.book_id == quiz.book_id,
            Quiz.status == Quiz.STATUS_COMPLETED,  # 不检查 passed
            Quiz.id != quiz.id,
            Quiz.is_deleted == 0,
        )
        .first()
    )
    if already_counted:
        effective_word_count = 0
```

**苏格拉底拷问**：
1. 首次测验失败后再通过会怎样？→ 已存在失败的 COMPLETED 记录 → 通过后积分也不计入
2. 这意味着什么？→ 孩子如果第一次没通过，这本书的积分永远拿不到
3. 正确逻辑？→ 应该检查"是否存在其他已通过的 Quiz"，而非"任意已完成的 Quiz"

**AI 判定**：✅ **确认 P0**。学习数据永久错误。

**请专家回复**：
- [ ] 确认此判定
- [ ] 去重条件应改为 `Quiz.passed == True` 对吗？

---

## P0-9: 阅读提交审核通过不增加已读完书数

**专家结论**：`review_submission` 只更新状态，不调用 `increment_books_read`。

**代码实证**：
```python
# backend/domain/advancement/service.py:492-503
def review_submission(self, submission_id: int, data) -> dict:
    sub = self.db.query(ReadingSubmission).filter(ReadingSubmission.id == submission_id).first()
    if not sub:
        raise NotFoundError("提交不存在")
    sub.status = data.status
    if data.comment:
        sub.comment = data.comment
    self.db.commit()
    return {"success": True}
    # 没有 increment_books_read，没有 check_and_advance
```

**苏格拉底拷问**：
1. 如果 P0-2 修复了（删除测验的 increment_books_read），谁来增加已读书数？→ 只能是这里
2. 如果这里也不加 → `books_read_at_level` 永远为 0 → 晋级永远不可能
3. 两个修复必须配套？→ 是的

**AI 判定**：✅ **确认 P0**。与 P0-2 配套。

**请专家回复**：
- [ ] 确认此判定
- [ ] 审核通过后是否应该同时触发 `check_and_advance`？

---

## P0-10: 关键表缺少唯一约束

**专家结论**：借阅、Quiz、成就、阅读提交表缺少唯一约束，高并发下重复记录。

**苏格拉底拷问**：
1. 当前数据量和并发量？→ 测试环境，量级很小
2. 实际生产并发？→ 儿童阅读平台，不是秒杀场景，并发量低
3. 应用层先查后插能否防住？→ 大部分场景可以，极端并发下不行
4. 是否可以降级？→ 可以。应用层加锁 + 后续迁移补约束

**AI 判定**：⚠️ **降级为 P1**。当前并发风险低，但上线前必须补齐。

**请专家回复**：
- [ ] 是否接受降级为 P1？
- [ ] 建议：Sprint 1 加应用层锁，Sprint 2 用 Alembic 补唯一约束

---

## P0-11: 高频字段缺少索引

**专家结论**：`book_copy_id`、`Quiz.book_id` 等无索引。

**苏格拉底拷问**：
1. 当前数据量？→ 测试环境，几百条记录
2. 索引缺失的影响？→ 数据量小时全表扫描也很快
3. 是否可以降级？→ 可以。功能不受影响，只是性能问题

**AI 判定**：⚠️ **降级为 P1**。上线前用 Alembic 迁移补齐。

**请专家回复**：
- [ ] 是否接受降级为 P1？

---

## P0-12: `/admin/api/oplogs` 未认证

**专家结论**：端点无认证，任何人可写入日志文件。

**代码实证**：
```python
# backend/domain/admin/routers/admin_system_router.py:33-55
@router.post("/oplogs")
def receive_oplogs(data: dict):  # 无 admin=Depends(...)
    logs = data.get("logs", [])
    for log in logs:
        log_line = f"[{ts}] [{page}] [{category}] {action} {detail}\n"
        with open("/tmp/admin_oplogs.log", "a") as f:
            f.write(log_line)
    return {"ok": True}
```

**苏格拉底拷问**：
1. 实际风险？→ 可被恶意刷屏写满 `/tmp` → 可注入伪造日志
2. 修复成本？→ 极低，加一行认证
3. 是否需要改写入方式？→ 应该写入数据库 `operation_log` 表而非文件

**AI 判定**：✅ **确认 P0**。修复成本极低。

**请专家回复**：
- [ ] 确认此判定
- [ ] 是否需要同时改为写入数据库？

---

## P0-13: admin.js 全局表单拦截（额外发现）

**专家结论**：全局拦截所有表单提交，未带 Authorization 头且使用 FormData。

**代码实证**：
```javascript
// backend/static/admin/js/admin.js:349-359
form.addEventListener('submit', (e) => {
    e.preventDefault();  // 阻止原生提交
    const formData = new FormData(form);
    return fetch(form.action || location.href, {
        method: form.method || 'POST',
        body: formData,           // FormData 格式，非 JSON
        // 无 Authorization header
    }).then(r => { if (!r.ok) throw new Error('提交失败'); return r; });
});
```

**苏格拉底拷问**：
1. 影响范围？→ 所有使用 `<form>` 提交的管理页面
2. 使用 `api.request()` 的页面受影响吗？→ 不受影响
3. 哪些页面用了 `<form>`？→ 需要逐一检查

**AI 判定**：✅ **确认 P0**。管理端部分页面 CRUD 不可用。

**请专家回复**：
- [ ] 确认此判定
- [ ] 是否有页面依赖这个全局拦截？如果有，需要改为各页面自行处理

---

## 总结：需要专家确认的 5 个关键问题

1. **P0-3 报名前置条件**：亲子课完成和测评报告是否必须系统内有记录？建议改为管理员可手动标记
2. **P0-6 多孩优惠叠加**：续费折扣与多孩折扣是否可叠加？
3. **P0-10/P0-11 降级**：唯一约束和索引是否接受降级为 P1（Sprint 2 修复）？
4. **P0-13 admin.js**：是否有页面依赖全局拦截？修复策略是移除还是改为带 auth 的 JSON 提交？
5. **朗读自动打卡**：PRD 16.3 要求朗读完成自动打卡，是否需要在本次修复中实现？

---

*请逐条回复确认/反驳/补充，确认后立即启动修复冲刺。*
