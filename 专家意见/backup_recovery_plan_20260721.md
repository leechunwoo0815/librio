# 数据备份与恢复方案

**编制日期**: 2026-07-21  
**项目**: DmkWords (librio)  
**适用阶段**: 本地开发 → 生产部署  
**约束**: 仅方案文档 + 脚本，不改动现有代码逻辑

---

## 一、现状分析

### 1.1 数据库现状（命令实测）

```
MySQL 版本: 9.6.0 (Homebrew, macOS arm64)
数据库名: dmkwords
表数量: 55 张
数据库大小: 453.80 MB
binlog: ON (路径: /opt/homebrew/var/mysql/binlog)
Alembic 迁移: 32 个版本
软删除数据量: 0（当前所有表 is_deleted=1 均为 0，开发期数据较少）
上传文件目录: uploads/ (0B，空)
```

### 1.2 当前备份现状

- ❌ 无备份脚本
- ❌ 无恢复演练记录
- ❌ 无软删除数据清理策略
- ✅ MySQL binlog 已启用
- ✅ Alembic 迁移版本完整（32 个）
- ✅ 软删除字段 `is_deleted` 统一在 `BaseModel` 中定义

### 1.3 数据分类

| 类别 | 存储 | 特点 | 示例 |
|------|------|------|------|
| 结构化数据 | MySQL (55 表) | 核心业务数据，453 MB | child, order, borrow_record, deposit_record |
| 文件资产 | uploads/ 目录 | 图书封面/损坏照片/语音录音 | uploads/cover/, uploads/voice/, uploads/damage/ |
| 配置数据 | .env + system_config 表 | 环境变量 + 可配置参数 | SECRET_KEY, overdue_fine_per_day |
| 迁移版本 | alembic/versions/ (32 文件) | Schema 变更历史 | — |

---

## 二、备份方案

### 2.1 本地开发环境（cron 定时）

#### 2.1.1 全量备份脚本

**文件**: `scripts/backup_db.sh`

```bash
#!/usr/bin/env bash
# ============================================================
# DmkWords 数据库全量备份脚本
# 用途: mysqldump 每日全量备份，保留 30 天
# 用法: crontab -e → 0 2 * * * /path/to/librio/scripts/backup_db.sh
# 依赖: mysqldump (Homebrew MySQL 自带)
# ============================================================

set -euo pipefail

# ── 配置 ──
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$PROJECT_DIR/.env"

BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-}"
DB_NAME="${DB_NAME:-dmkwords}"
RETENTION_DAYS=30
DATE_TAG=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_full_${DATE_TAG}.sql.gz"

# ── 初始化 ──
mkdir -p "$BACKUP_DIR"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# ── 全量备份（mysqldump --single-transaction 保证一致性快照）──
log "开始全量备份: $DB_NAME"

MYSQL_PWD="${DB_PASSWORD}" mysqldump \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --user="$DB_USER" \
  --single-transaction \
  --routines \
  --triggers \
  --events \
  --set-gtid-purged=OFF \
  --column-statistics=0 \
  "$DB_NAME" 2>"$BACKUP_DIR/backup_${DATE_TAG}.err" | gzip > "$BACKUP_FILE"

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | awk '{print $1}')
log "备份完成: $BACKUP_FILE ($BACKUP_SIZE)"

# ── 同时备份上传文件 ──
if [ -d "$PROJECT_DIR/uploads" ] && [ "$(du -s "$PROJECT_DIR/uploads" | awk '{print $1}')" -gt 0 ]; then
  UPLOADS_ARCHIVE="$BACKUP_DIR/uploads_${DATE_TAG}.tar.gz"
  tar -czf "$UPLOADS_ARCHIVE" -C "$PROJECT_DIR" uploads/
  log "文件备份完成: $UPLOADS_ARCHIVE"
fi

# ── 清理过期备份 ──
DELETED_COUNT=$(find "$BACKUP_DIR" -name "${DB_NAME}_full_*.sql.gz" -mtime +${RETENTION_DAYS} -print -delete | wc -l)
DELETED_UPLOADS=$(find "$BACKUP_DIR" -name "uploads_*.tar.gz" -mtime +${RETENTION_DAYS} -print -delete | wc -l)
log "清理过期备份: ${DELETED_COUNT} 个 SQL + ${DELETED_UPLOADS} 个文件归档"

# ── 备份完整性校验 ──
if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
  log "❌ 备份文件损坏: $BACKUP_FILE"
  exit 1
fi
log "✅ 备份校验通过"

# ── 记录备份元数据 ──
META_FILE="$BACKUP_DIR/backup_log.csv"
if [ ! -f "$META_FILE" ]; then
  echo "timestamp,file,size,db_size_mb,tables" > "$META_FILE"
fi
DB_SIZE=$(MYSQL_PWD="${DB_PASSWORD}" mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -N -e \
  "SELECT ROUND(SUM(data_length+index_length)/1024/1024,2) FROM information_schema.tables WHERE table_schema='$DB_NAME';" "$DB_NAME" 2>/dev/null || echo "N/A")
TABLE_COUNT=$(MYSQL_PWD="${DB_PASSWORD}" mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -N -e \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$DB_NAME';" 2>/dev/null || echo "N/A")
echo "${DATE_TAG},${BACKUP_FILE},${BACKUP_SIZE},${DB_SIZE},${TABLE_COUNT}" >> "$META_FILE"
log "元数据已记录: $META_FILE"
```

