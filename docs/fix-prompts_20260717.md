# MegaWords 遗留问题修复开发 Prompt

**生成日期**: 2026-07-17  
**范围**: 前端 P0/P1/P2 + 后端配置种子修复（含新发现的 P1 键名不匹配） + Lint 清理  
**前置条件**: 所有测试已通过（pytest 175/4/0，behave 138/0）
**补充审查**: 齐活林（Qi）— 深度代码核查发现 1 个被遗漏的 P1（seeder 键名不匹配），已纳入 Task 7

---

## 任务总览

| # | 优先级 | 内容 | 状态 | 工作量 | 备注 |
|---|--------|------|------|--------|------|
| 7 | P1 | **修复 seeder 键名不匹配 + 统一种子来源** | ✅ 超额完成 | 15 分钟 | 统一 DEFAULTS + 死键清理 |
| 1 | P0 | 替换 appid 占位符 | ⏳ 待外部 | 5 分钟 | 需从微信公众平台获取真实 appid |
| 2 | P0 | 补全服务协议页内容 | ⏳ 待法务 | 需法务/运营 | 无法生成具有法律效力的文本 |
| 3 | P0 | 填写隐私政策运营主体 | ⏳ 待运营 | 10 分钟 | 需填写与认证主体一致的全称 |
| 4 | P1 | 引入 iconfont 替换 emoji | ✅ 已完成 | 半天 | 285 emoji → 62 icon 类, 31/31 文件, 降级策略 |
| 5 | P2 | reading-stats 折线图恢复 | ⏳ 待产品 | 需产品决策 | — |
| 6 | P2 | 删除 premium-hero::before 伪元素 | ✅ 已完成 | 1 分钟 | 规则块已删除 |
| 8 | 低 | ruff lint 清理（92→0） | ✅ 已完成 | 10 分钟 | 0 errors |

---

## Task 1: 【P0】替换 appid 占位符

**文件**: `frontend/project.config.json:4`

**现状**: `"appid": "wx0000000000000000"`

**操作**: 
1. 在微信公众平台（mp.weixin.qq.com）获取已注册小程序的真实 AppID
2. 替换 `project.config.json` 中的 `appid` 值
3. 检查 `backend/domain/config.py` 中微信支付相关的 `WECHAT_APP_ID` 配置，确保与小程序 AppID 一致

**验证**: `grep -rn "wx0000000000000000" frontend/` 返回空

---

## Task 2: 【P0】补全服务协议页内容

**文件**: `frontend/pages/agreement/service-agreement/service-agreement.wxml`

**现状**: 页面仅含一行占位文本 `服务协议内容`

**操作**:
1. 编写完整的用户服务协议，至少包含以下章节：
   - 服务内容与范围（借阅、会员、阅读打卡等）
   - 用户权利与义务
   - 会员费用与退费规则
   - 押金条款（缴纳、退还条件）
   - 图书损坏/丢失赔偿规则
   - 账号使用规范
   - 服务变更与终止条件
   - 争议解决
2. 使用与 `privacy-policy.wxml` 相同的页面结构和样式类（`section-title`, `agreement-text` 等）
3. 确保退费规则与后端 `RefundService` 逻辑一致（观察期内可退、正式会员按天折算等）

**参考**: `frontend/pages/agreement/privacy-policy/privacy-policy.wxml` 的页面结构

---

## Task 3: 【P0】填写隐私政策运营主体

**文件**: `frontend/pages/agreement/privacy-policy/privacy-policy.wxml:16`

**现状**: `运营主体：【公司全称待补充——请商户在 privacy-policy.wxml 中填入认证主体名称】`

**操作**:
1. 将 `【公司全称待补充...】` 替换为微信认证主体全称（需与小程序后台认证主体一致）
2. 补充联系方式（电话/邮箱/地址）
3. 检查隐私政策中个人信息收集清单是否与实际功能匹配（借阅、支付、短信验证码等）

**注意**: 运营主体名称必须与小程序后台「基本设置 → 主体名称」完全一致，否则审核会被拒。

---

## Task 4: 【P1】引入 iconfont 替换 WXML 中的 emoji

**范围**: 257~285 处 emoji（因扫描口径不同），分布在 31 个 WXML 文件中

