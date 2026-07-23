# 儿童隐私合规设计文档

**编制日期**: 2026-07-21  
**项目**: DmkWords (librio)  
**适用法规**: 《儿童个人信息网络保护规定》(2019.8.10 施行)、《个人信息保护法》(2021.11.1 施行)、《未成年人保护法》  
**约束**: 仅设计文档，不改动代码

---

## 一、法规要点摘要

### 1.1 核心条款

| 法规 | 条款 | 要求 | 当前状态 |
|------|------|------|---------|
| 儿童保护规定 | 第 8 条 | 收集不满 14 周岁儿童个人信息应征得监护人同意 | ❌ 无监护人同意环节 |
| 儿童保护规定 | 第 9 条 | 监护人应如实填写儿童个人信息 | ⚠️ 无身份核验 |
| 儿童保护规定 | 第 11 条 | 不得收集与所提供服务无关的儿童个人信息 | ⚠️ 未做字段级审查 |
| 儿童保护规定 | 第 15 条 | 监护人有权删除儿童个人信息 | ⚠️ 仅有软删除，无级联清理 |
| 个人信息保护法 | 第 31 条 | 处理不满 14 周岁未成年人个人信息应取得监护人同意 | ❌ 同上 |
| 未成年人保护法 | 第 72 条 | 处理未成年人个人信息应遵循必要性原则 | ⚠️ 未做必要性评估 |

### 1.2 关键定义

- **儿童**: 不满 14 周岁的未成年人
- **监护人**: 父母或其他法定代理人
- **明示同意**: 监护人通过主动行为（勾选+确认、签名等）表达同意，非默认勾选
- **可撤回**: 监护人有权随时撤回同意，并要求删除数据

---

## 二、当前数据收集清单（实测）

### 2.1 儿童信息收集字段

**数据来源**: `backend/domain/child/models.py` (实测)

| # | 字段 | 类型 | 用途 | 必要性评估 | 敏感度 |
|---|------|------|------|----------|--------|
| 1 | `name` | String(50) | 孩子中文姓名 | ✅ 必要（借阅管理） | 🟡 中 |
| 2 | `english_name` | String(50) | 孩子英文姓名 | ⚠️ 可选 | 🟡 中 |
| 3 | `age` | SmallInteger | 孩子年龄(3-15) | ✅ 必要（分级推荐） | 🟡 中 |
| 4 | `grade` | String(20) | 年级 | ✅ 必要（分级推荐） | 🟢 低 |
| 5 | `status` | SmallInteger | 会员状态(0-5) | ✅ 必要（业务流转） | 🟢 低 |
| 6 | `member_start_time` | DateTime | 会员开始时间 | ✅ 必要（权益管理） | 🟢 低 |
| 7 | `member_expire_time` | DateTime | 会员到期时间 | ✅ 必要（权益管理） | 🟢 低 |
| 8 | `ar_level` | Numeric(3,1) | AR 阅读等级 | ✅ 必要（分级阅读） | 🟢 低 |
| 9 | `teacher_id` | BigInteger | 指导老师 ID | ✅ 必要（师生匹配） | 🟢 低 |
| 10 | `venue_id` | BigInteger | 所属场馆 ID | ✅ 必要（多场馆） | 🟢 低 |
| 11 | `total_reading_minutes` | Integer | 累计阅读分钟 | ✅ 必要（统计报告） | 🟢 低 |
| 12 | `total_words_read` | Integer | 累计阅读词数 | ✅ 必要（统计报告） | 🟢 低 |
| 13 | `total_books_finished` | Integer | 累计读完本数 | ✅ 必要（统计报告） | 🟢 低 |
| 14 | `current_streak_days` | Integer | 连续打卡天数 | ✅ 必要（激励机制） | 🟢 低 |
| 15 | `longest_streak_days` | Integer | 最长连续打卡 | ✅ 必要（激励机制） | 🟢 低 |
| 16 | `deposit_status` | SmallInteger | 押金状态 | ✅ 必要（资金管理） | 🟢 低 |
| 17 | `outstanding_fines` | Numeric(10,2) | 未缴罚款 | ✅ 必要（资金管理） | 🟡 中 |
| 18 | `current_level_id` | BigInteger | 当前晋级级别 | ✅ 必要（晋级体系） | 🟢 低 |

### 2.2 间接收集的儿童信息