#### 2.1.2 binlog 增量备份

由于 MySQL 9.6.0 的 binlog 已启用（`log_bin=ON`），可通过 `mysqlbinlog` 工具实现增量恢复：

```bash
#!/usr/bin/env bash
# ============================================================
# DmkWords binlog 增量备份脚本
# 用途: 每小时备份 binlog 文件，用于 PITR (Point-in-Time Recovery)
# 用法: crontab -e → 0 * * * * /path/to/librio/scripts/backup_binlog.sh
# 依赖: mysqlbinlog (Homebrew MySQL 自带)
# ============================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
source "$PROJECT_DIR/.env"

BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}/binlog"
MYSQL_DATA_DIR="/opt/homebrew/var/mysql"
DATE_TAG=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# 刷新 binlog（开始新 binlog 文件）
MYSQL_PWD="${DB_PASSWORD:-}" mysql -h"${DB_HOST:-localhost}" -P"${DB_PORT:-3306}" -u"${DB_USER:-root}" -e "FLUSH BINARY LOGS;"

# 复制已关闭的 binlog 文件到备份目录（排除当前正在写入的）
CURRENT_BINLOG=$(MYSQL_PWD="${DB_PASSWORD:-}" mysql -h"${DB_HOST:-localhost}" -P"${DB_PORT:-3306}" -u"${DB_USER:-root}" -N -e "SHOW MASTER STATUS;" | awk '{print $1}')

for binlog_file in "$MYSQL_DATA_DIR"/binlog.*; do
  filename=$(basename "$binlog_file")
  if [ "$filename" != "$CURRENT_BINLOG" ]; then
    if [ ! -f "$BACKUP_DIR/$filename" ]; then
      cp "$binlog_file" "$BACKUP_DIR/"
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] 复制 binlog: $filename"
    fi
  fi
done

# 清理 7 天前的 binlog 备份
find "$BACKUP_DIR" -name "binlog.*" -mtime +7 -delete
echo "[$(date '+%Y-%m-%d %H:%M:%S')] binlog 增量备份完成"
```

#### 2.1.3 crontab 配置

```bash
# DmkWords 备份 crontab
# 编辑: crontab -e

# 每日 02:00 全量备份
0 2 * * * /Users/litianyu/cc-projects/librio/scripts/backup_db.sh >> /Users/litianyu/cc-projects/librio/backups/cron.log 2>&1

# 每小时 binlog 增量备份
0 * * * * /Users/litianyu/cc-projects/librio/scripts/backup_binlog.sh >> /Users/litianyu/cc-projects/librio/backups/cron.log 2>&1

# 每周日 03:00 备份 Alembic 迁移版本和上传文件
0 3 * * 0 tar -czf /Users/litianyu/cc-projects/librio/backups/code_$(date +\%Y\%m\%d).tar.gz -C /Users/litianyu/cc-projects/librio alembic/ .env scripts/ backend/config.py
```

