# R11 第十一轮 管理后台补面（RBAC 纵深）— 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-062 起 / C-104 起。

## 范围

R11 管理后台第三轮攻击面。R1（6.1-6.4）/R2（6.1-6.4 换面）已审 inline script/innerHTML/wiring/权限码种子。
本轮换面：① 12 个 admin router 共 152 端点权限码覆盖率（脚本逐端点解析）；② RBAC 自身安全
（has_permission/is_super_admin/get_permission_codes 实现）；③ 提权面（create_admin/update_admin/
set_role_permissions 角色分配约束）。

## 结果

- **发现 1 项**：F-062（P3）create_admin 无角色层级校验（可创建超管，不对称于 update_admin）
- **clean 1 项**：C-104 admin 152 端点权限码全覆盖 + RBAC 核心防护完整

---

## [F-20260808-062] create_admin 无角色层级校验——持有 admin.create 者可创建超管（RBAC 提权链） — P3

- **级别**: P3（观察项；当前种子 admin.create 仅 super_admin 持有，无当前可利用路径；权限下放后即提权）
- **维度**: 6.4 权限码（第三轮换面：RBAC 自身提权面）
- **文件**: `backend/domain/admin/services/account_service.py:196-217`（create_admin）/ `:229-245`（_check_admin_role_change）/ `backend/domain/admin/routers/admin_system_router.py:824-833`（create_admin 端点）/ `backend/seeds/seed_rbac.py:223-333`（STAFF_PERMS 不含 admin.create）
- **事实**:
  - `create_admin`（L196-217）直接 `role=data.role` + `admin_role_id=self._resolve_admin_role_id(data)`（L205-206），`_resolve_admin_role_id`（L175-194）只校验角色存在（is_deleted==0），**不校验"目标角色权限 ≤ 创建者权限"**；legacy 路径 `role=0 → super_admin`（L187）同样无约束
  - `update_admin`（L258-296）有 `_check_admin_role_change`（L229-245）——含"不能修改自己的角色"（L230-235）+ "角色必须存在"（L236-245）——**create_admin 无对应防护，不对称**
  - `set_role_permissions`（role_service.py:124-159）可将任意权限码（含 admin.create/admin.edit/role.edit）授予任意角色，无超管保护（超管 get_permission_codes 直接返回全部，不受影响——见 C-104）
  - `is_super_admin`（account_service.py:49-50）= role_code == "super_admin"，超管权限不可被 role.edit 削减（get_permission_codes L341-350 对超管直接返回全部 Permission）
- **证据**: ① 逐行读 create_admin/_resolve_admin_role_id/_check_admin_role_change 三段（无层级校验）；② AST 解析 STAFF_PERMS/TEACHER_PERMS 确认不含 admin.create/role.edit（仅 super_admin 持有）；③ 排重 grep：findings 无"提权/超管/角色层级"命中，F-034（book.view 权限漂移）不同面
- **触发**: 超管通过 set_role_permissions 将 admin.create 授予非超管角色（运营店长等）后，该角色调用 `POST /admin/api/admins` 传 `admin_role_id=<super_admin 角色 id>` 或 `role=0` → 创建超管 → 全权（含回收站彻底删除、改配置、删管理员等）
- **影响**: RBAC 权限边界被突破——一旦 admin.create 下放，持权者可永久获得超管权限且不可被回收（超管 is_super_admin 恒 True）。当前种子下无攻击路径（仅超管可创建管理员，超管本就全权），属权限设计缺陷/潜在提权面
- **建议**: ① create_admin/update_admin 增加层级校验——"被分配角色的权限集合必须是操作者权限集合的子集"（或至少禁止分配 super_admin 给非超管操作者创建/编辑的目标）；② 对齐 update_admin 已有保护模式（"不能修改自己的角色"扩展为"不能创建/分配高于自己权限的角色"）；③ 可考虑 set_role_permissions 增加"超管角色不可被非超管修改"保护（当前超管权限不受影响，属纵深防御）
- **排重**: 已 grep 确认不在 F-001~061 / C-001~103 中；F-012/F-034（权限种子漂移）不涉；C-060（R2 权限函数族反向核对）不涉 RBAC 层级

---

## [C-20260808-104] admin 152 端点权限码全覆盖 + RBAC 核心防护完整 — clean

- **方法**: R11 定向纵深。① Python 脚本逐端点解析 12 个 admin router（@router 装饰器 + 函数签名收集到闭括号）匹配 require_perm/require_super_admin/get_current_admin 鉴权依赖；② 读 RBAC 核心（admin_rbac.py require_perm/require_super_admin、account_service has_permission/is_super_admin/get_permission_codes/get_data_scope、role_service set_role_permissions、seed_rbac 角色权限种子）；③ 读 create_admin/update_admin/_check_admin_role_change/_resolve_admin_role_id
- **证据**:
  - **152 端点全部有鉴权依赖**：脚本输出 12 文件 152 端点零漏配；revive_child 用 `require_super_admin()`（admin_system_router.py:431，首轮脚本误报后人工澄清）✓；admin_login 为公开端点（预期）✓
  - **权限码语义合理**：create_admin→admin.create、set_role_permissions→role.edit、delete_admin→admin.delete 等（逐端点核对）✓；STAFF_PERMS 不含 admin/role/config 组高危码（仅 log.list/recycle.list/recycle.restore）✓
  - **超管不可降权**：is_super_admin=role_code=="super_admin"，get_permission_codes 对超管返回全部权限（不受 RolePermission 软删影响）→ set_role_permissions 无法削减超管 ✓
  - **最后超管保护**：update_admin 禁用/降权超管前 `assert_not_last_super_admin`（L272-275）✓
  - **不能修改自己的角色**：_check_admin_role_change L230-235 ✓
  - **set_role_permissions 全量替换**：软删重建 + 未知权限码静默跳过（无害）+ 幂等（existing 复用）✓；无"改超管角色"风险（超管权限不依赖 RolePermission）✓
  - **数据范围**：get_data_scope all/none/own（teacher 限定 own）✓
- **排重**: R11 本轮 RBAC 面 clean 侧（F-062 角色层级缺失为唯一缺口）；C-060（R2 权限函数族反向核对：124 唯一码全命中种子）与 C-104 互补（C-060 查码 vs 种子，C-104 查端点 vs 鉴权）；F-012/F-034 种子漂移不涉

---

## R11 完结汇总

- **范围**: 管理后台第三轮（152 端点权限码全覆盖 + RBAC 自身安全 + 提权面）
- **结果**: 发现 1 项（F-062 P3 create_admin 角色层级缺失）+ clean 1 项（C-104 权限码全覆盖）
- **关键结论**:
  - 管理后台 152 端点权限码 100% 覆盖——无裸端点，RBAC 接线完整
  - 超管保护体系完整（不可降权、最后超管保护、不能改自己角色）
  - 唯一缺口：create_admin 缺"不得创建/分配高于自己权限的角色"层级校验（不对称于 update_admin 的 _check_admin_role_change）；当前种子无利用路径，但 admin.create 一旦下放即提权
- **累计**: 61 发现（P0:0 / P1:0 / P2:10 / P3:51）+ 101 clean 记录
- **提交**: 见 git log（本轮 rounds/R11 文件 + progress 索引同步更新）
- **R11 收尾结论**: 十一轮共 61 项发现无 P0/P1；10 项 P2 全部未修。R12 候选：小程序端补面（数据 null/清理/网络兜底，维度 5 第二轮——R2 已审 5.1-5.4 一轮，本轮深度递增换面）。
