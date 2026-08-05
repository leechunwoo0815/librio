# DmkWords 生产部署检查清单

> 生成日期: 2026-07-13
> 基于 TASK_PLAN.md Phase 4 + 实际代码扫描

---

## □ 1. 外部依赖就绪

| # | 检查项 | 状态 | 操作指引 |
|---|--------|------|---------|
| 1.1 | 微信小程序真实 appid | ⬜ | 替换 `frontend/project.config.json` 中 `YOUR_REAL_APPID_HERE` |
| 1.2 | 短信签名审核通过 | ⬜ | 腾讯云/Aliyun 控制台提交签名审核（1-3 工作日） |
| 1.3 | 短信模板 ID 就绪 | ⬜ | 创建验证码模板并填入 `.env` 的 `SMS_TEMPLATE_CODE` |
| 1.4 | 微信支付商户号开通 | ⬜ | 微信支付商户平台入驻审核（1-5 工作日） |
| 1.5 | APIv3 证书下载 | ⬜ | 下载商户证书 + 平台证书 → 转 PEM 格式 |
| 1.6 | 隐私保护指引提交 | ⬜ | 微信公众平台 → 设置 → 基本设置 → 小程序隐私保护指引 |

---

## □ 2. 环境变量配置

### 2.1 创建 `.env`

```bash
cp .env.example .env
```

### 2.2 必填字段

| 变量 | 说明 | 获取方式 |
|------|------|---------|
| `SECRET_KEY` | JWT 签名密钥（至少 32 字符随机串） | `openssl rand -hex 32` |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | MySQL 连接信息 | DBA 提供 |
| `WECHAT_APP_ID` | 小程序 AppID | 微信公众平台 → 开发 → 开发设置 |
| `WECHAT_APP_SECRET` | 小程序 AppSecret | 微信公众平台 → 开发 → 开发设置 |
| `WECHAT_MCH_ID` | 微信支付商户号 | 微信支付商户平台 |
| `WECHAT_API_KEY_V3` | V3 专用 API 密钥（32 字节） | 微信支付商户平台 → API 安全 |
| `WECHAT_CERT_SERIAL_NO` | 商户证书序列号 | `openssl x509 -in apiclient_cert.pem -noout -serial` |
| `WECHAT_PRIVATE_KEY_PATH` | 商户私钥 PEM 绝对路径 | 证书转换后存放路径 |
| `WECHAT_PLATFORM_CERT_PATH` | 微信平台证书 PEM 绝对路径 | 证书存放路径 |
| `WECHAT_PAY_NOTIFY_URL` | 支付回调 URL | `https://<domain>/order/payment-callback` |
| `WECHAT_REFUND_NOTIFY_URL` | 退款结果通知 URL（F55） | `https://<domain>/refund/callback`（微信 V3 退款接口 notify_url，不配置则收不到退款回调） |
| `SMS_PROVIDER` | `tencent` 或 `aliyun` | 根据所选服务商 |
| `SMS_APP_ID` / `SMS_APP_KEY` | 短信 SDK 凭据 | 腾讯云/Aliyun 控制台 |
| `SMS_SIGN_NAME` | 短信签名 | 审核通过的签名名称 |
| `SMS_TEMPLATE_CODE` | 验证码模板 ID | 审核通过的模板 ID |

### 2.3 安全确认

- [ ] `DEBUG=false`（生产绝不可为 true）
- [ ] `ENABLE_TEST_TOKEN=false`（生产绝不可为 true）
- [ ] `MOCK_PAYMENT=false`（生产绝不可为 true）
- [ ] `MOCK_SMS=false`（生产绝不可为 true）
- [ ] 多实例部署必须 `REDIS_LOCK_FAIL_OPEN=false`（默认 true 为单实例/开发降级；多实例下 Redis 宕机若无锁执行，定时任务会在各实例并发重复跑）
- [ ] 迁移 043（check_in 唯一约束）含历史去重 DELETE：大表执行前评估锁表时长，建议低峰执行
- [ ] 迁移 044（child.exited_at / user.paid_member_ever）含存量回填 UPDATE：同上低峰执行
- [ ] 迁移 045（order.activation_issue）纯加列，低峰执行
- [ ] 迁移 046（borrow_record.fine_in_outstanding + refund_application/deposit_record.out_refund_no）纯加列
- [ ] 迁移 047（original_amount/partial_refund_no + 存量回填 UPDATE）低峰执行
- [ ] 迁移 048（deposit_record.active_child_id 生成列 + 唯一索引）含存量重复活跃押金修复 UPDATE；上线前先核对重复活跃押金
- [ ] 迁移 049（book_waitlist.active_child_book 生成列唯一 + order.trade_no 唯一）低峰执行
- [ ] 种子幂等重跑：`venv/bin/python -m backend.seeds.seed_rbac`（含 migrate_admin_roles——
    F34：旧 admin.role 需回填到 admin_role_id，否则初始超管无法执行会员状态变更/复活）
