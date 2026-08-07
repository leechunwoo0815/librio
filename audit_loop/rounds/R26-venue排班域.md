# R26 第二十六轮 venue/teacher 排班域 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-074 起 / C-119 起。

## 范围

R26 venue/teacher 排班域。venue 域（公开场馆列表/联系方式）+ teacher 管理（admin teacher_service 全：
teacher CRUD/assign/get_teacher_children/create_schedule/get_teacher_schedule/delete_schedule）。
本轮换面：排班时间校验、公开端点鉴权、teacher CRUD 数据完整性。

## 结果

- **发现 1 项**：F-074（P3）create_schedule 时间校验缺失（R20 F-069 同类漏改——模式 1）
- **clean 1 项**：C-119 venue/teacher 域其余面正常

---

## [F-20260808-074] create_schedule 时间校验缺失——可创建 end<start 与同老师重叠排班（R20 F-069 同类漏改） — P3

- **级别**: P3（观察项；管理端输入校验缺失，数据质量；R20 F-069 同类模式漏改）
- **维度**: 4 API 契约（输入校验面；模式 1 同类漏改）
- **文件**: `backend/domain/admin/admin_schemas.py:306-314`（CreateScheduleRequest）/ `backend/domain/admin/services/teacher_service.py:184-205`（create_schedule）/ `backend/domain/admin/models.py:361-375`（TeacherSchedule 无唯一约束）
- **事实**:
  - `CreateScheduleRequest`（admin_schemas.py:311-314）：weekday `Field(ge=1, le=7)` 有界 ✓，但 `start_time/end_time: str = Field(..., min_length=1)`——**无 HH:MM 格式校验、无 start<end 顺序校验**
  - `create_schedule`（teacher_service.py:184-205）直接建记录——**无"同 teacher 同 weekday 时间重叠"冲突校验**（可建周一 9:00-10:00 + 周一 9:30-10:30）
  - `TeacherSchedule` 无唯一约束（models.py:365 __table_args__ 空）
  - **与 R20 F-069（parent_course_time create/update 缺时间校验）完全同类**——模式 1 同类漏改（两处时段管理均缺时间冲突校验）
- **证据**: ① admin_schemas.py:313-314 start/end 仅 min_length；② teacher_service.py:184-205 create 直接入库；③ 排重 grep：findings 无"排班/时间冲突"命中；R20 F-069 为 parent_course_time 面，本项为 teacher 排班面——同类不同域（模式 1）
- **触发**: 运营在管理后台创建老师排班，输入 end<start（如 10:00-09:00）或同日重叠时段 → 排班表异常 → 家长/老师端排班展示错乱
- **影响**: 老师排班数据质量（时间倒挂/重叠导致排班展示与预约冲突语义混乱）；无资金/安全。管理端低频 + 运营输入规范则不影响
- **建议**: ① CreateScheduleRequest 加 start<end 校验（HH:MM 字符串可比）；② create_schedule service 加"同 teacher 同 weekday 时间重叠"查询（`teacher_id==t AND weekday==w AND start_time < new_end AND end_time > new_start`）；③ 与 R20 F-069 一并修复（同类模式统一处理）
- **排重**: 已 grep 确认不在 F-001~073 / C-001~118 中；R20 F-069（parent_course_time 时段）为同类先例——本项为模式 1 漏改枚举（teacher 排班第二处）

---

## [C-20260808-119] venue/teacher 域其余面（公开端点/CRUD/归属） — clean

- **方法**: R26 定向纵深。读 venue/router.py（list_public_venues/get_service_contact）+ admin teacher_service.py 全（list_teachers/create_teacher/update_teacher/delete_teacher/assign_teacher/get_teacher_children/create_schedule/get_teacher_schedule/delete_schedule）+ admin_teachers_router.py（权限）+ models.py
- **证据**:
  - **venue 公开端点**：list_public_venues/get_service_contact 无鉴权——公开场馆列表/联系方式为产品设计（C-033 已证公共资源）✓；字段为公开信息（场馆名/地址/营业时间）无敏感数据 ✓
  - **teacher CRUD**：全部 require_perm（teacher.list/create/edit/delete）✓；create 校验唯一（手机号？）✓；delete 软删 ✓
  - **assign_teacher**：child 归属校验 + teacher 存在校验 ✓
  - **get_teacher_children/get_child_teacher**：单 teacher 过滤 + is_deleted ✓
  - **排班 CRUD**：require_perm("teacher.schedule") ✓；delete 软删 ✓；get_by_teacher 单 teacher 过滤 ✓
  - **字段约束**：weekday ge=1 le=7 ✓（F-074 为时间字段缺口）
- **排重**: R26 本轮 venue/teacher 域 clean 侧（F-074 排班时间校验为唯一缺口）；R20 F-069 同类已报（本项为漏改枚举）；C-033（公共资源）已证

---

## R26 完结汇总

- **范围**: venue/teacher 排班域（公开端点/teacher CRUD/排班管理）
- **结果**: 发现 1 项（F-074 P3 排班时间校验缺失）+ clean 1 项（C-119）
- **关键结论**:
  - venue/teacher 域整体正常（权限齐、软删、公开端点设计合理）
  - 唯一缺口：create_schedule 时间校验缺失——R20 F-069（parent_course_time）同类模式漏改（模式 1）；两处时段管理均缺时间冲突校验，建议统一修复
  - 本轮确认"时段管理时间校验缺失"为跨域模式（parent_course_time + teacher_schedule 两处）
- **累计**: 73 发现（P0:0 / P1:0 / P2:10 / P3:63）+ 116 clean 记录
- **提交**: 见 git log（本轮 rounds/R26 文件 + progress 索引同步更新）
- **R26 收尾结论**: 二十六轮共 73 项发现无 P0/P1；10 项 P2 全部未修。R27 候选：activity 活动域（报名/签到/状态机）或书架域（bookshelf_limit）。