> ⚠️ **已执行完成** — 使用优雅降级策略。当前 285 emoji 已全部替换为 `<text class="icon icon-xxx">回退字符</text>`，31/31 文件部署完毕，标签外裸露 emoji = 0。@font-face 已注释待真实 woff2 文件。

**Top 10 文件**:
| emoji 数 | 文件 |
|----------|------|
| 18 | pages/index/index.wxml |
| 17 | pages/shelf/shelf.wxml |
| 17 | pages/activity-pkg/activity-detail/activity-detail.wxml |
| 15 | pages/order-pkg/borrow-history/borrow-history.wxml |
| 15 | pages/member/member.wxml |
| 13 | pages/order-pkg/official/official.wxml |
| 13 | pages/reading-pkg/quiz-result/quiz-result.wxml |
| 12 | pages/reading-pkg/reader/reader.wxml |
| 11 | pages/member-pkg/reading-stats/reading-stats.wxml |
| 11 | pages/member-pkg/observation-report/observation-report.wxml |

**操作**:
1. 在 [iconfont.cn](https://www.iconfont.cn) 创建项目，挑选图标集（建议使用 Material Symbols 或 Ant Design 图标库）
2. 下载 iconfont 字体文件，放置到 `frontend/static/iconfont/` 目录
3. 在 `app.wxss` 中引入：
   ```css
   @font-face {
     font-family: 'iconfont';
     src: url('/static/iconfont/iconfont.woff2') format('woff2');
   }
   .icon { font-family: 'iconfont'; }
   ```
4. 定义图标类名映射表（如 `icon-book` → `\ue001`）
5. 批量替换 WXML 中的 emoji 为 `<text class="icon icon-xxx"></text>`
6. 调整对应 WXSS 中 `.icon` 的 `font-size`、`color` 等属性以匹配原 emoji 视觉效果

**替换映射建议**:
| 常见 emoji | iconfont 类名 | 用途 |
|-----------|--------------|------|
| 📚 | icon-book | 书籍/书架 |
| 🏆 | icon-trophy | 成就/排名 |
| 📖 | icon-book-open | 阅读 |
| ⭐ | icon-star | 收藏/评分 |
| 🎫 | icon-ticket | 优惠券 |
| 📅 | icon-calendar | 日期 |
| 🔔 | icon-bell | 通知 |
| 👤 | icon-user | 个人中心 |
| ✅ | icon-check | 完成/通过 |
| ❌ | icon-close | 取消/错误 |

**验证**: 
```python
# 验证脚本
python3 -c "
import os, re
emoji_pattern = re.compile('['
    '\U0001F300-\U0001F9FF\U00002600-\U000026FF\U00002700-\U000027BF'
    '\U0001F600-\U0001F64F\U0001F680-\U0001F6FF'
']')
count = 0
for root, _, files in os.walk('frontend/pages'):
    for f in files:
        if f.endswith('.wxml'):
            with open(os.path.join(root, f)) as fh:
                count += len(emoji_pattern.findall(fh.read()))
print(f'Remaining emoji: {count}')
"
# 期望输出: Remaining emoji: 0
```

---

## Task 5: 【P2】reading-stats 折线图恢复

**文件**: 
- `frontend/pages/member-pkg/reading-stats/reading-stats.wxml:154-165`
- `frontend/pages/member-pkg/reading-stats/reading-stats.js:44-60`
- `frontend/pages/member-pkg/reading-stats/reading-stats.wxss:459-515`

**现状**: 阅读时长趋势使用 CSS bar chart（`bar-col` / `bar-fill`），原型设计为折线图。WXML 中有一个隐藏的 `line-chart` 类（第 3 行）。

**操作**:
> ⚠️ **需产品确认**: 是否恢复为折线图。如果产品确认保留柱状图，直接删除隐藏的 `line-chart` 类即可关闭此 issue。

**若恢复为折线图**:
1. 引入轻量 canvas 绘图方案（推荐 [wx-f2](https://github.com/antvis/wx-f2) 或手写 canvas 2D API）
2. 在 `reading-stats.json` 中声明 canvas 组件：
   ```json
   { "usingComponents": {} }
   ```
3. 在 WXML 中替换 `bar-chart-wrap` 区域为：
   ```html
   <view class="chart-card" wx:if="{{trend.length > 0}}">
     <text class="chart-title">阅读时长趋势（近7天）</text>
     <canvas type="2d" id="readingChart" class="chart-canvas"></canvas>
   </view>
   ```
4. 在 JS `onReady` 中初始化 canvas，根据 `trend` 数据绘制折线图
5. 删除 `bar-chart-wrap` / `bar-col` / `bar-fill` / `bar-value` 相关 WXSS
6. 同步处理词汇趋势图（`word-trend` 部分）

---

## Task 6: 【P2】清理 premium-hero::before 伪元素

**文件**: `frontend/pages/order-pkg/official/official.wxss:425-433`

**现状**:
```css
.premium-hero::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -30%;
  width: 400rpx;
  height: 400rpx;
  background: radial-gradient(circle, rgba(var(--warning-rgb), 0.1) 0%, transparent 70%);
  border-radius: 50%;
}
```

**操作**: 直接删除 `.premium-hero::before` 规则块（425-433 行），不影响功能。

**验证**: `grep -n "premium-hero::before" frontend/pages/order-pkg/official/official.wxss` 返回空

---

## Task 7: 【P1→修复后降为完成】修复 seed_default_configs — 键名不匹配 + 补全缺失键

**文件**: `backend/seeds/seed_rbac.py:300-324`

### 🔴 首先修复：2 个键名不匹配 bug（P1，未被之前任何审查发现）

当前 seeder 中的 2 个键名与代码读取的键名**不一致**：

| seeder 键名 (seed_rbac.py) | 代码读取键名 (order/service.py:82-83) | 匹配? |
|---------------------------|--------------------------------------|-------|
| `observation_price` | `price_observation` | ❌ |
| `official_member_price` | `price_official_member` | ❌ |

**影响**: Seeder 写入的 `observation_price` 和 `official_member_price` 是**死数据**——代码查询 `price_observation` 和 `price_official_member` 找不到，永远走硬编码 fallback。管理员通过 UI 修改价格后才生效。

### 🟡 其次修复：27 个缺失的配置键（含原始报告列出的 7 个）

当前 seeder 仅初始化 8 个键，`SystemConfig.DEFAULTS`（`admin/models.py:77`）定义了 35 个键。缺失 27 个。

### 🟡 额外修复：config_type 不一致

| 位置 | type | 值格式 |
|------|------|--------|
| seeder:302-311 | `"decimal"` | `"500.00"` |
| DEFAULTS:124-128 | `"string"` | `"500"` |

两者 `ConfigService._parse_value()` 都能解析（都用 `Decimal(value)`），但管理端按 `config_type` 渲染表单控件时可能表现不一致。

### ⭐ 推荐方案：统一种子来源（一劳永逸）

**不要手动逐个添加键名**——用 `SystemConfig.DEFAULTS` 作为唯一来源，永久消除 seeder 与 DEFAULTS 不一致的风险：

```python
def seed_default_configs(db: Session):
    """幂等初始化系统配置默认值 — 来源: SystemConfig.DEFAULTS"""
    from backend.domain.admin.models import SystemConfig
    
    for key, (value, typ, desc) in SystemConfig.DEFAULTS.items():
        existing = db.query(SystemConfig).filter(
            SystemConfig.config_key == key,
            SystemConfig.is_deleted == 0,
        ).first()
        if not existing:
            db.add(SystemConfig(
                config_key=key,
                config_value=value,
                config_type=typ,
                description=desc,
            ))
    db.flush()
```

这个方案自动解决上述 3 个问题：
1. ✅ 键名自动匹配（来自 DEFAULTS）
2. ✅ 全部 35 个键自动补全（不用手动列 27 个）
3. ✅ config_type 自动一致

### 验证

```bash
# 运行种子
.venv/bin/python -m backend.seeds.seed_rbac

# 验证关键价格键名
.venv/bin/python -c "
from backend.core.database import get_session
from backend.domain.admin.models import SystemConfig
db = next(get_session())
keys = [c.config_key for c in db.query(SystemConfig).filter(SystemConfig.is_deleted==0).all()]
# 确认使用了正确键名
assert 'price_observation' in keys, 'price_observation 缺失！'
assert 'price_official_member' in keys, 'price_official_member 缺失！'
# 确认死数据键不存在
assert 'observation_price' not in keys, '旧键名 observation_price 未清理！'
assert 'official_member_price' not in keys, '旧键名 official_member_price 未清理！'
print(f'✅ 全部通过 — {len(keys)} 个配置键')
"

# 如果有旧部署数据，清理旧键名
.venv/bin/python -c "
from backend.core.database import get_session
from backend.domain.admin.models import SystemConfig
db = next(get_session())
dead = db.query(SystemConfig).filter(
    SystemConfig.config_key.in_(['observation_price', 'official_member_price']),
    SystemConfig.is_deleted == 0,
).all()
for c in dead:
    c.is_deleted = 1
db.commit()
print(f'清理了 {len(dead)} 条旧键名记录')
"
```

---

## Task 8: 【低】清理 ruff lint 错误

**现状**: 92 个错误
- 72 × E702（测试文件中分号多语句）
- 17 × F401（未使用导入，可 `--fix` 自动修复）
- 2 × F841（未使用变量）
- 1 × E701（冒号多语句）

**操作**:
```bash
# Step 1: 自动修复 17 个未使用导入
cd /Users/litianyu/cc-projects/librio
ruff check backend/ tests/ --fix

# Step 2: 手动修复 F841 和 E701（3 个文件）
ruff check backend/ tests/ --select F841,E701 --output-format concise

# Step 3: 批量修复 E702（测试文件分号）
# 这些是测试 setup 中用 ; 分隔多条语句，改为换行即可
ruff check tests/ --select E702 --fix  # 如果无法自动修复，需手动改分号为换行
```

**验证**: `ruff check backend/ tests/` 返回 `All checks passed!`

---

## 执行顺序建议

1. **Task 7**（配置种子 — **含 P1 键名不匹配修复**）— 后端改动，立即运行测试验证。优先级提升原因：seeder 键名 bug 导致价格配置写入死数据。
2. **Task 8**（lint 清理）— 机械操作，`--fix` 优先
3. **Task 6**（premium-hero 清理）— 一行删除
4. **Task 2 + Task 3**（服务协议 + 隐私政策）— 需运营/法务内容
5. **Task 1**（appid 替换）— 提审前最后一步
6. **Task 4**（iconfont）— 工作量最大，可与上述并行
7. **Task 5**（折线图）— 需产品决策后执行

### 补充审查发现（来自齐活林的深度核查）

| 发现 | 严重等级 | 已纳入 Task |
|------|---------|------------|
| seeder 键名不匹配: `observation_price`≠`price_observation`, `official_member_price`≠`price_official_member` | P1 | Task 7 ✅ |
| seeder 仅 8/35 键, 缺失 27 个（非报告中说的 7 个） | P2 | Task 7 ✅（统一来源方案自动覆盖） |
| seeder `config_type="decimal"` vs DEFAULTS `config_type="string"` 不一致 | P2 | Task 7 ✅（统一来源方案自动修复） |
| `due_remind_days`/`member_expire_remind_days`/`observation_remind_days` 在 scheduler.py 中正确连接 | ✅ 无问题 | 无需行动 |

---

## 全量测试命令

每完成一个 Task 后运行：

```bash
cd /Users/litianyu/cc-projects/librio

# 后端测试
.venv/bin/python -m pytest tests/ --tb=short -q
# 期望: 178+ passed, 0 failed

# BDD 测试
.venv/bin/python -m behave
# 期望: 16 features passed, 0 failed

# Lint 检查
ruff check backend/ tests/
# 期望: All checks passed!

# 前端 emoji 检查
python3 -c "
import os, re
emoji_pattern = re.compile('[\U0001F300-\U0001F9FF\U00002600-\U000026FF\U00002700-\U000027BF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF]')
count = sum(len(emoji_pattern.findall(open(os.path.join(r,f)).read())) for r,_,fs in os.walk('frontend/pages') for f in fs if f.endswith('.wxml'))
print(f'Emoji: {count}')
"
```