### 2.2 生产环境方案建议（云 RDS）

> ⚠️ 本项目当前处于本地开发阶段，生产部署后应迁移到云数据库。

| 项目 | 方案 | 说明 |
|------|------|------|
| 数据库引擎 | 腾讯云 MySQL 8.0 / 阿里云 RDS MySQL 8.0 | 兼容当前 MySQL 9.6 语法 |
| 自动备份 | 云厂商每日自动全量备份 | 默认保留 7 天，可配置 30 天 |
| binlog | 云厂商自动保留 | 用于 PITR，保留 7 天 |
| 跨可用区 | 主从复制 + 异地灾备 | 生产环境必须配置 |
| 文件存储 | 对象存储 (COS/OSS) | 上传文件不存本地，改用云存储 |
| 恢复演练 | 每季度 1 次 | 从备份恢复到测试环境验证 |

---

## 三、恢复演练 SOP

### 3.1 全量恢复流程

```bash
# ============================================================
# 恢复步骤：从全量备份恢复到新库
# 前提: 备份文件存在于 backups/ 目录
# ============================================================

# Step 1: 创建恢复用数据库（不覆盖原库）
mysql -u root -e "CREATE DATABASE dmkwords_restore CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Step 2: 解压并恢复
gunzip < backups/dmkwords_full_YYYYMMDD_HHMMSS.sql.gz | mysql -u root dmkwords_restore

# Step 3: 验证表数量
mysql -u root dmkwords_restore -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='dmkwords_restore';"
# 预期: 55

# Step 4: 验证关键表数据
mysql -u root dmkwords_restore -e "
SELECT 'child' AS tbl, COUNT(*) AS cnt FROM child WHERE is_deleted=0
UNION SELECT 'order', COUNT(*) FROM \`order\` WHERE is_deleted=0
UNION SELECT 'borrow_record', COUNT(*) FROM borrow_record WHERE is_deleted=0
UNION SELECT 'deposit_record', COUNT(*) FROM deposit_record WHERE is_deleted=0;
"

# Step 5: 对比备份元数据
cat backups/backup_log.csv | tail -1
# 核对 timestamp / tables 数量 / db_size 是否一致

# Step 6: 恢复上传文件（如有）
tar -xzf backups/uploads_YYYYMMDD_HHMMSS.tar.gz -C /tmp/restore_test/

# Step 7: 确认无误后切换（停服 → 改名）
# ⚠️ 生产环境需要: 通知用户停服 → 重命名 dmkwords → dmkwords_bak → dmkwords_restore → dmkwords → 重启服务
```

### 3.2 PITR (Point-in-Time Recovery) 流程

```bash
# ============================================================
# 场景: 误删数据后，恢复到误操作前的时间点
# 前提: 有全量备份 + binlog 备份
# ============================================================

# Step 1: 确定全量备份时间点
ls -lt backups/dmkwords_full_*.sql.gz | head -1
# 假设: 备份时间 2026-07-21 02:00:00

# Step 2: 确定 binlog 恢复截止时间（误操作前）
# 假设: 误操作发生在 2026-07-21 14:30:00，恢复到 14:29:00

# Step 3: 恢复全量备份（到恢复库）
mysql -u root -e "CREATE DATABASE dmkwords_pitr CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
gunzip < backups/dmkwords_full_20260721_020000.sql.gz | mysql -u root dmkwords_pitr

# Step 4: 应用 binlog 到指定时间点
mysqlbinlog \
  --start-datetime="2026-07-21 02:00:00" \
  --stop-datetime="2026-07-21 14:29:00" \
  /opt/homebrew/var/mysql/binlog.* | mysql -u root dmkwords_pitr

# Step 5: 验证数据正确性（检查误删数据是否恢复）
mysql -u root dmkwords_pitr -e "SELECT COUNT(*) FROM child WHERE is_deleted=0;"

# Step 6: 导出恢复的数据，应用到生产库
# mysqldump --single-transaction dmkwords_pitr specific_table > recovered_data.sql
# mysql dmkwords < recovered_data.sql
```