| # | 数据 | 来源 | 存储位置 | 敏感度 |
|---|------|------|---------|--------|
| 1 | 语音录音 | `voice_recording` 表 (audio_url, text_content) | uploads/voice/ + DB | 🔴 高（生物特征） |
| 2 | 损坏照片 | `book_damage_report.photo_url` | uploads/damage/ + DB | 🟡 中（可能含孩子手部等） |
| 3 | 阅读记录 | `reading_session`, `reading_progress` | DB | 🟡 中 |
| 4 | 测验成绩 | `quiz`, `quiz_answer` | DB | 🟡 中 |
| 5 | 查词记录 | `user_vocabulary` | DB | 🟢 低 |
| 6 | 打卡记录 | `check_in` | DB | 🟢 低 |
| 7 | 阅读报告 | `learning_report`, `observation_report` | DB | 🟡 中 |
| 8 | 图书封面 | `book.cover_url` | uploads/cover/ + DB | 🟢 低 |

### 2.3 监护人信息收集字段

**数据来源**: `backend/domain/user/models.py`

| # | 字段 | 类型 | 用途 | 敏感度 |
|---|------|------|------|--------|
| 1 | `parent_name` | String(50) | 家长姓名 | 🟡 中 |
| 2 | `phone` | String(11) | 手机号 | 🔴 高 |
| 3 | `openid` | String(100) | 微信 OpenID | 🟡 中 |
| 4 | `unionid` | String(100) | 微信 UnionID | 🟡 中 |
| 5 | `avatar` | String(255) | 家长头像 URL | 🟢 低 |

---

## 三、注册流程"监护人同意"环节设计

### 3.1 当前注册流程（实测）

```
微信小程序登录 → wx.login() → code2session 获取 openid
→ find_or_create_by_openid() → 创建 User（无任何同意环节）
→ login.wxml 有隐私协议勾选框（privacyChecked）
→ 但仅存储到 wx.setStorageSync('privacy_agreed', checked)
→ 后端无同意记录
```

**问题**: 
1. 隐私勾选仅前端 localStorage 记录，后端无持久化
2. 添加孩子（`child-manage` 页面）时无监护人同意弹窗
3. 语音录音上传时无单独的监护人同意

### 3.2 设计方案：三段式同意

#### 3.2.1 第一段：注册时 — 隐私政策同意

**时机**: 用户首次微信登录时（`find_or_create_by_openid` 创建用户前）  
**前端**: `login.wxml` 已有勾选框 ✅，需增加：
- 勾选后弹出隐私政策全文弹窗（非跳转页面）
- 弹窗底部"我已阅读并同意"按钮
- 点击按钮后调用 `POST /user/consent` 记录同意

**后端新增**:

```sql
-- 同意记录表
CREATE TABLE consent_record (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL COMMENT '用户ID',
    consent_type VARCHAR(50) NOT NULL COMMENT '同意类型: privacy_policy / child_data / voice_recording',
    consent_text_hash VARCHAR(64) NOT NULL COMMENT '同意文案哈希(SHA-256)，用于追溯当时版本',
    consent_version VARCHAR(20) NOT NULL COMMENT '隐私政策版本号',
    ip_address VARCHAR(45) COMMENT 'IP地址',
    user_agent VARCHAR(500) COMMENT 'User-Agent',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    withdrawn_at DATETIME NULL COMMENT '撤回时间',
    INDEX idx_user_type (user_id, consent_type),
    INDEX idx_created (created_at)
) COMMENT='用户同意记录表';
```

**API 设计**:
```
POST /user/consent
  Body: { consent_type: "privacy_policy", consent_version: "v1.0" }
  Response: { success: true, consent_id: 123 }
  逻辑: 记录同意，存储文案哈希用于追溯

GET /user/consent
  Response: { consents: [{ type, version, created_at, withdrawn_at }] }

POST /user/consent/withdraw
  Body: { consent_type: "child_data" }
  逻辑: 标记 withdrawn_at，触发数据删除流程
```

#### 3.2.2 第二段：添加孩子时 — 儿童信息收集同意

**时机**: 用户在 `child-manage` 页面点击"添加孩子"  
**前端**: 在"确认添加"按钮前增加弹窗：

```
┌─────────────────────────────────────┐
│  📋 儿童信息收集同意                  │
│                                     │
│  我们将收集以下儿童信息：              │
│  • 姓名、年龄、年级                  │
│  • 阅读记录、测评成绩                 │
│  • 打卡记录、阅读时长                 │
│                                     │
│  这些信息仅用于：                     │
│  • 分级阅读推荐                      │
│  • 阅读报告生成                      │
│  • 晋级评定                          │
│                                     │
│  您可随时在"设置"中撤回同意并删除数据。  │
│                                     │
│  [不同意]          [同意并继续]        │
└─────────────────────────────────────┘
```

