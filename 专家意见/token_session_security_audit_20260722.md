# Token/会话安全审查报告

**日期**: 2026-07-22  
**审查范围**: JWT 过期策略、Token 吊销、用户切换越权边界  
**项目**: librio (dmkwords)

---

## 一、审查发现总览

| 编号 | 严重度 | 标题 | 状态 |
|------|--------|------|------|
| S-01 | 🔴 P0 | `set_current_child` 不校验归属 — 越权切换任意孩子 | 未修复 |
| S-02 | 🔴 P0 | `add_to_shelf` / `add_favorite` / `start_quiz` 不校验归属 | 未修复 |
| S-03 | 🟠 P1 | 改密码后旧 Token 仍有效 — 无吊销机制 | 未修复 |
| S-04 | 🟠 P1 | 管理员禁用后旧 Token 在过期前仍可使用（部分缓解） | 部分缓解 |
| S-05 | 🟡 P2 | 用户端无 status 字段 — 无法禁用恶意用户 | 设计缺陷 |
| S-06 | 🟡 P2 | JWT 无刷新机制 — 2 小时硬过期 | 设计选择 |
| S-07 | 🟢 P3 | `logout` 端点无服务端操作 — 纯客户端删 token | 设计选择 |
| S-08 | 🟢 P3 | `test-token-mock` 后门受双重开关保护 | 低风险 |

---

## 二、详细发现

### S-01: `set_current_child` 不校验归属 — 越权切换任意孩子 🔴 P0

**证据**: `backend/domain/user/service.py:124-130`

```python
def set_current_child(self, user_id: int, child_id: int) -> UserResponse:
    """设置当前选中的孩子"""
    user = self.user_repo.get_by_id_or_raise(user_id)
    user.current_child_id = child_id    # ← 直接写入，不校验 child 是否属于该 user
    self.user_repo.update(user)
    self.db.commit()
    return UserResponse.model_validate(user)
```

**风险**: 攻击者可将自己的 `current_child_id` 设为任意孩子的 ID。后续所有依赖 `current_child_id` 的端点（阅读进度、书架操作等）将以该孩子身份操作。

**影响路径**:
1. 攻击者调用 `POST /user/child/switch`（或等效端点）传入 `child_id=任意ID`
2. `current_child_id` 被设为目标孩子
3. 后续 `save_progress`、`start_session` 等端点虽然调用了 `verify_child_ownership`，但传入的 `child_id` 来自 `current_child_id`——**而 `verify_child_ownership` 会校验 `child.user_id != current_user.id`**，所以实际越权操作会被拦截 ✅
4. **但** `add_to_shelf`、`add_favorite`、`start_quiz` 这三个端点直接用 `current_child_id` 且**不调用 `verify_child_ownership`** → 越权成功 ❌

**实际可利用性**: 中高。S-01 本身只是设置值，但结合 S-02 可实现完整越权链。

---

### S-02: `add_to_shelf` / `add_favorite` / `start_quiz` 不校验归属 🔴 P0

**证据**:

`backend/domain/bookshelf/router.py:27-39` — `add_to_shelf`:
```python
def add_to_shelf(
    req: BookshelfAddRequest,
    child_id: int | None = None,
    service: BookshelfService = Depends(get_bookshelf_service),
    current_user=Depends(get_current_user),
):
    cid = child_id or getattr(current_user, "current_child_id", None)
    if not cid:
        raise ValidationError("请先选择孩子")
    return service.add_to_shelf(cid, req.book_id)   # ← 无 verify_child_ownership!
```

`backend/domain/bookshelf/router.py:78-92` — `add_favorite`: 同上模式，无归属校验。

`backend/domain/advancement/router.py:53-65` — `start_quiz`: 同上模式，无归属校验。

**风险**: 结合 S-01，攻击者可：
- 对任意孩子添加书架图书（篡改其阅读清单）
- 对任意孩子收藏图书
- 对任意孩子启动测验（影响其测验记录和成就）

**修复方案**: 所有使用 `current_child_id` 的端点必须调用 `verify_child_ownership(child_id, current_user, db)`。

---

### S-03: 改密码后旧 Token 仍有效 🟠 P1

**证据**: `backend/domain/admin/services/account_service.py:312-330`

```python
def change_password(self, admin_id, old_password, new_password, current_admin_id):
    ...
    target.password_hash = hash_password(new_password)
    self.db.commit()
    return {"success": True, "message": "密码修改成功"}
    # ← 无 token 吊销，旧 token 在 exp 过期前继续有效
```

**风险**: 如果管理员密码泄露并被修改，攻击者持有的旧 token 仍可在过期前继续使用（管理员 8 小时，用户 2 小时）。

**当前缓解**: 管理端 `get_current_admin` 每次查询会检查 `Admin.status == ACTIVE`，如果管理员被禁用则 token 失效。但改密码不会自动禁用账号。

**修复方案**:
- 方案 A（推荐）: 在 `Admin` 表加 `token_generation` 字段（整数），`create_admin_token` 时写入 payload，`get_current_admin` 比对——改密码时 `token_generation += 1` 使旧 token 失效
- 方案 B: Redis 存 jti 黑名单（需引入 Redis）
- 方案 C: 改密码时缩短旧 token 过期时间（不可行，JWT 不可撤销）

---

### S-04: 管理员禁用后旧 Token 在过期前仍可使用（部分缓解）🟠 P1

