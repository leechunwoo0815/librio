# DmkWords (librio) — 项目概览

> 最后更新：2026-07-21 | 版本：V3.11 — T3.6a 图书损坏定责完成

## 一句话

DmkWords 是一个 OMO（Online-Merge-Offline）儿童英语分级阅读平台，微信小程序+PC 管理后台，服务线下门店的借阅+会员+测评一体化系统。

## 核心指标

| 指标 | 数值 |
|------|------|
| 测试（pytest 本地/CI） | **294** passed / 5 skipped 本地 |
| BDD（behave） | 151 scenarios / 1030 steps |
| 代码规范（ruff） | 0 errors |
| 数据库迁移（alembic） | clean |
| DB 表 | 54 |
| 后端 API 端点 | 184+ |
| 后端领域模块 | 27 |
| 定时任务 | 15 |
| 小程序页面 | 31 |
| 小程序组件 | 12 |
| PC 管理端模板 | 37（含 base.html） |
| 管理端 CSS 文件 | 33 |
| 动态配置项 | 37 |

## 近期交付（2026-07-21）

| 交付项 | 状态 | 详情 |
|--------|------|------|
| T3.6a 图书损坏定责 | ✅ 交付+审核通过 | 三级定级 + D05丢失联动 + 冲正回滚 + 申诉窗口 + 定时过期确认 + RBAC + 家长通知 + 9单元测试 |
| 安全审计修复 | ✅ 7/7 闭合 | P0 4 项 + P1 3 项 |
| PRD 功能 | ✅ 完整 | QR 码、生词高亮、季度/半年会员、权益转让 |
| 生产就绪 Phase 1 | ✅ 完成 | .env 修正、DEBUG=false 启动成功 |
| 性能 N+1 | ✅ 19 处修复 | 原 8 处 + 新增 11 处 |
| 前端打磨 | ✅ 完成 | 弯引号支持、空文本兜底 |
| SMS SDK | ✅ 已实现 | 腾讯云 + 阿里云（需真实凭据上线） |
| 测试覆盖 | ✅ +10 | test_admin_services.py (10) + profile 批量测试 |
| 微信合规审计 | ✅ 通过 | 10 项修复 + 文件上传中危 2 项修复 |
| 日志覆盖审计 | ✅ 全域覆盖 | 安全路径 5 项 + 真吞异常排查 10 处 |
| 第三方终审修复 | ✅ 9/9 闭合 | P0 5 项(架构/业务/合规) + P1 4 项(运维/XSS/押金) |
| 专家意见交付 | ✅ 4 份可执行文件 | P0 修复指南 + P1 修复指南 + P2 优化建议 + README |
| 施工指令执行 | ✅ 6/6 完成 | 3 P1 + 5 P2 timer + 1 P2 风格 — 全部落地 |
| 零宕机审查 | ✅ 8/8 根因验证+修复 | F6 F5 F3 F2 F1 F4 S1 S2 — 6 fatal + 2 serious 全部修复 |
| 新增测试 | ✅ +1 | test_pay_deposit_returns_pay_params |
| 内联脚本 Phase 1 | ✅ 29 模板提取 | 内联 `<script>` → 34 个 page JS + base-init.js |
| 内联脚本 Phase 2 | ✅ 7 模板 onclick 清零 | books/borrow/activities/orders/reports/levels/users → data-pg 委托 |
| IIFE 全覆盖 | ✅ 34/34 | 所有 page JS 文件全文件 IIFE 包裹，3 轮终审通过 |
| R-1 押金回调修复 | ✅ | deposit/router.py 双重 分→元 转换修复 |
| R-3 订单回调 P0 修复 | ✅ | order/router.py 双重转换修复，全库 Decimal(/100) 清零 |
| 新单测加密分支 | ✅ | test_order_callback_via_encrypted_branch 覆盖真实网关路径 |
| 集成测试 | ✅ 55/55 | Flow 6 适配 REFUND_PENDING 审批流 |

## 架构分层

Router (FastAPI) → Service (业务逻辑) → Repository (SQLAlchemy 2.0) → Model (ORM)
跨域：EventBus + ConfigService + Ownership middleware
网关：PaymentGateway (WeChat Pay / Mock) + SmsGateway (Tencent / Aliyun / Mock)

## 运行命令

```bash
venv/bin/python -m pytest tests/unit/ -x -q
venv/bin/python -m behave features/ --no-capture -q
venv/bin/ruff check backend/
venv/bin/python -m alembic check
PYTHONPATH=. venv/bin/python -m uvicorn backend.main:app --reload
```

## 关键文档索引

| 文档 | 用途 |
|------|------|
| CLAUDE.md | 项目最高宪法 |
| HANDOFF.md | 会话交接文档 |
| checkpoint.md | 完整项目状态跟踪 |
| ARCHITECTURE.md | 架构设计文档 |
| PRD/DmkWords_V3.5需求文档.md | 完整需求文档 |
| PRD/表结构.md | 数据库表结构 |
| PRD/UML-ER.md | UML 状态图 + ER 图 |
| .ai/context/CONTEXT.md | 领域术语和业务规则 |
| .ai/context/PROJECT_STATUS.md | 项目进度指标 |
