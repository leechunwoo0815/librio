# R78 第七十八轮 dict 内嵌 ORM 序列化全库复查（F-089 同类枚举） — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：C-171 起（本轮零发现）。

## 范围

R78 F-089 同类漏改枚举（模式 1）：全库"service 返回 dict 含 items 值"20 处，逐一核对 items 是 ORM 列表
（序列化失败 500）还是 dict/Pydantic Response（安全）——确认 F-089 是否孤立。

## 结果

- **发现 0 项**
- **clean 1 项**：C-171 dict 内嵌 ORM 面枚举完成——仅 damage（F-089）一处，其余 19 处安全

---

## [C-20260808-171] dict 内嵌 ORM 序列化面（20 处 items 返回点枚举） — clean

- **方法**: R78 定向纵深。python 脚本全库扫"items"返回点（20 处）+ 逐一核对 items 赋值来源（ORM .all() vs dict 构建）+ response_model 核对
- **证据**:
  - **F-089（damage:482）**：items = 查询 ORM 列表直接放 dict + AdminActionResponse 宽松 → 序列化失败（已报 R77，唯一缺陷）
  - **安全 19 处**：
    - 转 dict 构建：system_service:209（循环内 append dict + RecycleBinResponse）、borrow_service:123/192/267（result.append dict）、report_service:109、refund_service:66、teacher_service:82、role_service:46、benefit_transfer_service:75、advancement:831/903/1058（result.append dict，如 list_questions R23 已核 dict 列表）
    - 具体 schema：order_service:126/user_service:130/advancement:579（items=[] dict + 具体响应模型）
    - 已序列化：activity:67（list_activities 返回）、system_service:74（dict）
  - **响应模型**：其余端点均具体 schema（list[SomeResponse]）或 dict 构建——Pydantic 序列化安全 ✓
  - **核心区分**：SQLAlchemy ORM（项目 declarative BaseModel）→ 失败（F-089）；Pydantic Response/dict → 安全（其余）
- **排重**: R78 本轮回调枚举 clean 侧（零新缺陷）；F-089（R77）为唯一 dict 内嵌 ORM 面；C-052（R2 直接返回 ORM 4 处）互补

---

## R78 完结汇总

- **范围**: dict 内嵌 ORM 序列化面全库枚举（20 处）
- **结果**: 发现 0 项 + clean 1 项（C-171）
- **关键结论**:
  - **F-089 为孤立点**：20 处 items 返回中仅 damage get_list 直接放 ORM（其余均 dict/Pydantic 构建安全）
  - 模式 1 复查完成：dict 内嵌 ORM 序列化面无第二处
  - 本轮为合法零发现（铁律 3），但确认 F-089 修复只需改一处
- **累计**: 88 发现（P0:0 / P1:0 / P2:14 / P3:74）+ 168 clean 记录
- **提交**: 见 git log（本轮 rounds/R78 文件 + progress 索引同步更新）
- **R78 收尾结论**: 七十八轮共 88 项发现无 P0/P1；14 项 P2。R79 候选：继续轮转新面。