**后端逻辑**:
```
POST /child (创建孩子)
  1. 检查用户是否有有效的 child_data 同意记录
  2. 无则返回 403 + 错误码 "consent_required"
  3. 有则创建孩子
```

#### 3.2.3 第三段：首次录音时 — 语音数据收集同意

**时机**: 用户首次使用朗读功能（`save_recording`）  
**前端**: 首次点击录音按钮时弹窗：

```
┌─────────────────────────────────────┐
│  🎤 语音数据收集同意                  │
│                                     │
│  朗读功能需要录制孩子的语音。           │
│  录音用于：                           │
│  • 朗读打卡                          │
│  • 发音评估                          │
│                                     │
│  录音文件将安全存储，仅您和指导老师     │
│  可查看。录音数据保留 6 个月后自动删除。 │
│                                     │
│  [不同意]          [同意并开始录音]     │
└─────────────────────────────────────┘
```

**后端逻辑**:
```
POST /reading/voice (保存录音)
  1. 检查用户是否有有效的 voice_recording 同意记录
  2. 无则返回 403 + 错误码 "voice_consent_required"
  3. 有则保存录音
```

### 3.3 同意记录字段设计

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | BIGINT PK | 主键 |
| `user_id` | BIGINT FK→user | 监护人用户 ID |
| `consent_type` | VARCHAR(50) | 同意类型（privacy_policy/child_data/voice_recording） |
| `consent_text_hash` | VARCHAR(64) | 同意文案 SHA-256 哈希（追溯当时版本） |
| `consent_version` | VARCHAR(20) | 隐私政策版本号 |
| `ip_address` | VARCHAR(45) | 同意时 IP 地址 |
| `user_agent` | VARCHAR(500) | User-Agent |
| `created_at` | DATETIME | 同意时间 |
| `withdrawn_at` | DATETIME NULL | 撤回时间（NULL=有效） |

---

## 四、数据删除权实现路径

### 4.1 删除请求入口

**设计方案**: 小程序"设置"页面增加"删除孩子数据"入口

```
设置 → 隐私管理 → 删除孩子数据
  → 选择孩子
  → 展示将删除的数据清单
  → 二次确认（输入孩子姓名验证）
  → 提交删除请求
  → 后端异步执行级联删除
  → 完成后通知监护人
```

### 4.2 级联删除清单

**以删除 Child ID=123 为例**:

| # | 表 | 删除条件 | 数据类型 | 特殊处理 |
|---|---|---------|---------|---------|
| 1 | `child` | `id=123` | 核心记录 | 软删除→30天后物理删除 |
| 2 | `reading_session` | `child_id=123` | 阅读会话 | 物理删除 |
| 3 | `reading_progress` | `child_id=123` | 阅读进度 | 物理删除 |
| 4 | `check_in` | `child_id=123` | 打卡记录 | 物理删除 |
| 5 | `voice_recording` | `child_id=123` | 语音录音 | 物理删除 DB + 删除 uploads/voice/ 文件 |
| 6 | `user_vocabulary` | `child_id=123` | 生词本 | 物理删除 |
| 7 | `quiz_answer` | 经 `quiz_id` 级联 | 测验答案 | 物理删除（见 26b 勘误） |
| 8 | `reading_submission` | `child_id=123` | 阅读提交 | 物理删除 |
| 9 | `child_level` | `child_id=123` | 级别记录 | 物理删除 |
| 10 | `child_achievement` | `child_id=123` | 成就记录 | 物理删除 |
| 11 | `level_certificate` | `child_id=123` | 证书 | 物理删除 |
| 12 | `bookshelf` | `child_id=123` | 书架 | 物理删除 |
| 13 | `favorites` | `child_id=123` | 收藏 | 物理删除 |
| 14 | `borrow_record` | `child_id=123` | 借阅记录 | **保留 2 年后删除**（交易凭证） |
| 15 | `deposit_record` | `child_id=123` | 押金记录 | **保留至押金结清后 3 年**（财务合规） |
| 16 | `order` | `child_id=123` | 订单 | **保留 5 年**（交易记录法定保留） |
| 17 | `refund_application` | `child_id=123` | 退款记录 | **保留至退款完成后 3 年** |
| 18 | `activity_enrollment` | `child_id=123` | 活动报名 | 物理删除 |
| 19 | `reservation` | `child_id=123` | 预约 | 物理删除 |
| 20 | `observation_report` | `child_id=123` | 观察期报告 | 物理删除 |
| 21 | `learning_report` | `child_id=123` | 学习报告 | 物理删除 |
| 22 | `ar_evaluation` | `child_id=123` | AR 评估 | 物理删除 |
| 23 | `observation_evaluation` | `child_id=123` | 观察期评估 | 物理删除 |
| 24 | `guidance_record` | `child_id=123` | 指导记录 | 物理删除 |
| 25 | `book_damage_report` | `child_id=123` | 损坏报告 | **保留 2 年**（财务凭证） |
| 26 | ~~`parent_course_time`~~ | — | ~~亲子课时间~~ | **勘误（2026-07-23）**：该表为场馆排期表（venue_id 关联），无 child_id，不属于儿童数据，已从删除清单移除 |
| 26a | `quiz` | `child_id=123` | 测验记录 | 物理删除（原清单遗漏，代码已补） |
| 26b | `quiz_answer` | 经 `quiz_id` 级联 | 测验答案 | 物理删除（无 child_id，经 quiz 关联） |
| 27 | `benefit_transfer_application` | `source_child_id=123 OR target_child_id=123` | 权益转移 | **保留至审核完成后 1 年** |
| 28 | `message_read_status` | 通过 `message_id` 关联 | 消息已读 | 物理删除（通过 user_id） |

