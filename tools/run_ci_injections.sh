#!/usr/bin/env bash
# v1.0.9 CI 侧故障注入（串行，仓库外运行，保持基线干净）。
# 每轮：reset 到 BASE → 注入 → force push → 等该 SHA 的 CI workflow 完成（期望 failure）
#       → 记录 → 恢复 BASE 并 force push。
set -u
REPO_DIR="E:/Work/项目开发/hugo博客开发/hugo-theme-nebula"
cd "$REPO_DIR" || exit 1

PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
REPO="tanglx02/hugo-theme-nebula"
BASE="${BASE_SHA:-$(git rev-parse HEAD)}"
LOG=/tmp/ci-inject-all.log
RES=/tmp/ci-inject-results.txt
: > "$LOG"; : > "$RES"
log() { echo "$@" | tee -a "$LOG"; }

# 按 workflow 名 "CI" 过滤——仓库里还有 compat-latest.yml，不过滤会误配
wait_run() {
  local sha="$1" rid=""
  for i in $(seq 1 30); do
    rid=$(gh run list --repo "$REPO" --limit 25 --json databaseId,headSha,workflowName \
          --jq ".[] | select(.headSha == \"$sha\" and .workflowName == \"CI\") | .databaseId" | head -1)
    [ -n "$rid" ] && break
    sleep 10
  done
  echo "$rid"
}
wait_done() {
  local st
  for i in $(seq 1 70); do
    st=$(gh run view "$1" --repo "$REPO" --json status,conclusion \
         --jq '"\(.status)/\(.conclusion)"' 2>/dev/null)
    case "$st" in completed/*) echo "$st"; return;; esac
    sleep 40
  done
  echo "timeout/"
}

log "=== v1.0.9 CI 注入开始，BASE=$BASE ==="
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
  log "inject $code: sha=${SHA:0:7} run=$RID"
  [ -z "$RID" ] && { log "!! 未找到 CI run"; continue; }
  RESULT=$(wait_done "$RID")
  log "inject $code: 结果=$RESULT"
  gh run view "$RID" --repo "$REPO" --json jobs \
     --jq '.jobs[] | "\(.name) | \(.conclusion)"' 2>/dev/null \
     | grep -vE "success|skipped" | sed 's/^/    红: /' | tee -a "$LOG"
  echo "$code $RID $RESULT" >> "$RES"
  # 每轮结束立刻恢复基线，避免下一轮 push 取消本轮 CI（本轮已等到 completed）
  git reset -q --hard "$BASE"
done

log ""
log "########## 恢复基线并等最终绿灯 ##########"
git reset -q --hard "$BASE"
git push -q --force origin main
FINAL_SHA=$(git rev-parse HEAD)
sleep 20
FRID=$(wait_run "$FINAL_SHA")
log "最终基线 sha=${FINAL_SHA:0:7} run=$FRID"
if [ -n "$FRID" ]; then
  FRES=$(wait_done "$FRID")
  log "最终结果=$FRES"
  echo "FINAL $FRID $FRES" >> "$RES"
fi
log "=== 完成 ==="