#!/usr/bin/env bash
# LOOP-2 外层驱动 —— 反复唤起执行模型，直到 loop_check --mode full 退出码 0（或升级人工）。
# 模型不需要"自觉坚持"：坚持由本脚本负责；模型每次只需完成台账下一项。
#
# 用法:
#   LOOP_CLI=opencode bash audit_loop/loop2/driver.sh          # 默认 opencode
#   LOOP_CLI=claude   bash audit_loop/loop2/driver.sh          # claude -p 无头模式
#   LOOP_CLI=codex    bash audit_loop/loop2/driver.sh          # codex exec 无头模式
#   LOOP_MAX_ITERS=300 ...                                     # 会话上限，默认 200
#
# 停机条件（三选一，全部由脚本判定）:
#   1. scripts/loop_check.py --mode full 退出码 0   → 闭环完成（写 DONE 标记）
#   2. ledger 校验退出码 3（剩余全 BLOCKED）        → 升级人工，见 ESCALATE.md
#   3. 达到 LOOP_MAX_ITERS                          → 强制停，人工介入
set -uo pipefail
cd "$(dirname "$0")/../.." || exit 2
ROOT=$(pwd)

CLI="${LOOP_CLI:-opencode}"
MAX="${LOOP_MAX_ITERS:-200}"
LOG="$ROOT/audit_loop/loop2/driver.log"
PROMPT='读 audit_loop/loop2/PROMPT.md 并严格执行。这是 LOOP-2 外层驱动的自动调用：按台账顺序做第一行未完成项，做完提交即可结束本次会话，无需请示下一步，无需总结全局。'

echo "=== LOOP2 driver start $(date '+%F %T') cli=$CLI max=$MAX ===" | tee -a "$LOG"

for i in $(seq 1 "$MAX"); do
  echo "" | tee -a "$LOG"
  echo "########## LOOP2 session $i/$MAX begin $(date '+%F %T') ##########" | tee -a "$LOG"

  case "$CLI" in
    opencode) opencode run "$PROMPT" 2>&1 | tee -a "$LOG" ;;
    claude)   claude -p "$PROMPT" 2>&1 | tee -a "$LOG" ;;
    codex)    codex exec "$PROMPT" 2>&1 | tee -a "$LOG" ;;
    *) echo "[driver] 未知 LOOP_CLI=$CLI（支持 opencode/claude/codex）" | tee -a "$LOG"; exit 2 ;;
  esac

  # 会话后：先做廉价的台账一致性校验
  venv/bin/python scripts/loop_check.py --mode ledger 2>&1 | tee -a "$LOG"
  rc=$?
  echo "########## session $i ledger-check rc=$rc $(date '+%F %T') ##########" | tee -a "$LOG"

  case $rc in
    0)  # 台账全闭环 → 跑唯一完工判定
      venv/bin/python scripts/loop_check.py --mode full 2>&1 | tee -a "$LOG"
      frc=$?
      if [ "$frc" -eq 0 ]; then
        echo "[driver] DONE：loop_check --mode full 通过，闭环完成。见 audit_loop/loop2/FINAL_REPORT.md" | tee -a "$LOG"
        exit 0
      fi
      echo "[driver] full 校验未过（rc=$frc），继续循环修复" | tee -a "$LOG"
      ;;
    3)
      echo "[driver] 剩余项全部 BLOCKED，升级人工：读 audit_loop/loop2/ESCALATE.md 后交专家处置" | tee -a "$LOG"
      exit 3
      ;;
    1)
      : # 仍有未完成项，继续下一会话
      ;;
    *)
      echo "[driver] 台账解析错误（rc=$rc），先修复 LEDGER.md 格式再继续" | tee -a "$LOG"
      exit 2
      ;;
  esac
done

echo "[driver] 达到会话上限 $MAX，强制停机，人工介入（未见 DONE 标记）" | tee -a "$LOG"
exit 4
