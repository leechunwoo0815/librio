# 全量静态分析审查报告

> **生成时间**: 2026-07-17 GMT+8  
> **审查工具**: mypy + Bandit + pip-audit + Semgrep  
> **审查范围**: `backend/` + `frontend/` JS（Semgrep）  
> **约束**: 只分析不修改，零回归

---

## 1. mypy — 类型检查

**命令**: `mypy backend/ --ignore-missing-imports --no-strict-optional --check-untyped-defs`

| 指标 | 值 |
|------|-----|
| 检查文件数 | 240 |
| 总错误 | **571** |
| 实际 bug 类 | ~30（其余为 `Column[T]` vs `T` 的 SQLAlchemy 已知假阳性） |

### 代表性真实问题

| 文件 | 行 | 问题 | 风险 |
|------|----|------|------|
| `common/events.py` | 416 | `_record_dead_letter` 第 3 参期望 `str`，传入 `Exception` | **中** — 死信记录会序列化异常对象失败 |
| `reading/schemas.py` | 33 | `int` 赋值给 `Decimal` 字段 | **低** — Pydantic 会做隐式转换 |
| `borrow/schemas.py` | 59 | 同上 | **低** |
| `config_service.py` | 53,131 | `Column[str]` ↔ `str` 赋值混淆 | **低** — 运行时不影响 |
| `dictionary/service.py` | 53-86 | row 元组直接传给 Pydantic 模型，`Column[T]` 未解包 | **低** — Pydantic 容忍 |
| `seed_rbac.py` | 382-471 | ORM 列对象混入业务逻辑 | **低** — 只跑一次 |

### 大量假阳性说明

~540 个错误来自 SQLAlchemy `Column[type]` 在查询结果中未解包为裸 `type`，这是 SQLAlchemy 2.0 与 mypy 的已知间隙。`pip install sqlalchemy2-stubs` 后可用 `Mapped[]` 注解消除，但不影响运行。

---

## 2. Bandit — 安全基线

**命令**: `bandit -r backend/`

| # | 类型 | 文件 | 行 | 描述 | 风险判定 |
|---|------|------|----|------|---------|
| 1 | B110 try_except_pass | `events.py` | 420 | 空 except 吞异常（session cleanup 场景） | **低** — cleanup 正常，但建议至少 log |
| 2 | B311 random | `gateways/sms/mock.py` | 31 | Mock SMS 用 `random.randint` 生成验证码 | **低** — Mock 用途，非生产 |
| 3 | B311 random | `order_service.py` | 297 | 订单号生成用 `random.randint` | **低** — 防碰撞场景，非安全用途 |
| 4 | B311 random | `order/repository.py` | 35 | 同上 | **低** |
| 5 | B105 硬编码 | `config.py` | 114 | `SECRET_KEY` 默认值在守卫语句中被检测 | **假阳性** — 这是防御性检查，不是硬编码 |

**结论**: 全部低危或假阳性，无阻塞。

---

## 3. pip-audit — 依赖审计

**命令**: `pip-audit -r requirements.txt`

| 包 | 版本 | CVE | 说明 | 风险 |
|----|------|-----|------|------|
| `ecdsa` | 0.19.2 | PYSEC-2026-1325 | P-256 曲线时序攻击，可泄露 nonce → 私钥 | **低** — 本项目仅用 ecdsa 做微信支付签名验证，不用于密钥生成；且库作者声明侧信道不在范围 |

**结论**: 无紧急 CVE。生产部署时关注 `ecdsa` 更新即可。

---

## 4. Semgrep — 业务安全

**命令**: `semgrep --config=auto backend/`

| # | 类型 | 文件 | 行 | 问题 | 风险 |
|---|------|------|----|------|------|
| 1 | 不安全 format string | `admin.js` | 24 | `console.log(\`[${category}] ${action}\`, detail)` — 字符串拼接日志格式 | **极低** — 仅 PC 管理台调试日志 |
| 2 | 非字面量 RegExp | `admin.js` | 422 | `new RegExp(pattern)` — pattern 来自用户输入 | **低** — admin 搜索功能，仅管理端可用 |

**结论**: 仅前端 JS 2 项低风险，不影响后端安全。

---

## 5. wechat-devtools MCP

| 条件 | 状态 |
|------|------|
| `mcp-server.js` | ✅ 存在 (4970 bytes) |
| 微信开发者工具 CLI | ❌ 未安装（macOS 缺少 `cmd` 命令行工具） |

**无法执行**。需要先在 macOS 安装微信开发者工具 CLI，然后通过 MCP 调用编译检查。当前环境不支持。

---

## 汇总

| 工具 | 总发现 | 真实 bug | 阻塞 |
|------|--------|---------|------|
| mypy | 571 | ~30（全低/中） | 无 |
| Bandit | 5 | 0 | 无 |
| pip-audit | 1 | 0（CVE 已知 + 低风险） | 无 |
| Semgrep | 2 | 0 | 无 |
| MCP | N/A | 环境缺失 | — |

**结论**: 无新增阻塞 bug。建议关注 mypy 的 `events.py:416`（`Exception`→`str` 类型不匹配）作为下次迭代的 minor 修复项。
