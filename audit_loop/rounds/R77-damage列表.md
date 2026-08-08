# R77 第七十七轮 损坏报告管理端列表 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-089 起 / C-170 起。

## 范围

R77 损坏报告管理端列表（R46/R47 已审 damage 定责/冲正链，本列表面）。get_list 返回 dict 含 ORM items、
response_model=AdminActionResponse 序列化、C-052 ORM 序列化面补漏。

## 结果

- **发现 1 项**：F-089（P2）damage get_list 的 items 是 ORM 对象列表，经 AdminActionResponse 序列化失败（PydanticSerializationError 500）——管理端损坏报告列表功能损坏
- **clean 1 项**：C-170 列表面其余正常（过滤/分页/权限）

---

## [F-20260808-089] damage get_list 返回 ORM items 经 AdminActionResponse 序列化失败（500）——管理端列表功能损坏 — P2

- **级别**: P2（功能错/用户可见异常——管理端损坏报告列表接口 500，运营无法查看/管理损坏报告）
- **维度**: 4 API 契约（ORM 序列化面；C-052 补漏）
- **文件**: `backend/domain/admin/services/damage_admin_service.py:465-483`（get_list 返回 items=ORM 列表）/
  `backend/domain/admin/routers/admin_damage_router.py:43-53`（response_model=AdminActionResponse）/
  `backend/domain/admin/admin_schemas.py:28-47`（AdminActionResponse extra="allow" 不处理 ORM）
- **事实**:
  - `get_list`（damage_admin_service.py:482-483）：`return {"total": total, "items": items, ...}`——**items 是 BookDamageReport ORM 对象列表**
  - 端点 `response_model=AdminActionResponse`（router L43）——AdminActionResponse `extra="allow"`（admin_schemas.py:35）+ model_validator 仅处理 Pydantic BaseModel（L43-47，ORM 非 Pydantic 不转）
  - **实证**：`AdminActionResponse.model_validate({'items': [BookDamageReport()]})` 通过（extra 保留 ORM）→ `jsonable_encoder(resp)` → **PydanticSerializationError: Unable to serialize unknown type: BookDamageReport**——FastAPI 响应路径正是 jsonable_encoder → **真实请求 500**
  - **C-052 补漏**：R2 C-052（L720-724）审"直接返回 ORM 4 处"（refund/order/borrow/advancement）——其 grep `return .*(.all()|.first()|.scalar())` 只匹配 router 直接返回，**未覆盖"dict 内嵌 ORM items"面**（damage get_list 是第 5 处，C-052 漏）
- **证据**: ① get_list L482-483 items=ORM；② 实证输出"PydanticSerializationError: Unable to serialize unknown type: BookDamageReport"（jsonable_encoder 复现，FastAPI 同路径）；③ 排重 grep：C-052 4 处不含 damage（dict 内嵌面漏）
- **触发**: 运营打开管理后台"损坏报告"列表 → GET /admin/api/book-damage → 500
- **影响**: 管理端损坏报告列表**功能损坏**（无法查看/筛选损坏报告）——定责/审核/赔偿链（R46/R47）全部依赖列表入口；运营需绕过列表（直接操作报告详情）。无资金/安全（管理端功能错），P2
- **建议**: ① get_list 的 items 改为 dict 列表（`[{...} for r in items]` 或 `[BookDamageReportResponse.model_validate(r) for r in items]`）；② 或端点换 `PaginatedResponse`（admin_schemas.py:49-53，items: list）——但 items 仍需转 dict（ORM 无法序列化）；③ 修复后补列表端点测试（防回归）
- **排重**: 已 grep 确认不在 F-001~088 / C-001~169 中；C-052（R2 4 处 ORM）为覆盖盲区，本项为其补漏（dict 内嵌面）；F-010（缺契约 16 端点）不涉

---

## [C-20260808-170] 列表面其余正常（过滤/分页/权限） — clean

- **方法**: R77 定向纵深。读 damage_admin_service.py:465-483（get_list）+ admin_damage_router.py:43-53（端点）+
  admin_schemas.py:28-53（AdminActionResponse/PaginatedResponse）+ 实证 + 排重
- **证据**:
  - **过滤**：is_deleted==0 + status 可选（L467-471）✓
  - **分页**：count + offset/limit + page_size le=100（router L47）✓
  - **排序**：create_time desc ✓
  - **权限**：require_perm("book_damage.list")（router L49）✓
  - **响应模型缺陷**：仅 F-089（items ORM 序列化失败）——AdminActionResponse extra="allow" 无法处理 ORM 值
- **排重**: R77 本轮列表面 clean 侧（F-089 序列化为唯一缺口）

---

## R77 完结汇总

- **范围**: 损坏报告管理端列表（get_list/序列化/过滤/分页）
- **结果**: 发现 1 项（**F-089 P2 列表 500 功能损坏**）+ clean 1 项（C-170）
- **关键结论**:
  - **F-089 是重要功能缺陷（P2）**：damage 管理端列表接口 500——get_list 返回 ORM items 经 AdminActionResponse 无法序列化（实证 PydanticSerializationError）；C-052（R2）只审 router 直接返回 ORM，漏了"dict 内嵌 ORM"面
  - 修复简单（items 转 dict）+ 补测试
  - 提示：**同类 dict 内嵌 ORM 面需全库复查**（F-089 为第 1 处，模式 1 潜在多处）
- **累计**: 88 发现（P0:0 / P1:0 / **P2:14** / P3:74）+ 167 clean 记录
- **提交**: 见 git log（本轮 rounds/R77 文件 + progress 索引同步更新）
- **R77 收尾结论**: 七十七轮共 88 项发现无 P0/P1；14 项 P2（F-089 新增）。R78 候选：继续轮转新面。
