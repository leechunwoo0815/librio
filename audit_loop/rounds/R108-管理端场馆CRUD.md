# R108 第一百零八轮 管理端场馆链 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-091、F-092 起，C-201 起。

## 范围

R108 管理端场馆链（venue_service.py 全：list/create/delete/update + Venue 模型 + soft_delete 链路）。R52
方法清单曾列 venue 管理未深挖，R10/R15/R19/R20 仅涉性能/关联面，CRUD 主链本次定向纵深。

## 结果

- **发现 2 项**（P3×2）：F-091 场馆名无唯一约束（可重复建馆）；F-092 删除不存在场馆假成功
- **clean 1 项**：C-201 场馆列表分页 + 更新安全

---

## [F-20260808-091] Venue.name 无唯一约束，可创建重复场馆（P3）

- **级别**: P3（低）
- **位置**: backend/domain/admin/services/venue_service.py:39-51（create_venue）；backend/domain/admin/models.py:393（Venue.name 无 unique）
- **类别**: 先查后插无唯一约束（模式① 家族——R10-R30 归纳，与 F-066/075/076/086 同类，venue 实体首次出现）
- **事实**: create_venue 直接 `Venue(name=data.name, ...)` 插入，**无 name 查重**；Venue.name 列仅 `nullable=False` 无 `unique=True` → 同名场馆可无限创建
- **证据**:
  - venue_service.py:39-51 无任何 name 存在性查询（对照 book_service 的 ISBN 查重、role_service 的 code 查重）
  - models.py:393 `name = Column(String(100), nullable=False, comment="场馆名称")` 无 unique
  - 全库 unique 约束仅 2 处（models.py:29 username、:86 配置键）——venue.name 不在其中
- **触发**: 管理端重复录入同名场馆（如"旗舰店"建两次）→ 双双落库
- **影响**: 家长端场馆选择列表歧义（R20 list_by_venue 按 venue 展示时段，同名场馆无法区分）；管理端统计/报表按 name 聚合错乱
- **建议**: `name` 加 `unique=True`（存量重名先清理）或 create_venue 增查重抛 ValidationError（与 user.phone / role.code 同款）
- **排重**: 已 grep rounds/R*.md + findings-20260807.md——F-066/075/076/086 均为 book/barcode 等实体，venue name 唯一性首次报；R101 老师 CRUD 的 C-194 判 clean 基于"老师重名影响小"，场馆为家长端核心选择项，业务影响显著不同，不构成豁免

---

## [F-20260808-092] delete_venue 删除不存在场馆返回假成功（P3）

- **级别**: P3（低）
- **位置**: backend/domain/admin/services/venue_service.py:53-57（delete_venue）；backend/common/base_repo.py:117-122（soft_delete）
- **类别**: 存在性守卫缺失（模式⑤ 家族）
- **事实**: delete_venue 调 `self.venue_repo.soft_delete(venue_id)` 后无条件 `return {"success": True}`；而 soft_delete 内部 `get_by_id` 对不存在 id **静默返回 None**（base_repo.py:119-122），无 NotFoundError 抛出 → 删除不存在的场馆也返回成功
- **证据**:
  - base_repo.py:118-122：`obj = self.get_by_id(id); if obj: ...` 无 else 分支抛错
  - venue_service.py:55-57 无存在性前置检查（对照同文件 update_venue L61-63 有 `if not venue or is_deleted == 1: raise NotFoundError`——同链不对称）
  - 对照 R102 delete_role：is_system 拦截 + admin_count 检查双保护（R102 C-195）
- **触发**: 管理端误删已删/不存在的 venue_id → API 返回 success=True
- **影响**: 调用方/前端无法区分"已删除"与"删除失败"；重复删除操作无感知。弱业务影响，但同链 update 有检查而 delete 无——不对称缺口
- **建议**: delete_venue 前置 get_by_id，不存在抛 NotFoundError（与 update_venue 对齐）；如需幂等可显式注释说明
- **排重**: grep 确认"假成功/删除不存在"无历史记录（R102 delete_role 有保护但未覆盖 venue 链）

---

## [C-20260808-201] 场馆列表分页 + 更新安全 — clean

- **方法**: R108 定向纵深。读 venue_service.py 全（70 行）+ models.py Venue + base_repo soft_delete + schema
- **证据**:
  - **list_venues**：page_size 默认 100、offset 计算正确、total=count()、has_next 公式正确（L27-37）✓；VenueResponse.model_validate 序列化 ✓
  - **update_venue**：get_by_id + is_deleted 过滤 + NotFoundError（L61-63）✓；exclude_unset 增量更新 + hasattr 防御（L64-67）✓
  - **软删机制**：soft_delete 仅置 is_deleted=1，物理行保留 ✓
  - **权限**：R11 已核（venue.* require_perm）✓
- **排重**: R15（venue N+1 性能面）、R19（评估域关联）、R20（家长课程 venue 时段）——均非本条覆盖面

---

## R108 完结汇总

- **范围**: 管理端场馆 CRUD（venue_service.py 全链）
- **结果**: 发现 2 项（F-091 P3、F-092 P3）+ clean 1 项（C-201）
- **关键结论**:
  - create_venue 无 name 查重 + 模型无唯一约束 → 可重复建馆（模式① venue 实体首次）
  - delete_venue 无存在性检查 → 假成功（同链 update 有检查，不对称）
  - list/update 工程正确
- **累计**: 91 发现（P0:0 / P1:0 / P2:14 / P3:77）+ 198 clean 记录
- **提交**: 见 git log（本轮 rounds/R108 文件 + progress 索引同步更新）
- **R108 收尾结论**: 一百零八轮共 91 项发现无 P0/P1；14 项 P2。R109 候选：继续轮转新面（如 activity 管理端、certificate 管理端）。