### 3.3 恢复演练计划

| 频率 | 场景 | 验证项 | 负责人 |
|------|------|--------|--------|
| 每季度 1 次 | 全量恢复到新库 | 表数 55 / 数据行数 / 关键记录 | 运维 |
| 每半年 1 次 | PITR 到指定时间点 | 数据一致性 / 时间精度 | 运维 + 开发 |
| 上线前 1 次 | 完整灾备演练 | 停服 → 恢复 → 验证 → 切换 → 恢复服务 | 全员 |

---

## 四、软删除数据清理策略

### 4.1 当前软删除分布

**实测命令**: 
```sql
SELECT 'borrow_record' AS tbl, COUNT(*) AS deleted FROM borrow_record WHERE is_deleted=1
UNION SELECT 'child', COUNT(*) FROM child WHERE is_deleted=1
...（10 张核心表）;
```
**结果**: 当前所有表 is_deleted=1 均为 0（开发期数据量少）。

### 4.2 数据生命周期定义

| 表 | 保留期 | 物理清理条件 | 清理方式 | 理由 |
|---|--------|------------|---------|------|
| `child` | 3 年 | is_deleted=1 且 create_time > 3 年 | 定时任务物理删除 | 监护人可能要求彻底删除儿童数据（合规要求） |
| `user` | 3 年 | is_deleted=1 且无关联 child | 级联检查后删除 | 账号注销后保留日志，期满物理删除 |
| `order` | 5 年 | is_deleted=1 且 create_time > 5 年 | 归档后删除 | 交易记录法定保留 5 年 |
| `deposit_record` | 3 年 | is_deleted=1 且关联 order 已过保留期 | 级联检查后删除 | 押金记录与订单同步保留 |
| `borrow_record` | 2 年 | is_deleted=1 且 create_time > 2 年 | 物理删除 | 借阅记录保留 2 年供查询 |
| `reading_session` | 1 年 | is_deleted=1 且 create_time > 1 年 | 物理删除 | 阅读会话数据量大，保留 1 年足够 |
| `voice_recording` | 6 个月 | is_deleted=1 且 create_time > 6 月 | 物理删除 + 删除音频文件 | 语音数据占空间大且涉及儿童隐私 |
| `book_damage_report` | 2 年 | is_deleted=1 且 create_time > 2 年 | 物理删除 | 损坏记录保留 2 年供审计 |
| `system_message` | 6 个月 | is_deleted=1 且 create_time > 6 月 | 物理删除 | 消息数据量大，6 月足够 |
| `activity` | 1 年 | is_deleted=1 且 create_time > 1 年 | 物理删除 | 活动数据保留 1 年供回顾 |
| `reservation` | 6 个月 | is_deleted=1 且 create_time > 6 月 | 物理删除 | 预约数据量大，6 月足够 |
| 其他表 | 2 年 | is_deleted=1 且 create_time > 2 年 | 物理删除 | 默认策略 |

### 4.3 清理脚本设计

**文件**: `scripts/purge_soft_deleted.py`（完整代码见该文件，以下为关键逻辑说明）

