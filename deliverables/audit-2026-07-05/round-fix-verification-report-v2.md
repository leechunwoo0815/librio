# 本轮修复完成度复核报告（第二版）

> **复核人**：齐活林（交付总监）
> **复核日期**：2026-07-05
> **复核对象**：BaseSchema extra=forbid、路由层 ORM 清零、前端上传路径修复

---

## 总体结论

**本轮修复有实质性进展，但引入了一个全局性回归：BaseSchema 设置 `extra=forbid` 后，大量 Service 返回的 dict 字段与 Response Schema 不匹配，导致多个接口 500。**

- ✅ pytest 100/100
- ✅ behave 138/138
- ✅ 路由层 `db.*` 直接 ORM 操作：0 处
- ✅ 前端上传路径：3/3 已修复
- ✅ BaseSchema 已设置 `extra=forbid`
- ❌ ruff check backend/：**8 个错误**（用户声称 0）
- ❌ formal_test_v2.py：**108/119，11 个失败**（其中 7 个是 500 回归）
- ❌ 多个接口因 ResponseValidationError 返回 500

---

## 已确认修复项

### 1. BaseSchema extra=forbid ✅

`backend/common/base_schema.py:83-87` 已设置：
```python
model_config = ConfigDict(
    from_attributes=True,
    populate_by_name=True,
    extra="forbid",
)
```

所有继承 `BaseSchema` 的 Schema 自动禁止额外字段。

### 2. 路由层 ORM 清零 ✅

精确统计 `db.query/add/commit/refresh/flush/delete/rollback` 直接调用：
- **admin routers 中：0 处**
- 已从 57 处（第一版复核）降至 0

新增 Service 方法确实承担了数据查询职责。

### 3. 前端上传路径修复 ✅

- `booklist.html:430`：`/admin/upload` → `/admin/api/upload`
- `books.html:579`：`/admin/upload/chunk` → `/admin/api/upload/chunk`
- `books.html:602`：`/admin/upload/complete` → `/admin/api/upload/complete`

所有前端管理路径检查：0 处错误路径残留。

---

## 新发现的回归问题

### 1. Response Schema 字段不匹配导致大量 500

**根本原因**：`extra=forbid` 开启后，所有返回 dict 的 Service 方法必须严格匹配 Schema 字段。但大量 Service 返回的 dict 包含 Schema 未定义的字段，导致 `ResponseValidationError` 500。

**受影响接口示例**：

| 接口 | 位置 | 错误 |
|------|------|------|
| `GET /profile/{child_id}` | `profile/service.py:60-74` | 返回 `name`, `english_name`, `age`, `grade`, `total_books_finished`, `total_words_read`, `total_reading_minutes`, `current_streak_days`, `longest_streak_days`, `current_level`, `achievement_count`, `achievements` — `ProfileResponse` 仅定义 `child_id`, `child_name`, `total_books`, `total_words`, `total_minutes`, `current_streak`, `level_name`, `badge_emoji` |
| `GET /advancement/leaderboard` | `advancement/leaderboard_service.py:96-107` | 返回 `books_read`，但 `LeaderboardEntryResponse` 无此字段 |
| `GET /admin/api/config` | `admin_system_router.py` | 500 |
| `GET /admin/api/deposits` | `admin_system_router.py` | 500 |
| `GET /admin/api/reservations` | `admin_system_router.py` | 500 |

**formal_test 失败项**：
- 系统配置：500
- deposits：500
- config：500
- reservations：500
- 排行榜（总）：500
- 名片信息：500
- 端点存在：名片：500

**说明**：这是设置 `extra=forbid` 后必然会暴露的问题。修复方向不是回退 `extra=forbid`，而是**统一让 Service 返回 Pydantic Schema 对象，或严格让返回的 dict 与 Schema 字段一致**。

### 2. ruff 检查 backend/ 仍有 8 个错误

```
F841  admin_advancement_router.py:152  cert 变量未使用
F401  admin_reports_router.py:6  sqlalchemy.func 未使用
F401  admin_reports_router.py:6  sqlalchemy.cast 未使用
...
（共 8 个）
```

用户声称 ruff 0 错误，实际 8 个。

### 3. 测试脚本路径问题仍部分存在

formal_test 中仍有部分 `/admin/dashboard`、`/admin/users` 等路径期望 401/403，但后端实际路由为 `/admin/api/*`，导致 404。虽然数量比上次减少，但仍未完全修复。

---

## 修复建议

### 高优先级（立即修复）

1. **统一 Service 返回类型**：
   - 所有 Service 方法应返回 Pydantic Schema 对象，而不是裸 dict。
   - 如果必须返回 dict，则确保 dict 字段严格匹配 `response_model` 的 Schema。
   - 建议批量扫描所有 `return {` 的 Service 方法，逐一与 Schema 对齐。

2. **修复已知 500 接口**：
   - `profile/service.py` 改为返回 `ProfileResponse` 对象，或修改 Schema 包含所有字段。
   - `advancement/leaderboard_service.py` 移除 `books_read` 字段，或添加到 Schema。
   - `admin_system_router.py` 的 config/deposits/reservations 等接口检查返回字段与 Schema 匹配。

3. **修复 ruff 8 个错误**：
   - 删除未使用变量和导入。

### 中优先级

4. **修复 formal_test_v2.py 管理端路径**：
   - 将无认证测试的 `/admin/dashboard` 等改为 `/admin/api/dashboard`。
   - 场馆列表接口 404 问题需确认后端路由。

5. **全面扫描所有返回 dict 的 Service 方法**：
   - 使用脚本检查所有 `response_model` 与 Service 返回类型的字段一致性。

---

## 结论

本轮修复在架构层面（ORM 下沉、BaseSchema extra=forbid）有重要进步，但 **BaseSchema extra=forbid 引入的全局响应校验回归是当前最大 blocker**。在修复所有 Service 返回类型与 Schema 字段一致性之前，系统无法正常响应多个核心接口。

**建议：先修复所有 500 回归和 ruff 错误，再重新运行 formal_test，确认通过率达到 115+/119 后再启动专家复查。**
