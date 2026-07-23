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
# MySQL 9.x 用 SHOW BINARY LOG STATUS 替代 SHOW MASTER STATUS
CURRENT_BINLOG=$(MYSQL_PWD="${DB_PASSWORD:-}" mysql -h"${DB_HOST:-localhost}" -P"${DB_PORT:-3306}" -u"${DB_USER:-root}" -N -e "SHOW BINARY LOG STATUS;" 2>/dev/null | awk '{print $1}')
if [ -z "$CURRENT_BINLOG" ]; then
  CURRENT_BINLOG=$(MYSQL_PWD="${DB_PASSWORD:-}" mysql -h"${DB_HOST:-localhost}" -P"${DB_PORT:-3306}" -u"${DB_USER:-root}" -N -e "SHOW MASTER STATUS;" 2>/dev/null | awk '{print $1}')
fi

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
find "$BACKUP_DIR" -name "binlog.*" -mtime +7 -delete 2>/dev/null
echo "[$(date '+%Y-%m-%d %H:%M:%S')] binlog 增量备份完成"
