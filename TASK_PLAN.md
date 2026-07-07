# MegaWords V3.6 — 任务规划

> **更新日期**: 2026-07-05
> **状态**: 所有架构问题已修复，代码质量达标

---

## 已完成

| 阶段 | 内容 | 状态 |
|------|------|------|
| P0 | 活动取消/签到 API | ✅ |
| P1 | 押金退款校验 | ✅ |
| P2 | 定时任务补充（3个） | ✅ |
| P3 | RBAC 权限拦截 | ✅ |
| P4 | 前端音频伴读改造 | ✅ |
| P5 | 前端分包优化 | ✅ |
| P6 | 清理兼容 shim + 文档更新 | ✅ |
| P7 | 管理端 PC Web 平台 | ✅ |
| P8 | MySQL 迁移 | ✅ |
| P9 | BDD stub 断言补充 | ✅ |
| P10 | 全量审计修复（P0+P1+P2） | ✅ |
| P11 | V3.1 核心域单元测试 | ✅ |
| P12 | borrow_record BDD 修复 | ✅ |
| P13 | 前端关键问题修复 | ✅ |
| P14 | 审计 41 P0 + 38 P1 + 16 P2 修复 | ✅ |
| P15 | 架构改进 8 项任务 | ✅ |
| P16 | 自检遗留问题修复（F1-F4） | ✅ |
| P17 | 体验优化 55/65 项（P0 全部 + P1 部分） | ✅ |
| P18 | 新增 7 个后端 API（消息/回收站/批量导入/导出） | ✅ |
| P19 | 通用组件开发（error-view/empty-state/storage/submit-lock） | ✅ |
| P20 | PC 后台工具（表单校验/批量操作/草稿缓存/Toast） | ✅ |
| P21 | 开发执行手册 25 步全部执行 | ✅ |
| P22 | 剩余 10 项 P1 体验优化全部完成 | ✅ |
| P23 | 深度优化（打卡动画/错题回顾/退款透明/分享兜底/配置分类/权限隐藏） | ✅ |
| P24 | V3.4 新增 9 个管理端页面（消息管理/仪表盘增强等） | ✅ |
| P25 | V3.4 消息管理功能（发送/列表/批量操作） | ✅ |
| P26 | V3.4 仪表盘增强（新增统计字段/实时数据） | ✅ |
| P27 | V3.4 Token 精确校准（--accent: #5560cf）+ 31/31 class 对齐 ≥95% + 0 hardcoded + 0 oklch | ✅ |
| P28 | 管理端 CRUD 全量修复（P0+P1+P2） | ✅ |

---

## 架构改进完成清单

| 任务 | 内容 | 新增文件 | 验证 |
|------|------|----------|------|
| 1 | 声明式归属校验层 | `middleware/ownership.py` | 0 手动校验残留 |
| 2 | 统一配置服务 | `common/config_service.py` | 33 处 ConfigService 引用 |
| 3 | 事件总线事务统一 | `common/events.py` 重写 | 0 should_close |
| 4 | Service 拆分 | `advancement/leaderboard_service.py` | AdvancementService 397 行 |
| 5 | 微信集成改进 | pay_v3.py + subscribe.py | Redis 缓存 + 证书刷新 |
| 6 | 测试治理 | `scripts/check_fake_assertions.py` | CI 脚本通过 |
| 7 | API 契约验证 | `scripts/verify_api_contract.py` | 0 路径不匹配 |
| 8 | 错误处理标准化 | `common/exceptions.py` 补充 | 0 HTTPException + 0 ValueError |
| 9 | 管理端路由拆分 | `admin/routers/` 目录（8 个文件） | 每个文件 < 400 行 |
| 10 | Schema 统一 | `admin_schemas.py`（52 个 Schema） | 全部有 extra="forbid" |
| 11 | N+1 查询修复 | Service 层批量查询 | 0 处 N+1 |
| 12 | 分页统一 | 所有列表接口 | 0 处无分页 |
| 13 | SQL 聚合 | reading-data 使用 func.sum/func.count | 0 处全表加载 |

---

## 验收结果

| 检查项 | 结果 |
|--------|------|
| 单元测试 | 100/100 pass |
| Router 层 ORM 操作 | 0 处 |
| N+1 查询 | 0 处 |
| 无分页列表接口 | 0 个 |
| inline import | 0 处 |
| response_model | 所有路由都有 |
| Schema extra=forbid | 52/52 |
| stub 函数 | 返回 success: false |
| 前端 stub 按钮 | 3 个全部 disabled |
| 前端 API 路径 | 32/32 正常 |
| 管理端页面 | 33 模板（含 base.html），全部 200 OK |
| MySQL 迁移 | 45 张表全部补齐 |
| API 端点 | 167 个（用户端 74 + 管理端 93） |
| 前端页面 | 27 个小程序页面 |
| 前端组件 | 12 个通用组件 |
| PC 后台页面 | 33 个（含 base.html） |
| 页面级 CSS | 31 个 |
| Token 对齐 | --accent: #5560cf ✅ |
| Class 对齐 | 31/31 页 ≥95%（不含 base 模板） ✅ |
| 硬编码颜色 | 0 残留 ✅ |
| oklch | 0 残留 ✅ |

---

## 管理端路由架构

管理端 API 路由已按领域拆分为 8 个文件，统一前缀 `/admin/api`：

| 文件 | 行数 | 职责 |
|------|------|------|
| `admin_venues_router.py` | 58 | 场馆管理 |
| `admin_teachers_router.py` | 139 | 老师管理 + 排班 |
| `admin_activities_router.py` | 101 | 活动管理 |
| `admin_books_router.py` | 205 | 图书 + 副本 + 上传 + 导出 |
| `admin_borrow_router.py` | 254 | 借阅 + 押金 + 预约 |
| `admin_advancement_router.py` | 365 | 级别 + 成就 + 题库 + 审核 |
| `admin_reports_router.py` | 282 | 退款 + 报告 + 阅读数据 |
| `admin_system_router.py` | 298 | 仪表盘 + 配置 + 用户 + 订单 + 管理员 |

---

*任务规划更新完成。所有 P0 + P1 + P2 问题已修复。*
