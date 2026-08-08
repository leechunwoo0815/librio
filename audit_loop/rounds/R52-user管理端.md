# R52 第五十二轮 user 管理端补面（账号迁移/监护人变更）— 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-083 起 / C-145 起。

## 范围

R52 user 管理端补面（admin user_service + guardian_service）。migrate_account（账号迁移）/change_guardian
（监护人变更）/revive_child（复活）/admin CRUD——迁移覆盖完整性、监护人变更校验。

## 结果

- **发现 1 项**：F-083（P3）migrate_account 未迁移 ConsentRecord（user_id 无 FK 声明漏网）——迁移后新账号录音被拒
- **clean 1 项**：C-145 账号迁移/监护人变更其余面正常（4 类迁移覆盖 + 变更校验）

---

## [F-20260808-083] migrate_account 未迁移 ConsentRecord——账号迁移后语音同意记录残留旧账号，新账号录音被拒 — P3

- **级别**: P3（观察项；账号迁移低频 + 影响录音功能非资金）
- **维度**: 8.3 软删一致性 × 数据完整性（交叉维度；user_id 无 FK 声明漏网）
- **文件**: `backend/domain/admin/services/guardian_service.py:29-88`（migrate_account 迁 4 类）/
  `backend/domain/user/consent_model.py:23`（ConsentRecord.user_id 无 ForeignKey）
- **事实**:
  - migrate_account（L53-75）迁移 4 类 user_id 关联：Child/Order/RefundApplication/SystemMessage
  - 全库 user_id FK 声明表仅 4 类（order/message/refund/child）——**ConsentRecord.user_id 无 ForeignKey 声明**（consent_model.py:23 仅 Column + index）→ migrate_account 未覆盖
  - **影响链**：账号迁移后 ConsentRecord.user_id 仍指向旧账号 → 新账号 `consent_repo.get_latest_valid(user_id, VOICE)`（R9 C-102 save_recording L461-470 已审）查不到 → **新账号录音被拒（voice_consent_required）**——用户需重新同意语音政策
- **证据**: ① guardian_service.py:53-75 仅迁 4 类；② consent_model.py:23 无 FK；③ 排重 grep：findings 无"migrate/consent 迁移"命中
- **触发**: 运营执行 F1 账号迁移（换微信/openid）→ 该账号此前已同意语音数据收集 → 迁移后新账号录音功能被拒（需重新同意）
- **影响**: 账号迁移后语音同意记录丢失（新账号需重新授权，录音功能暂时不可用）；无资金/安全。迁移低频（换微信场景），P3 观察
- **建议**: ① migrate_account 补迁 ConsentRecord（`update({user_id: new_user_id})` where old_user_id）；② 或 consent 查询改为"user_id OR 该 user 任一 child 的旧 user_id"兜底；③ 全库核对"无 FK 声明的 user_id 列"（consent 为唯一漏网）
- **排重**: 已 grep 确认不在 F-001~082 / C-001~144 中；R9（consent 校验链）为本项影响链上游

---

## [C-20260808-145] 账号迁移/监护人变更其余面（4 类覆盖/变更校验） — clean

- **方法**: R52 定向纵深。读 guardian_service.py 全（migrate_account L29-88/change_guardian L94-140/
  revive_child L141-）+ user_service（admin CRUD）+ 排重
- **证据**:
  - **4 类迁移覆盖**：全库 user_id FK 声明表仅 4 类（order/message/refund/child），migrate_account 全迁 ✓（F-083 为无 FK 声明的 consent 漏网）
  - **change_guardian**：confirmed 二次确认 + with_for_update + 新监护人存在校验 + 非同一人守卫 ✓
  - **revive_child**：require_super_admin（R11 已核）+ confirmed + F13（R35 已审复活链）✓
  - **admin CRUD**：create/update/delete child/user 权限齐（R11 已核 152 端点）✓
  - **批量预取**：list_users_with_children 批量（R2 C-082 已分类）✓
- **排重**: R52 本轮管理端 clean 侧（F-083 consent 漏迁为唯一缺口）；F-025（N+1）/F-077（登录链）已报不重

---

## R52 完结汇总

- **范围**: user 管理端（账号迁移/监护人变更/复活）
- **结果**: 发现 1 项（F-083 P3 consent 漏迁）+ clean 1 项（C-145）
- **关键结论**:
  - 账号迁移工程正常（4 类 user_id FK 表全迁 + 变更校验 + 双确认）
  - 唯一缺口：ConsentRecord.user_id 无 FK 声明漏出迁移清单——迁移后语音同意丢失（录音被拒）；修复成本极低（补迁一行）
  - 本项为"无 FK 声明列漏网"核对发现（R13 F-063 assessment 同类核对方法）
- **累计**: 82 发现（P0:0 / P1:0 / P2:12 / P3:70）+ 142 clean 记录
- **提交**: 见 git log（本轮 rounds/R52 文件 + progress 索引同步更新）
- **R52 收尾结论**: 五十二轮共 82 项发现无 P0/P1；12 项 P2。R53 候选：继续轮转新面。
