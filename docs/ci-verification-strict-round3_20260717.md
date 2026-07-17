# CI 全量验证报告（第三轮严格审查）

**日期**: 2026-07-17 (v2 — 最终提交数字修正)  
**审查原因**: 补齐 HTTP 层测试 + 7 个边界场景后的终审  
**审查方式**: 逐条代码级 + 执行级核实

---

## 一、CI 7 项检查 — 全部通过 ✅

| # | 检查项 | 声称 | 实际 | 判定 |
|---|--------|------|------|------|
| 1 | ruff check backend/ tests/ | 0 errors | All checks passed! | ✅ 一致 |
| 2 | ruff check features/ scripts/ | 0 errors | All checks passed! | ✅ 一致 |
| 3 | ruff format --check . | 325 files | **326 files** already formatted | ⚠️ 第三次偏差 |
| 4 | pytest | 36 新增 (15+21) | **210 passed, 5 skipped**（+21 vs 上轮 189） | ✅ 新增 36=15+21 准确 |
| 5 | behave | 138/970 | 138/970/0 failed | ✅ 一致 |
| 6 | verify_api_contract | OK | OK | ✅ 一致 |
| 7 | check_model_consistency | 53 tables | 53 tables | ✅ 一致 |

### pytest 数字演变（三轮追踪）

| 轮次 | passed | skipped | 总 | 增量 | 说明 |
|------|--------|---------|-----|------|------|
| 第一轮 | 174 | 5 | 179 | — | 基线 |
| 第二轮 | 189 | 5 | 194 | +15 | +15 service 层测试 |
| 第三轮 | 210 | 5 | 215 | +21 | +21 HTTP 层测试 |
| **累计增量** | | | | **+36** | **15 service + 21 HTTP = 36 ✅** |

数学完全一致。声称 36 新增 = 实际 36 新增 ✅。

### ruff format 数字偏差（第三次）

声称 325，实际 326。新增 `test_new_routes_http.py` → 325+1=326。数学正确但声称数字未更新。**第三次数字偏差**（前两次为 pytest passed/skipped）。

---

## 二、21 个 HTTP 层测试 — 逐条核实 ✅

### 测试分布

| 端点 | HTTP 测试数 | 覆盖 |
|------|------------|------|
| GET /child/transfer/records | 6 | 鉴权401 ✅ 正常200 ✅ 空列表 ✅ 软删除排除 ✅ 排序 ✅ status映射 ✅ |
| GET /book/{id}/related | 4 | 公开访问(404) ✅ 正常返回 ✅ 空列表 ✅ 不存在404 ✅ |
| GET /reading/checkin/{id}/records | 4 | 鉴权401 ✅ 正常200 ✅ 空列表 ✅ 他人孩子403 ✅ |
| DELETE /child/{id} | 7 | 鉴权401 ✅ 正常200 ✅ 他人403 ✅ 不存在404 ✅ 未还书422 ✅ OVERDUE 422 ✅ 已删除404 ✅ |
| **合计** | **21** | |

声称 21 = 实际 21 ✅

### HTTP 状态码正确性

| 状态码 | 场景 | 判定 |
|--------|------|------|
| 401 | 未携带 Authorization → TransferRecords, CheckinRecords, DeleteChild | ✅ 正确 |
| 403 | 他人孩子 → CheckinRecords, DeleteChild | ✅ 正确 |
| 404 | 不存在/已删除 → RelatedBooks, DeleteChild | ✅ 正确 |
| 422 | 有未还书 → DeleteChild (ValidationError → 422) | ✅ 正确 |
| 200 | 正常路径 → 全部端点 | ✅ 正确 |

### 测试代码质量

| 检查项 | 结果 |
|--------|------|
| 假断言 | 0 ✅ |
| 有意义断言 | 30 ✅ |
| try/except（fixture 清理，非吞噬） | 1（fixture finally） ✅ |
| fixture 隔离 | 1 个 http fixture，StaticPool + create/drop all ✅ |
| ruff check | All checks passed! ✅ |
| ruff format | 1 file already formatted ✅ |
| JWT 鉴权 | 使用 `create_access_token` 生成真实 JWT ✅ |

---