**特殊保留项**（法规要求）:
- 交易记录（order, deposit_record, refund_application）需法定保留
- 借阅记录保留 2 年（纠纷举证）
- 损坏报告保留 2 年（财务凭证）

### 4.3 删除流程设计

```
家长发起删除请求
  ↓
后端检查前置条件：
  • 无活跃借阅（BORROWING/OVERDUE 状态）
  • 无待处理押金（deposit_status != PAID_ACTIVE）
  • 无待处理退款
  → 有则拒绝，提示先处理
  ↓
执行软删除 child.is_deleted=1
  ↓
异步任务（24小时内执行）：
  1. 物理删除非财务数据（表 2-13, 18-28）
  2. 删除 uploads/voice/ 下该孩子的音频文件
  3. 保留财务数据（order, deposit, refund, borrow, damage）
  4. 记录删除日志到 operation_log
  ↓
通知监护人删除完成（消息推送）
```

### 4.4 数据导出权

> 《个人信息保护法》第 45 条：个人有权向信息处理者查阅、复制其个人信息。

**设计方案**: 增加 `GET /child/{id}/data-export` API，返回该孩子的所有数据（JSON 格式），供监护人下载。

---

## 五、隐私政策文档补全大纲

### 5.1 占位符清单（实测）

**文件**: `frontend/pages/agreement/privacy-policy/privacy-policy.wxml`

| # | 位置 | 占位内容 | 需补充信息 | 标注 |
|---|------|---------|-----------|------|
| 1 | 第一节"运营主体" | 【公司全称待补充——请商户在 privacy-policy.wxml 中填入认证主体名称】 | 微信认证主体公司全称 | **需商户提供** |
| 2 | 第九节"办学资质" | 【待补充——请商户在此填写办学许可证编号】 | 民办学校办学许可证编号 | **需商户提供** |
| 3 | 第九节"办学资质" | 发证机关：xx 市教育局 | 发证机关全称 | **需商户提供** |
| 4 | 第九节"办学资质" | 【待补充——请商户上传办学许可证扫描件】 | 办学许可证扫描件 URL | **需商户提供** |

### 5.2 需补充的条款

| # | 缺失条款 | 法规依据 | 建议内容 |
|---|---------|---------|---------|
| 1 | **儿童个人信息专门条款** | 儿童保护规定第 8-13 条 | 单独章节说明儿童信息收集目的、范围、使用方式、监护人权利 |
| 2 | **数据保留期限** | 个人信息保护法第 19 条 | 明确各类数据的保留期限（参照本方案 4.2 节） |
| 3 | **数据删除权行权路径** | 儿童保护规定第 15 条 | 说明监护人如何申请删除数据 |
| 4 | **第三方共享清单** | 个人信息保护法第 23 条 | 列明共享的第三方（微信支付、短信服务商）及共享信息范围 |
| 5 | **个人信息出境** | 个人信息保护法第 38-40 条 | 说明是否涉及数据出境（当前: 不涉及） |
| 6 | **自动化决策说明** | 个人信息保护法第 24 条 | 说明推荐算法是否基于自动化决策（当前: AR 等级推荐是规则匹配，非 ML 自动化决策） |
| 7 | **撤回同意路径** | 儿童保护规定第 15 条 | 说明如何在 App 内撤回同意 |