**证据**: `backend/middleware/admin_auth.py:73-82`

```python
admin = (
    db.query(Admin)
    .filter(
        Admin.id == int(admin_id),
        Admin.is_deleted == 0,
        Admin.status == Admin.STATUS_ACTIVE,   # ← 每次请求都查 status
    )
    .first()
)
if not admin:
    raise UnauthorizedError("管理员不存在或已禁用")
```

**评估**: ✅ 管理员被禁用后，每次 API 调用都会查 DB 验证 status，旧 token 立即失效。这是合理的保护。

**但**: 改密码场景不会改 status，所以 S-03 仍然存在。

---

### S-05: 用户端无 status 字段 — 无法禁用恶意用户 🟡 P2

**证据**: `backend/domain/user/models.py` — User 表无 `status` 字段。

**风险**: 如果用户有恶意行为（刷接口、滥用资源），管理端无法禁用该用户账号。`get_current_user` 也无法做 status 检查。

**修复方案**: 给 User 表加 `status` 字段（`SmallInteger, default=1, comment="1=正常 0=禁用"`），`get_current_user` 查询时校验 status。

---

### S-06: JWT 无刷新机制 — 2 小时硬过期 🟡 P2

**证据**: `backend/config.py:55` — `ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 2  # 2小时`

**评估**: 当前用户端 token 2 小时硬过期，无 refresh token 机制。用户使用过程中可能突然掉线。

**设计选择**: 对于小程序场景，2 小时 + 重新静默登录（wx.login）是可接受的方案。小程序端可以监听 401 自动重新登录，用户无感。**暂不修改，记录为已知设计**。

---

### S-07: `logout` 端点无服务端操作 🟢 P3

**证据**: `backend/domain/admin/admin_auth_router.py:120-123`

```python
@router.post("/logout")
def admin_logout():
    """管理员登出（客户端清 token）"""
    return {"success": True}
```

**评估**: JWT 无状态登出的常见做法。客户端清 token 即可。如果要实现服务端登出，需要 jti 黑名单（Redis），当前规模不必要。**记录为已知设计**。

---

### S-08: `test-token-mock` 后门 🟢 P3

**证据**: `backend/middleware/auth.py:70-76`

```python
if settings.DEBUG and settings.ENABLE_TEST_TOKEN and token == "test-token-mock":
    logger.warning("Using test-token-mock — DEBUG+ENABLE_TEST_TOKEN both active")
```

**评估**: 受 `DEBUG=True` 且 `ENABLE_TEST_TOKEN=True` 双重开关保护。`config.py:111` 有生产环境校验 `SECRET_KEY` 不能为默认值。但建议生产环境显式检查 `ENABLE_TEST_TOKEN=False`。

---

## 三、修复优先级

| 优先级 | 编号 | 修复内容 | 工作量 |
|--------|------|---------|--------|
| **P0** | S-01 | `set_current_child` 加归属校验 | 0.5h |
| **P0** | S-02 | 3 个端点加 `verify_child_ownership` | 1h |
| **P1** | S-03 | token_generation 机制 | 4h |
| **P2** | S-05 | User 表加 status 字段 + migration | 2h |
| **P2** | S-08 | 生产环境显式校验 | 0.5h |
| **P3** | S-06/S-07 | 记录为已知设计，暂不修改 | — |

**总计**: P0 修复 1.5h，P1+P2 修复 6.5h。

---

## 四、架构图

```
                    JWT Token 生命周期
                    ═══════════════════

用户端:  wx-login/phone-login → create_access_token(sub=user_id, exp=2h)
                                   │
                                   ▼
         每次请求: get_current_user → verify_token → DB 查 User
                                    ❌ 无 status 检查 (S-05)
                                    ❌ 无 token 吊销 (S-03)

管理端:  admin_login → create_admin_token(sub=admin_id, role, exp=8h)
                                   │
                                   ▼
         每次请求: get_current_admin → verify_token → DB 查 Admin
                                    ✅ status == ACTIVE 检查 (S-04)
                                    ❌ 无 token 吊销 (S-03)


              current_child_id 越权链
              ═══════════════════════

  set_current_child(child_id=任意)
         │  ❌ 不校验归属 (S-01)
         ▼
  current_child_id = 任意孩子
         │
         ├──→ save_progress: verify_child_ownership ✅ 拦截
         ├──→ start_session: verify_child_ownership ✅ 拦截
         ├──→ add_to_shelf:  ❌ 不校验 (S-02) → 越权成功
         ├──→ add_favorite:  ❌ 不校验 (S-02) → 越权成功
         └──→ start_quiz:    ❌ 不校验 (S-02) → 越权成功
```

---

## 五、结论

**S-01 + S-02 是真实可利用的越权漏洞**，攻击链完整：设置任意 child_id → 操作该孩子的书架/收藏/测验。虽然影响范围有限（非财务/敏感数据），但属于明确的权限边界突破，应立即修复。

**S-03 token 吊销缺失**是中等风险——改密码后旧 token 在 2-8 小时内仍有效。`token_generation` 方案无需引入 Redis，改造成本低。

**S-05 用户端无 status**是设计缺陷，管理端无法封禁恶意用户，应在隐私 Phase 1 之前补齐。

---

*报告路径: 专家意见/token_session_security_audit_20260722.md*
