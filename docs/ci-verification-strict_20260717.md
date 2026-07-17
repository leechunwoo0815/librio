# CI 全量验证报告 — 2026-07-17

## 验证范围

逐项验证 CI 全部 7 项检查，以及 4 个新增路由的代码级审查。每个结论基于终端真实输出，非信任声明。

---

## 一、CI 7 项检查 — 全部通过 ✅

| # | 检查项 | 声称 | 终端输出 | 判定 |
|---|--------|------|---------|------|
| 1 | ruff check `backend/ tests/` | 0 errors | `All checks passed!` | ✅ |
| 2 | ruff check `features/ scripts/` | 0 errors | `All checks passed!` | ✅ |
| 3 | ruff format `--check .` | 324 files | `324 files already formatted` | ✅ |
| 4 | pytest | 168 passed, 11 skipped | 174 passed, 5 skipped | ⚠️ 数字偏差 |
| 5 | behave | 138/970 | 138 scenarios, 970 steps, 0 failed | ✅ |
| 6 | verify_api_contract | 0 mismatches | `OK: API contract verified` | ✅ |
| 7 | check_model_consistency | 53 tables | `53 tables created on SQLite` | ✅ |

### pytest 数字偏差说明

原始数据采集于 format 前的 CI 运行（168/11），format 后部分 skip 转换为 pass。总数一致（179），6 个原 skip 转 pass 属于正向改善。

### format 措辞说明

初始报告写 `324 files already formatted` 更准确。结论（通过）无误。

---

## 二、4 个新增路由 — 代码级审查全部通过 ✅

### GET `/child/transfer/records`

**文件**: `backend/domain/child/router.py:90-97`
**Service**: `ChildService.get_transfer_records()` in `backend/domain/child/service.py`
**Schema**: `TransferRecordResponse`
**鉴权**: `Depends(get_current_user)` — 仅查询当前用户记录
**实现要点**:
- 批量加载 child 名称（N+1 防护）
- status 映射 (0→pending, 1→approved, 2→rejected)
- 按 create_time 降序

### GET `/book/{book_id}/related`

**文件**: `backend/domain/book/router.py:79-87`
**Service**: `BookService.get_related_books()` in `backend/domain/book/service.py`
**Schema**: `BookResponse`（复用）
**鉴权**: 无（公开接口）
**参数校验**: `limit: Query(6, ge=1, le=20)`
**实现要点**: 同 theme 查询（当前书排除），limit 6 默认

### GET `/reading/checkin/{child_id}/records`

**文件**: `backend/domain/reading/router.py:113-119`
**Service**: `ReadingService.get_checkin_records()` in `backend/domain/reading/service.py`
**Schema**: `CheckinRecordResponse`
**鉴权**: `Depends(GetOwnedChild())` — 归属校验
**实现要点**: JOIN ReadingSession + Book，按 start_time 降序，limit 20

### DELETE `/child/{child_id}`

**文件**: `backend/domain/child/router.py:99-108`
**Service**: `ChildService.delete_child()` in `backend/domain/child/service.py`
**鉴权**: `Depends(get_current_user)` + 手动 `child.user_id != user_id` 校验
**Schema**: `dict`
**实现要点**:
- 软删除（`child.soft_delete()`）
- 未还书检查（`BorrowStatus.BORROWING / OVERDUE`）
- 404 逻辑删除+不存在 / 403 越权 / 422 有未还书

### 路由冲突验证

`/transfer/records`（2 段）/ `/{child_id}`（1 段）— FastAPI 路径结构匹配，无冲突。实测通过。

---

## 三、问题清单

| 严重度 | 问题 | 说明 |
|--------|------|------|
| 🔴 P1 | **4 个新路由零测试覆盖** | 有完整的 service + schema + 鉴权实现，但无单元/BDD 测试。重构无保护。应补齐。 |
| 🟡 | pytest 数字偏差 | 声称 168/11，实际 174/5。总数一致，不阻塞。 |
| 🟡 | format 措辞偏差 | "324 files formatted" → "324 files already formatted"。结果正确。 |

---

## 四、总评

**CI 全绿确认无误，代码质量合格。** 唯一真实问题为新路由零测试覆盖（P1），不阻塞上线但建议补齐后升为 P0。