- [ ] 上线前在微信商户平台核对「退款结果通知」地址已配置为 `WECHAT_REFUND_NOTIFY_URL`（代码层无法确认，F55）
- [ ] 上线前对生产库跑一次 P3-① 核对 SQL（应得 0 行；非零则执行幂等回填，与迁移 044 同逻辑）：
      ```sql
      -- 核对：应得 0
      SELECT COUNT(DISTINCT o.user_id) FROM `order` o
      JOIN `user` u ON u.id = o.user_id
      WHERE o.type IN (2,3,4,5) AND o.pay_status = 1 AND o.is_deleted = 0
        AND u.paid_member_ever = 0;
      -- 若非零，回填（幂等）
      UPDATE `user` SET paid_member_ever = 1 WHERE id IN (
        SELECT uid FROM (
          SELECT DISTINCT user_id AS uid FROM `order`
          WHERE type IN (2,3,4,5) AND pay_status = 1 AND is_deleted = 0
        ) t
      );
      ```
- [ ] `SECRET_KEY` 已改为随机值，不是默认值
- [ ] 微信支付私钥权限为 `600`：`chmod 600 $WECHAT_PRIVATE_KEY_PATH`
- [ ] 文件上传 MIME 校验已启用（后端 `validate_file_content` 严格拦截魔数不匹配）

### 2.4 WeasyPrint 依赖（PDF 生成）

**Docker 部署：**
Dockerfile 已包含以下系统包：
- `libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev`
- `fonts-noto-cjk fonts-wqy-microhei`

**裸机部署：**
```bash
sudo apt-get update && sudo apt-get install -y \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev \
    fonts-noto-cjk fonts-wqy-microhei
```

**冒烟测试：**
```bash
python -c "import weasyprint; print('WeasyPrint OK:', weasyprint.__version__)"
```

---

## □ 3. 数据库

- [ ] 生产数据库已备份（mysqldump 或快照）

```bash
# 执行迁移
venv/bin/python -m alembic upgrade head
```

- [ ] 迁移 head: `d8e9f0a1b2c3`
- [ ] 迁移无报错
- [ ] 种子数据已导入（如需要）: `venv/bin/python -m backend.seeds.seed_test_data`

---

## □ 4. HTTPS + 域名

- [ ] 域名已解析到服务器 IP
- [ ] SSL 证书已配置（Let's Encrypt / 商业证书）
- [ ] Nginx/Caddy 反向代理已配置到 `127.0.0.1:8002`
- [ ] 回调地址可达:
  - 微信支付: `https://<domain>/order/payment-callback`
  - 押金回调: `https://<domain>/deposit/callback`
  - 微信登录: `https://<domain>/user/wx-login`

---

## □ 5. 服务启动与监控

### 启动方式

```bash
cd /path/to/librio
venv/bin/pip install -r requirements.txt
venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8002
```

建议使用 systemd / supervisor 管理进程保活。

### 健康检查

负载均衡配置指向:

```
GET /health
预期: {"status": "ok", "version": "0.1.0"}
```

### 日志

- [ ] 生产日志级别由 `DEBUG=false` 控制
- [ ] 日志输出至文件或集中式日志服务
- [ ] 异常告警已配置（企业微信/Slack/邮件）

---

## □ 6. 投产前验证

```bash
# 语法与规范
venv/bin/ruff check backend/ tests/

# 单元测试
venv/bin/python -m pytest tests/ -x -q --tb=short

# BDD 测试
venv/bin/python -m behave features/ --no-capture -q

# 全链路集成测试
MOCK_PAYMENT=true MOCK_SMS=true DEBUG=true \
  venv/bin/python scripts/integration_test.py
```

预期: 全部通过

### 真实网关冒烟测试（外部依赖就绪后执行）

```bash
# 微信支付证书可读性
venv/bin/python -c "
from backend.integrations.wechat.pay_v3 import WeChatPayV3
p = WeChatPayV3()
assert p.private_key is not None, '商户私钥未加载'
assert p.platform_cert is not None, '平台证书未加载'
print('WeChatPayV3 OK')
"

# 短信网关配置合法（不实际发送）
venv/bin/python -c "
from backend.common.dependencies import get_sms_gateway
print(type(get_sms_gateway()).__name__)
"
```

---

## □ 7. 回滚方案

### 数据库回滚
```bash
venv/bin/python -m alembic downgrade -1  # 回退一个版本
```

### 代码回滚
```bash
git revert <last-deploy-commit>
```

### 小程序回滚
- 微信公众平台 → 版本管理 → 选择历史版本 → 启用为线上版本

### 服务器回滚
- 保留上一版本的部署快照/容器镜像
- 回滚后重新运行 `alembic upgrade head`（若迁移已回退）

---

## 签署

| 角色 | 签名 | 日期 |
|------|------|------|
| 部署负责人 | | |
| 代码审核 | | |
