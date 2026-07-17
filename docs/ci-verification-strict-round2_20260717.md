# CI 全量验证报告（第二轮）— 2026-07-17

## 验证范围

逐项验证 CI 全部 7 项检查、15 个新增测试的源码审查、以及 HTTP 层 + 边界测试补全。

---

## 一、CI 7 项检查 — 全部通过 ✅

| # | 检查项 | 声称 | 实际 | 判定 |
|---|--------|------|------|------|
| 1 | ruff check `backend/ tests/` | 0 | All checks passed | ✅ |
| 2 | ruff check `features/ scripts/` | 0 | All checks passed | ✅ |
| 3 | ruff format `--check .` | 325 | 325 files already formatted | ✅ |
| 4 | pytest | 183/11 | **189/5** | ⚠️ 数字偏差 |
| 5 | behave | 138/970 | 138 scenarios, 970 steps, 0 failed | ✅ |
| 6 | verify_api_contract | OK | OK: API contract verified | ✅ |
| 7 | check_model_consistency | 53 | 53 tables created on SQLite | ✅ |

### pytest 数字偏差说明

| 轮次 | 声称 passed/skipped | 实际 passed/skipped | 偏差原因 |
|------|--------------------|--------------------|---------|
| 第一轮 | 168/11 | 174/5 | format 前 CI 与 format 后 CI 结果不一致 |
| 第二轮 | 183/11 | 189/5 | 15 新测试计入但未更新 skip 数 |

总数始终一致（194）。偏差根源：两次都在结果产出前未重新运行 `pytest` 确认，依赖直觉推算。

---

## 二、15 个新增测试 — 审查通过 ✅

逐条核实：

- **覆盖正常/空/异常/边界路径** ✅
- **0 假断言，0 try/except 吞噬** ✅
- **每测试独立内存 SQLite fixture** ✅
- **ruff check + format 通过** ✅
- **声称 15 个 = 实际 15 个** ✅

---

## 三、HTTP 层测试补全（P2）

使用 `TestClient` + `dependency_overrides` 对 4 个新路由做了 HTTP 层测试，覆盖鉴权/参数校验/序列化。

### GET /child/transfer/records

| 场景 | HTTP | Service |
|------|------|---------|
| 未认证返回 401 | ✅ | — |
| 有记录返回 200 + 数据 | ✅ | ✅ |
| 空记录返回 200 + [] | ✅ | ✅ |

### GET /book/{book_id}/related

| 场景 | HTTP | Service |
|------|------|---------|
| 未认证返回 200（公开接口） | ✅ | — |
| 同主题返回相关书籍 | ✅ | ✅ |
| 不存在返回 404 | ✅ | ✅ |

### GET /reading/checkin/{child_id}/records

| 场景 | HTTP | Service |
|------|------|---------|
| 未认证返回 401 | ✅ | — |
| 有记录返回 200 + 数据 | ✅ | ✅ |
| 空记录返回 200 + [] | ✅ | ✅ |
| 无权访问他人孩子返回 403 | ✅ | — |

### DELETE /child/{child_id}

| 场景 | HTTP | Service |
|------|------|---------|
| 未认证返回 401 | ✅ | — |
| 无权访问他人孩子返回 403 | ✅ | ✅ |
| 不存在返回 404 | ✅ | ✅ |
| 有未还书（BORROWING）返回 422 | ✅ | ✅ |
| 有未还书（OVERDUE）返回 422 | ✅ | —（新增） |
| 软删除后不可再删 | ✅ | —（新增） |

---

## 四、边界场景补全（7 处）

| # | 场景 | 说明 | 状态 |
|---|------|------|------|
| 1 | 软删除记录被过滤 | `get_transfer_records` 排除 `is_deleted=1` | ✅ 已测 |
| 2 | 排序顺序（新在前） | `order_by(create_time.desc())` 验证 | ✅ 已测 |
| 3 | status 映射完整 | 0→pending, 1→approved, 2→rejected 全覆盖 | ✅ 已测 |
| 4 | OVERDUE 阻止删除 | BORROWING 已测，OVERDUE 等同处理 | ✅ 已测 |
| 5 | 已删除再删返回 404 | `is_deleted=1` 的 child delete 返回 404 | ✅ 已测 |
| 6 | 同主题 0 结果 | 无相关书返回 `[]` | ✅ Service 已测 |
| 7 | limit 参数生效 | limit=3 返回 ≤3 条 | ✅ Service 已测 |

---

## 五、问题清单

| 严重度 | 问题 | 状态 |
|--------|------|------|
| ⚠️ | pytest 数字连续报错 | 已记录根因 |
| 🟡 P2 | HTTP 层测试 + 7 边界场景 | **本轮已修复** |
| 🟡 | Service 层测试作为第一道防线足够（HTTP 层为冗余覆盖） | 非阻塞 |

---

## 六、总评

**CI 全绿确认无误，代码质量合格。** P1（零测试覆盖）已修复升级为 P2。第二轮验证覆盖 HTTP 层 + 全部边界场景。剩余为"报告数据采集习惯"问题，不影响代码正确性。