## 三、7 个边界场景覆盖 — 5/7 已修复

| # | 场景 | 上轮 | 本轮 | 测试方法 |
|---|------|------|------|---------|
| 1 | transfer/records 软删除排除 | ❌ | ✅ | `test_soft_deleted_excluded` |
| 2 | transfer/records 排序 | ❌ | ✅ | `test_ordered_newest_first` |
| 3 | transfer/records status 映射 | ❌ | ✅ | `test_status_map_full` |
| 4 | book/{id}/related 软删除排除 | ❌ | ❌ | **仍未测** |
| 5 | checkin/{id}/records 软删除排除 | ❌ | ❌ | **仍未测** |
| 6 | DELETE /child OVERDUE | ❌ | ✅ | `test_blocked_by_overdue_borrow` |
| 7 | DELETE /child 已删除再删 | ❌ | ✅ | `test_already_deleted_returns_404` |

**覆盖: 5/7 ✅, 遗漏: 2/7**（book 和 checkin 的软删除过滤，代码有 `is_deleted==0` 但测试未验证）

---

## 四、测试层级完整性

| 层级 | 上轮 | 本轮 | 状态 |
|------|------|------|------|
| Service 层（业务逻辑） | 15 ✅ | 15 ✅ | 保持 |
| HTTP 层（鉴权/序列化/参数） | 0 ❌ | 21 ✅ | **已修复** |
| HTTP 状态码 | 0 | 15 个断言 ✅ | **新增** |
| 鉴权（401/403） | 0 | 5 个测试 ✅ | **新增** |

---

## 五、环境兼容性确认

| 环境 | SECRET_KEY | DEBUG | 测试通过 |
|------|-----------|-------|---------|
| 本地 .env | 真实密钥 | false | ✅（create_access_token 用真实 JWT） |
| CI ci.yml | ci-test-key-short | true | ✅（ENABLE_TEST_TOKEN=true 可用 mock token） |

两种环境都能正确运行测试 ✅

---

## 六、发现的问题

### ✅ 数字演变（三轮完整追踪）

| 轮次 | passed | skipped | 总 | 新增 |
|------|--------|---------|----|------|
| 第一轮 | 174 | 5 | 179 | 基线 |
| 第二轮 | 189 | 5 | 194 | +15 service |
| 第三轮 | 210 | 5 | 215 | +21 HTTP |
| **累计** | **210** | **5** | **215** | **+36 = 15+21 ✅** |

### ⚠️ ruff format 第三次偏差

- 声称 325，实际 **326**（`test_new_routes_http.py` 新增未重计）
- 三轮累计数字偏差 3 次（pytest 2 + ruff 1）

### 🟡 2 个边界场景仍未测（P3）

- `GET /book/{id}/related` — 软删除图书排除（代码 `is_deleted==0`，测试未验证）
- `GET /reading/checkin/{id}/records` — 软删除 session 排除（代码 `is_deleted==0`，测试未验证）
- 风险极低：代码审查确认过滤逻辑正确，且正常路径间接覆盖

---

## 七、最终结论

| 维度 | 第一轮 | 第二轮 | 第三轮 | 最终 |
|------|--------|--------|--------|------|
| CI 全绿 | ✅ | ✅ | ✅ | ✅ |
| 4 路由代码质量 | ✅ | ✅ | ✅ | ✅ |
| Service 层测试 | ❌ 0 | ✅ 15 | ✅ 15 | ✅ |
| HTTP 层测试 | ❌ 0 | ❌ 0 | ✅ 21 | ✅ |
| 边界场景覆盖 | 0/7 | 0/7 | 5/7 | 5/7 |
| 数字准确性 | ⚠️ | ⚠️ | ⚠️ | ⚠️ |

**最终判定**:
- CI 全绿确认 ✅
- 4 个新路由 36 个测试全部真实有效 ✅
- Service 层 + HTTP 层双覆盖 ✅
- 7 个边界场景修复 5/7，剩余 2 个为 P3（风险极低）
- **P1/P2 已修复**，仅剩 P0 需外部输入（appid、服务协议、隐私政策运营者）
- **数字不可信**: ruff format 声称 325 实际 326（第三次偏差），pytest 数字演变手动追溯方对齐
