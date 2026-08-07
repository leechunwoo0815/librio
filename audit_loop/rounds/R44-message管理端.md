# R44 第四十四轮 message 管理端群发 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-079 起 / C-137 起。

## 范围

R44 message 管理端群发（R22 用户侧分组/已读链已审）。本轮：admin message_service 群发
（send_message 三模式/list_messages/mark_message_read/delete_message/send_overdue_reminders）——
目标校验、组值白名单、触达一致性。

## 结果

- **发现 1 项**：F-079（P3）群发 target_role_groups 无白名单校验——无效组值消息无人收到
- **clean 1 项**：C-137 消息管理端其余面正常（目标校验/列表/软删）

---

## [F-20260808-079] send_message 群发 target_role_groups 无白名单校验——无效组值群发无人收到 — P3

- **级别**: P3（观察项；管理端输入校验缺失，消息触达失败；与 R22 F-070 分组映射衔接）
- **维度**: 4 API 契约（输入校验面）
- **文件**: `backend/domain/admin/services/message_service.py:89-95`（send_message 群发）/ `backend/domain/message/service.py:15-26`（_USER_GROUP_MAP）
- **事实**:
  - send_message 群发（L89-95）：`groups = target_role_groups or ["trial", "observation", "member"]`——**target_role_groups 无白名单校验**，可传任意字符串列表
  - 用户侧接收（message/service.py _get_user_groups L25）：`{_USER_GROUP_MAP.get(c.status, "trial")}`——只产生 trial/observation/member 三组值
  - **无效组值场景**：运营群发传 target_role_groups=["member2"]（拼写错误）→ SystemMessage.target_role_codes=["member2"] → 用户侧 _get_user_groups 无 "member2" → **消息无人收到**（静默触达失败）
  - 与 R22 F-070（映射缺口）衔接：即使组值正确，EXPIRED/EXITED/ALUMNI 用户分组映射也有缺口
- **证据**: ① message_service.py:90 无白名单；② message/service.py:25 接收端仅三组值；③ 排重 grep：findings 无"群发组值校验"命中；F-070（分组映射缺口）为接收端面，本项为发送端输入校验面
- **触发**: 运营在管理后台群发消息时 target_role_groups 填错组值 → 群发成功（sent_count 显示）但用户端收不到
- **影响**: 群发消息静默触达失败（运营以为已发但用户收不到）；sent_count 显示 user_count（误导）。无资金/安全。管理端低频 + 运营输入规范则不影响
- **建议**: ① send_message 校验 target_role_groups ⊆ {"trial","observation","member"}（白名单）；② 或 sent_count 改为实际匹配组用户数（与 _get_user_groups 对齐）；③ 与 F-070 一并修复（发送端白名单 + 接收端映射完整性）
- **排重**: 已 grep 确认不在 F-001~078 / C-001~136 中；F-070（接收端映射缺口）不同面；F-051（F1/F4 前端零入口）不涉

---

## [C-20260808-137] 消息管理端其余面（目标校验/列表/软删/提醒） — clean

- **方法**: R44 定向纵深。读 admin message_service.py 全（send_message L17-101/list_messages L102-138/
  mark_message_read L139-153/delete_message L154-168/send_overdue_reminders L169-）+ 排重
- **证据**:
  - **目标校验**：target=user 查 User 存在（L32-38）+ target=teacher 查 Teacher 存在（L47-52）✓
  - **三模式正确**：all（单条 SystemMessage + 组）/user（定向 user_id）/teacher（TeacherMessage）✓
  - **全部老师遍历**：Teacher 表小（老师数少）✓
  - **列表**：分页 + is_deleted==0 ✓
  - **删除**：软删 ✓
  - **逾期提醒**：send_overdue_reminders（borrow 域 R31 已审逾期链）✓
  - **权限**：R11 已核 152 端点 ✓
- **排重**: R44 本轮消息管理端 clean 侧（F-079 组值白名单为唯一缺口）；R22 F-070（接收端映射）互补

---

## R44 完结汇总

- **范围**: message 管理端群发（目标校验/组值/列表/删除）
- **结果**: 发现 1 项（F-079 P3 组值无白名单）+ clean 1 项（C-137）
- **关键结论**:
  - 消息管理端工程正常（目标校验/软删/列表）
  - 唯一缺口：群发组值无白名单校验（无效组值静默触达失败）——与 R22 F-070（接收端映射缺口）构成消息触达链两端问题，建议一并修复
  - 本轮为"发送端-接收端对称性"核对（R22 查接收端，R44 查发送端）
- **累计**: 78 发现（P0:0 / P1:0 / P2:11 / P3:67）+ 134 clean 记录
- **提交**: 见 git log（本轮 rounds/R44 文件 + progress 索引同步更新）
- **R44 收尾结论**: 四十四轮共 78 项发现无 P0/P1；11 项 P2（含 F-077）。R45 候选：继续轮转新面。
