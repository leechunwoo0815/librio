# R34 第三十四轮 user 域补面（登录/token 链）— 审查报告（2026-08-08）

> 轮次文件拆分规范（用户指令 2026-08-08）：一轮一个报告文件。编号延续：F-077 起 / C-127 起。

## 范围

R34 user 域补面（F-003/F-020/F-041/F-051 已审）。本轮换面：登录/token 链（wx_login/phone_login/
find_or_create_by_openid/update_user_phone/change_phone/link_openid/set_current_child）——手机号
换绑与微信登录的身份一致性。

## 结果

- **发现 1 项**：F-077（P2）wx_login phone_code 链——update_user_phone 返回他人用户致 token 身份错乱（账号接管）
- **clean 1 项**：C-127 user 域登录链其余面正常（限流/防占用/查重）

---

## [F-20260808-077] wx_login phone_code 换绑链——手机号已被他人占用时 update_user_phone 返回他人用户，生成他人身份 token（账号接管） — P2

- **级别**: P2（越权身份接管——安全边界突破；触发条件为"微信授权手机号已被另一账号绑定"的常见场景）
- **维度**: 12 安全（身份认证面）
- **文件**: `backend/domain/user/router.py:48-52`（wx_login phone_code 链）/ `backend/domain/user/service.py:100-115`（update_user_phone）
- **事实**:
  - wx_login（router.py:48-52）：`if login_data.phone_code: phone = await WeChatAuth.get_phone_number(...); if phone: user = user_service.update_user_phone(user.id, phone)`——**将 update_user_phone 返回值重新赋值给 user**
  - `update_user_phone`（service.py:100-115）：`existing = get_by_phone(phone)` → **若已存在且非本人 → `return UserResponse.model_validate(existing)`**（L104-105）——返回**他人**用户信息
  - wx_login 随后 `token = create_access_token({"sub": str(user.id), ...})`（L51）——**user 已被替换为他人 → token 为他人身份**
  - 触发链：新微信用户 A（openid 新，find_or_create_by_openid 创建）→ 微信授权手机号 138xxx（已被用户 B 的账号绑定——B 曾手机号登录）→ update_user_phone 返回 B → A 拿到 B 身份 token → **A 接管 B 账号**
  - change_phone（router.py:87-89）有前置防占用（existing 且非本人 → ConflictError）——**wx_login 链无此防占用**（不对称）
- **证据**: ① router.py:48-52 wx_login 赋值链；② service.py:104-105 return existing；③ router.py:87-89 change_phone 防占用对照（wx_login 缺失）；④ 排重 grep：findings 无"手机号接管/账号接管/update_user_phone 返回他人"命中（F-051 为"换绑前端零入口"，不同面；F-041 openid 日志不同面）
- **触发**: 微信用户首次登录（新 openid）且其微信绑定手机号已被其他账号（手机号注册路径）占用——换手机号/家人共用/旧账号未解绑场景
- **影响**: 新用户以他人身份获得 JWT token → 查看/操作他人账号数据（孩子信息/订单/退款）；**账号接管**（越权）。被接管方（B）正常登录后 token_generation 变更会使 A 的 token 失效（缓解），但 A 已可访问 B 数据一段时间；B 无感知
- **建议**: ① wx_login 的 phone_code 链**复用 change_phone 的防占用校验**——phone 已被他人占用时：不更新（保留新用户 openid 账号，手机号留空）或提示用户；② update_user_phone 改为"存在即抛 ConflictError"（不再 return existing），调用方（wx_login）捕获后走"不绑定手机号"分支；③ 或 wx_login 中 phone 换绑后**重新校验 user.id 未被替换**（防御性断言）
- **排重**: 已 grep 确认不在 F-001~076 / C-001~126 中；F-051（换绑前端零入口）不同面；C-030（高敏凭据零日志）不涉

---

## [C-20260808-127] user 域登录链其余面（限流/防占用/查重/当前孩子） — clean

- **方法**: R34 定向纵深。读 user/service.py 全（create_user/find_or_create_by_openid/update_user/update_user_phone/link_openid/set_current_child）+ router.py 全（wx_login/phone_login/change-phone/info/rate_limit）+ 排重
- **证据**:
  - **限流**：wx_login/phone_login 均 `rate_limit(10, 60)`（router.py:32-34/126-128）防爆破 ✓
  - **openid 查重**：find_or_create_by_openid get_by_openid（service.py:68-77）✓（User.openid 唯一性需 DB 约束，R4 契约已核）
  - **change-phone 防占用**：前置 existing 且非本人 → ConflictError（router.py:87-89）✓（F-077 为 wx_login 链缺失）
  - **update_user**：phone 唯一性检查（排除自身，service.py:83-86）✓
  - **set_current_child**：child 归属校验（service.py:124-130）✓
  - **验证码校验**：change-phone/phone_login 均 gateway.verify_code（router.py:83/139）✓
  - **SMS 手机号**：F-020（日志明文）已报；C-030（凭据零日志）✓
  - **F-051**：换绑后端完整前端零入口（已报）排重
- **排重**: R34 本轮 user 域 clean 侧（F-077 账号接管为唯一缺口）；F-003/020/041/051 已报不重

---

## R34 完结汇总

- **范围**: user 域补面（登录/token/手机号换绑/身份一致性）
- **结果**: 发现 1 项（**F-077 P2 账号接管**）+ clean 1 项（C-127）
- **关键结论**:
  - **F-077 是 R10-R34 最严重发现（P2）**：wx_login 的 phone_code 换绑链缺防占用校验（change_phone 有、wx_login 无），手机号被他人绑定时返回他人身份 token——账号接管。修复成本低（wx_login 复用 change_phone 防占用或 update_user_phone 改抛异常）
  - user 域其余面正常（限流/查重/归属/验证码）
  - 本项为"两调用点不对称防护"典型（模式：一处有防占用、一处漏——模式 1 同类漏改）
- **累计**: 76 发现（P0:0 / **P1:0 / P2:11** / P3:65）+ 124 clean 记录
- **提交**: 见 git log（本轮 rounds/R34 文件 + progress 索引同步更新）
- **R34 收尾结论**: 三十四轮共 76 项发现无 P0/P1；**11 项 P2**（F-077 新增，其余 10 项未修）。R35 候选：继续轮转新面。
