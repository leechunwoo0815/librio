# R49 第四十九轮 dictionary 词典域 — 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-081 起 / C-142 起。

## 范围

R49 dictionary 词典域（此前仅 R30 顺带看 create_word 唯一约束）。全 service（search_words/get_word/
create_word/update_word/delete_word）——输入校验、唯一约束兜底一致性、软删过滤。

## 结果

- **发现 1 项**：F-081（P3）update_word 改 word 撞唯一约束未捕获 IntegrityError → 500（create 有兜底 update 无）
- **clean 1 项**：C-142 词典域其余面正常（escape_like/分页/软删）

---

## [F-20260808-081] update_word 改 word 撞唯一约束未捕获 IntegrityError → 500（create 有兜底 update 无，同类漏改） — P3

- **级别**: P3（观察项；管理端输入导致 500，无数据损坏；create 有兜底 update 无——不对称）
- **维度**: 4 API 契约（异常处理一致性）
- **文件**: `backend/domain/dictionary/service.py:121-141`（update_word）/ `:92-119`（create_word 对照）
- **事实**:
  - `create_word`（L92-119）：查重 + `try: commit() except IntegrityError: rollback + "已存在（并发创建）"`（L113-118）——**唯一约束冲突有兜底** ✓
  - `update_word`（L121-141）：改 `word.word`（L130-131，可改为已存在单词）→ L139 `self.db.commit()`——**无 try/except IntegrityError 兜底**（不对称）
  - **触发**：运营把单词 A 改为单词 B（B 已存在）→ DictionaryWord.word 唯一约束冲突 → 未捕获 IntegrityError → **500**
  - 附带：update_word 查询无 is_deleted 过滤（L124-126 仅 id）——可更新已软删词条（无害，get_word 后拒）
- **证据**: ① service.py:113-118 create 有兜底 vs :139 update 无（同文件不对称）；② 排重 grep：findings 无 dictionary update 命中；R30（create_word 唯一约束）已确认 create 安全，本项为 update 面
- **触发**: 管理后台编辑词条将其 word 改为已存在的其他单词
- **影响**: 500 错误（运营操作报错）；事务回滚无数据损坏；下次请求正常。管理端低频 + 运营输入规范则不影响
- **建议**: ① update_word 加 `try: commit() except IntegrityError: rollback + ValidationError("单词已存在")`（对齐 create_word L113-118）；② 或 update 前查重（排除自身）；③ update_word 查询补 is_deleted==0 过滤（一致性）
- **排重**: 已 grep 确认不在 F-001~080 / C-001~141 中；R30（create_word 唯一约束）互补；F-053 系列（无锁）不涉

---

## [C-20260808-142] 词典域其余面（escape_like/分页/软删/查询） — clean

- **方法**: R49 定向纵深。读 dictionary/service.py 全 145 行 + schemas.py + 排重
- **证据**:
  - **search_words**：escape_like 双字段（word + chinese_meaning，L35-40）+ 分页（offset/limit）+ is_deleted==0 ✓
  - **get_word**：is_deleted==0 ✓
  - **delete_word**：软删（is_deleted=1）✓
  - **create_word**：唯一约束 + IntegrityError 兜底（R30 已确认）✓
  - **字段映射**：pos/cn_definition/ar_level 映射正确 ✓
  - **排序**：order_by word ✓
- **排重**: R49 本轮词典域 clean 侧（F-081 update 兜底缺失为唯一缺口）

---

## R49 完结汇总

- **范围**: dictionary 词典域（搜索/CRUD/唯一约束一致性）
- **结果**: 发现 1 项（F-081 P3 update 撞唯一约束 500）+ clean 1 项（C-142）
- **关键结论**:
  - 词典域工程正常（escape_like/分页/软删/create 兜底）
  - 唯一缺口：update_word 改 word 撞唯一约束无 IntegrityError 兜底（create 有 update 无——同文件不对称，修复成本极低）
- **累计**: 80 发现（P0:0 / P1:0 / P2:12 / P3:68）+ 139 clean 记录
- **提交**: 见 git log（本轮 rounds/R49 文件 + progress 索引同步更新）
- **R49 收尾结论**: 四十九轮共 80 项发现无 P0/P1；12 项 P2（含 F-077/F-080）。R50 候选：继续轮转新面。