```python
# 清理策略表 — 每张表独立的保留期
PURGE_POLICY = {
    "child":              {"retention_days": 1095, "reason": "儿童隐私合规"},
    "user":               {"retention_days": 1095, "reason": "账号注销后保留期"},
    "order":              {"retention_days": 1825, "reason": "交易记录法定保留5年"},
    "deposit_record":     {"retention_days": 1095, "reason": "押金记录同步订单"},
    "borrow_record":      {"retention_days": 730,  "reason": "借阅记录保留2年"},
    "reading_session":    {"retention_days": 365,  "reason": "阅读会话数据量大"},
    "voice_recording":    {"retention_days": 180,  "reason": "语音数据涉及儿童隐私"},
    "book_damage_report": {"retention_days": 730,  "reason": "损坏记录审计保留"},
    "system_message":     {"retention_days": 180,  "reason": "消息数据量大"},
    "activity":           {"retention_days": 365,  "reason": "活动数据保留1年"},
    "reservation":        {"retention_days": 180,  "reason": "预约数据量大"},
}

# 核心流程（每张表）:
# 1. COUNT 待删行数（is_deleted=1 AND create_time < cutoff）
# 2. 若 --no-dry-run:
#    a. backup_deleted_rows() — 导出待删行到 CSV (backups/purge_YYYYMMDD/)
#    b. DELETE FROM 待删行
#    c. 若 table == "voice_recording": delete_voice_files() 同步删除 uploads/voice/ 音频文件
# 3. 输出清理统计
```

### 4.4 清理任务调度

```bash
# crontab 每月 1 日 04:00 执行清理（DRY-RUN 先行）
# 每月 1 日: DRY-RUN 输出报告
0 4 1 * * /Users/litianyu/cc-projects/librio/venv/bin/python /Users/litianyu/cc-projects/librio/scripts/purge_soft_deleted.py --dry-run >> /Users/litianyu/cc-projects/librio/backups/purge_dryrun.log 2>&1

# 每月 15 日: 实际执行清理（确认 DRY-RUN 无误后）
0 4 15 * * /Users/litianyu/cc-projects/librio/venv/bin/python /Users/litianyu/cc-projects/librio/scripts/purge_soft_deleted.py --no-dry-run >> /Users/litianyu/cc-projects/librio/backups/purge_actual.log 2>&1
```

---

## 五、验证清单

### 5.1 备份脚本验证

```bash
# 1. 手动执行全量备份
source venv/bin/activate
bash scripts/backup_db.sh

# 2. 验证备份文件
ls -la backups/dmkwords_full_*.sql.gz
gzip -t backups/dmkwords_full_*.sql.gz && echo "✅ 文件完整"

# 3. 恢复到测试库
mysql -u root -e "CREATE DATABASE dmkwords_test_restore CHARACTER SET utf8mb4;"
gunzip < backups/dmkwords_full_*.sql.gz | mysql -u root dmkwords_test_restore

# 4. 验证表数
mysql -u root dmkwords_test_restore -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='dmkwords_test_restore';"
# 预期: 55

# 5. 清理测试库
mysql -u root -e "DROP DATABASE dmkwords_test_restore;"
```

### 5.2 软删除清理验证

```bash
# DRY-RUN 测试
source venv/bin/activate
python scripts/purge_soft_deleted.py --dry-run
# 预期: 所有表显示 "0 条待清理"（当前无软删除数据）
```

---

## 六、风险与建议

| 风险 | 等级 | 建议 |
|------|------|------|
| 本地 MySQL 单点故障 | P0 | 生产环境必须迁移到云 RDS + 主从复制 |
| 备份文件与数据库同机 | P1 | 定期将备份同步到异地（云存储/U盘） |
| 软删除数据无限增长 | P1 | 按本方案 4.2 节策略定期清理 |
| ~~voice_recording 音频文件未纳入清理~~ | ✅ 已修复 | purge_soft_deleted.py 删除 voice_recording 行时同步删除 uploads/voice/ 对应音频文件 |
| 无备份加密 | P2 | 生产环境备份文件应加密存储 |
| binlog 空间无限增长 | P2 | 配置 `expire_logs_days=7` 自动清理 |

---

*方案编制时间: 2026-07-21 23:20（修正: 2026-07-22 00:10）*  
*编制人: Python 全栈工程师 Agent*  
*实测数据来源: MySQL 9.6.0 + 项目 .env 配置*  
*修正记录: [1] purge 脚本补删除前 CSV 备份; [2] crontab 路径 .venv→venv; [3] purge 脚本补 voice 文件同步删除*
