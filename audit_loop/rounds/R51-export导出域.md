# R51 第五十一轮 export 导出域 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-082 起 / C-144 起。

## 范围

R51 export 导出域（此前零审查记录——R1 C-100 仅提 CSV 固定名）。export_data（books/users/orders）+
_export_quiz_results + _export_activity_enrollments——模块白名单、敏感字段、CSV 注入、数据范围。

## 结果

- **发现 1 项**：F-082（P3）CSV 导出链——users 导出含 phone/openid 明文 + 用户可控字段无公式注入防护
- **clean 1 项**：C-144 导出域其余面正常（模块白名单/批量预取/limit）

---

## [F-20260808-082] CSV 导出链——users 导出含 phone/openid 明文 + 用户可控字段无公式注入防护 — P3

- **级别**: P3（观察项；管理端 book.export 权限 + CSV 打开场景；敏感数据泄露面 + 公式注入）
- **维度**: 12 安全（敏感数据面 + CSV 注入面）
- **文件**: `backend/domain/admin/services/export_service.py:47-49`（users 导出字段）/ `:109-135`（_export_quiz_results 直接写）/ `:22-82`（export_data）
- **事实**:
  - users 导出字段（L47-49）：`["id", "phone", "parent_name", "openid", "create_time"]`——**手机号 + openid 明文导出**（F-020 日志明文/F-041 openid 日志已报日志面，**导出文件面未报**）
  - **CSV 公式注入**：csv.writer/DictWriter 直接写用户可控字段（quiz_results 的 child.name/book.title L126-133；export_data 的 title/name/phone 等）——**以 `=`/`+`/`-`/`@` 开头的值被 Excel 解析为公式**（如孩子名 `=HYPERLINK(...)`）→ 打开 CSV 时公式执行
  - 数据范围：全量导出 limit(10000)（L55）
- **证据**: ① export_service.py:48 phone/openid 明文；② csv 直接写（L65-71/126-133）无公式注入防护（无 `'` 前缀/转义）；③ 排重 grep：findings 无"CSV 注入/导出敏感"命中（F-020/F-041 为日志面）
- **触发**: ① 运营导出 users CSV → 手机号/openid 明文（敏感信息外泄面）；② 导出 quiz_results CSV（含孩子名）→ Excel 打开时 = 开头公式执行（注入）
- **影响**: 敏感个人信息（手机号/openid）明文 CSV；公式注入（打开 CSV 时执行，管理端本地场景）。无远程攻击（管理端权限 + 本地打开），P3 观察
- **建议**: ① users 导出**移除 openid**（手机号按需脱敏 `138****1234`）；② CSV 注入防护——cell 以 =/+/-/@ 开头时前缀 `'`（标准防注入）；③ 或改用 Excel xlsx 格式（非公式解析）
- **排重**: 已 grep 确认不在 F-001~081 / C-001~143 中；F-020（日志 phone）/F-041（日志 openid）为日志面，本项为导出文件面

---

## [C-20260808-144] 导出域其余面（模块白名单/批量预取/limit） — clean

- **方法**: R51 定向纵深。读 export_service.py 全（export_data/_export_quiz_results/
  _export_activity_enrollments）+ admin_books_router export 端点 + 排重
- **证据**:
  - **模块白名单**：model_map 固定 3 类 + quiz_results/activity_enrollments 分支（L24-58）——无任意模块注入 ✓
  - **批量预取无 N+1**：quiz_results 用 child_ids/book_ids in_ 预取（L90-107）✓
  - **limit 控制**：limit(10000)（L55/87）✓
  - **权限**：require_perm("book.export") + rate_limit(10,60)（admin_books_router.py:393-398）✓
  - **导出内容**：books/orders 字段为业务数据（无敏感）✓
- **排重**: R51 本轮导出域 clean 侧（F-082 敏感字段+公式注入为唯一缺口）

---

## R51 完结汇总

- **范围**: export 导出域（CSV 生成/模块分发/敏感字段/注入）
- **结果**: 发现 1 项（F-082 P3 CSV 导出链）+ clean 1 项（C-144）
- **关键结论**:
  - 导出域工程正常（白名单/批量预取/limit/权限/限流）
  - 唯一缺口：users 导出含 phone/openid 明文 + CSV 公式注入（F-020/F-041 日志面已报，导出文件面为本轮新）
  - 修复成本低（脱敏 + `'` 前缀）
- **累计**: 81 发现（P0:0 / P1:0 / P2:12 / P3:69）+ 141 clean 记录
- **提交**: 见 git log（本轮 rounds/R51 文件 + progress 索引同步更新）
- **R51 收尾结论**: 五十一轮共 81 项发现无 P0/P1；12 项 P2。R52 候选：继续轮转新面。
