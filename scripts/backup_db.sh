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
if [ -d "$PROJECT_DIR/uploads" ] && [ "$(du -s "$PROJECT_DIR/uploads" 2>/dev/null | awk '{print $1}')" -gt 0 ]; then
  UPLOADS_ARCHIVE="$BACKUP_DIR/uploads_${DATE_TAG}.tar.gz"
  tar -czf "$UPLOADS_ARCHIVE" -C "$PROJECT_DIR" uploads/
  log "文件备份完成: $UPLOADS_ARCHIVE"
fi

# ── 清理过期备份 ──
DELETED_COUNT=$(find "$BACKUP_DIR" -name "${DB_NAME}_full_*.sql.gz" -mtime +${RETENTION_DAYS} -print -delete 2>/dev/null | wc -l)
DELETED_UPLOADS=$(find "$BACKUP_DIR" -name "uploads_*.tar.gz" -mtime +${RETENTION_DAYS} -print -delete 2>/dev/null | wc -l)
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
