#!/usr/bin/env bash
# v1.0.9 最终故障注入：CI 侧证明（串行）。
# 流程：reset 到基线 → 注入 X → force push main → 等该 SHA 的 run 完成（期望 failure）
#       → 记录 run id → 下一轮。全部结束后恢复基线并等最终绿灯。
# 用法： bash tools/run_ci_injections.sh
set -u
cd "$(dirname "$0")/.." || exit 1

PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
REPO="tanglx02/hugo-theme-nebula"
BASE="${BASE_SHA:-$(git rev-parse HEAD)}"
LOG=/tmp/ci-inject-all.log
: > "$LOG"

log() { echo "$@" | tee -a "$LOG"; }

wait_run() { # $1=sha  -> echoes run id
  local sha="$1" rid=""
  for i in $(seq 1 20); do
    rid=$(gh run list --repo "$REPO" --limit 15 --json databaseId,headSha \
          --jq ".[] | select(.headSha == \"$sha\") | .databaseId" | head -1)
    [ -n "$rid" ] && break
    sleep 10
  done
  echo "$rid"
}

wait_done() { # $1=run id
  local st
  for i in $(seq 1 60); do
    st=$(gh run view "$1" --repo "$REPO" --json status,conclusion \
         --jq '"\(.status)/\(.conclusion)"' 2>/dev/null)
    case "$st" in completed/*) echo "$st"; return;; esac
    sleep 40
  done
  echo "timeout/"
}

log "=== v1.0.9 CI 注入开始，基线 SHA=$BASE ==="
for code in A B C D E F G; do
  log ""
  log "########## 注入 $code ##########"
  git reset -q --hard "$BASE"
  if ! "$PY" tools/inject_v109.py "$code" >>"$LOG" 2>&1; then
    log "!! 注入 $code 应用失败"; continue
  fi
  git add -A
  git commit -q -m "[INJECT $code] v1.0.9 故意故障注入（临时提交，随后强制回滚）"
  git push -q --force origin main
  SHA=$(git rev-parse HEAD)
  sleep 20
  RID=$(wait_run "$SHA")
  log "inject $code: sha=$SHA run=$RID"
  [ -z "$RID" ] && { log "!! 未找到 run"; continue; }
  RES=$(wait_done "$RID")
  log "inject $code: 结果=$RES"
  gh run view "$RID" --repo "$REPO" --json jobs \
     --jq '.jobs[] | "\(.name) | \(.conclusion)"' 2>/dev/null \
     | grep -vE "success|skipped" | sed 's/^/    红: /' | tee -a "$LOG"
  echo "$code $RID $RES" >> /tmp/ci-inject-results.txt
done

log ""
log "########## 恢复基线并等最终绿灯 ##########"
git reset -q --hard "$BASE"
git push -q --force origin main
FINAL_SHA=$(git rev-parse HEAD)
sleep 20
FRID=$(wait_run "$FINAL_SHA")
log "最终基线 sha=$FINAL_SHA run=$FRID"
[ -n "$FRID" ] && log "最终结果=$(wait_done "$FRID")"
log "=== 完成 ==="