### 5.3 隐私政策版本管理

| 版本 | 日期 | 变更内容 | 状态 |
|------|------|---------|------|
| v1.0 | 上线日 | 初版 | 待发布 |

**版本管理规则**:
- 重大变更（新增收集字段/新增第三方共享）→ 升大版本号 + 重新弹窗同意
- 小幅修订（文案调整/补充说明）→ 升小版本号 + 站内信通知
- 每次变更记录到 `consent_record.consent_version`

---

## 六、合规差距清单

### 6.1 P0 — 法规硬性要求未满足

| # | 差距 | 法规依据 | 修复方案 | 工作量 |
|---|------|---------|---------|--------|
| P0-1 | 无监护人同意记录 | 儿童保护规定第 8 条 | 新增 `consent_record` 表 + 三段式同意流程（本方案第三章） | 3 天 |
| P0-2 | 隐私政策占位符未填 | 个人信息保护法第 17 条 | 商户提供公司全称/许可证信息后填入 | 0.5 天 |
| P0-3 | 无数据删除权行权路径 | 儿童保护规定第 15 条 | 实现"设置→删除孩子数据"入口 + 级联删除（本方案第四章） | 2 天 |
| P0-4 | 隐私政策缺儿童专门条款 | 儿童保护规定第 10 条 | 补充"儿童个人信息保护"专章 | 1 天 |

### 6.2 P1 — 合规建议

| # | 差距 | 法规依据 | 修复方案 | 工作量 |
|---|------|---------|---------|--------|
| P1-1 | 无数据导出功能 | 个人信息保护法第 45 条 | 新增 `GET /child/{id}/data-export` API | 1 天 |
| P1-2 | 无撤回同意机制 | 儿童保护规定第 15 条 | 新增 `POST /user/consent/withdraw` API | 0.5 天 |
| P1-3 | 无第三方共享清单 | 个人信息保护法第 23 条 | 隐私政策补充微信支付/短信服务商共享清单 | 0.5 天 |
| P1-4 | 语音数据无自动过期 | 儿童保护规定第 13 条 | 定时任务清理 6 月前 voice_recording + 文件 | 0.5 天 |
| P1-5 | 无 IP/User-Agent 记录 | 个人信息保护法第 17 条 | 同意时记录 IP 和 UA（本方案 3.3 节） | 0.5 天 |

### 6.3 P2 — 长期优化

| # | 差距 | 建议 |
|---|------|------|
| P2-1 | 无数据分类分级制度 | 建立数据分类分级表，标注每张表的敏感级别 |
| P2-2 | 无个人信息影响评估（PIA） | 上线前完成 PIA 报告 |
| P2-3 | 无数据安全事件应急预案 | 制定数据泄露应急预案 + 24h 报告流程 |
| P2-4 | 无 DPO（数据保护 officer） | 生产环境需指定 DPO |

---

## 七、实现优先级与路线图

```
Phase 1（上线前必须完成）— 预计 7 天
├── P0-1: consent_record 表 + 三段式同意流程      (3天)
├── P0-2: 隐私政策占位符填充                       (0.5天，需商户配合)
├── P0-3: 数据删除权 — 级联删除实现                 (2天)
└── P0-4: 隐私政策补充儿童专门条款                  (1天)

Phase 2（上线后 1 个月内）— 预计 3 天
├── P1-1: 数据导出 API                            (1天)
├── P1-2: 撤回同意 API                            (0.5天)
├── P1-3: 第三方共享清单                           (0.5天)
├── P1-4: 语音数据自动过期                         (0.5天)
└── P1-5: 同意记录 IP/UA                          (0.5天)

Phase 3（上线后 3 个月内）
├── P2-1: 数据分类分级
├── P2-2: PIA 报告
└── P2-3: 数据泄露应急预案
```

---

*设计文档编制时间: 2026-07-21 23:20*  
*编制人: Python 全栈工程师 Agent*  
*数据来源: 代码实测 (backend/domain/child/models.py, user/models.py, reading/models.py, voice/models.py, book/damage_model.py)*
