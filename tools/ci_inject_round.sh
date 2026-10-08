#!/usr/bin/env bash
# 逐轮推送注入，让 GitHub Actions 真实变红，记录 run id，然后恢复基线。
# 用法： bash tools/ci_inject_round.sh <A|B|C|D|E|F|G>
# 前置：工作区干净、基线 CI 已绿。
set -u
cd "$(dirname "$0")/.." || exit 1

PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
HUGO="C:/Users/Administrator/.workbuddy/binaries/hugo/bin/hugo.exe"
REPO="tanglx02/hugo-theme-nebula"

code="${1:?usage: ci_inject_round.sh A|B|...|G}"
BASE_SHA="$(git rev-parse HEAD)"
echo "基线 SHA = $BASE_SHA"

# 1) 注入
"$PY" tools/inject_v109.py "$code" || exit 2

# 2) 提交 + 推送
msg="ci-inject-$code: $(python -c "import sys;sys.path.insert(0,'tools');import inject_v109 as m;print(m.INJECTIONS['$code']['desc'])" 2>/dev/null || echo "$code")"
git add -A && git commit -q -m "[INJECT $code] $msg" && git push -q origin main
INJ_SHA="$(git rev-parse HEAD)"
echo "注入 SHA = $INJ_SHA"

# 3) 等这条 run 出现
sleep 25
RUN=""
for i in $(seq 1 12); do
  RUN=$(gh run list --repo "$REPO" --limit 12 --json databaseId,headSha --jq ".[] | select(.headSha == \"$INJ_SHA\") | .databaseId" | head -1)
  [ -n "$RUN" ] && break
  sleep 10
done
echo "注入 run = $RUN"

# 4) 等结果
if [ -n "$RUN" ]; then
  for i in $(seq 1 40); do
    st=$(gh run view "$RUN" --repo "$REPO" --json status,conclusion --jq '"\(.status)/\(.conclusion)"' 2>/dev/null)
    case "$st" in completed/*) echo "注入 run 结果 = $st"; break;; esac
    sleep 45
  done
  echo "--- 失败 job ---"
  gh run view "$RUN" --repo "$REPO" --json jobs --jq '.jobs[] | "\(.name) | \(.conclusion)"' | grep -v "success\|skipped"
fi

echo "RUN_ID=$RUN" > "/tmp/ci-inject-$code.env"

# 5) 恢复基线（force reset 到基线 sha，再强推）
git reset -q --hard "$BASE_SHA"
git push -q --force-with-lease origin main
echo "已恢复基线 $BASE_SHA"
git log --oneline -1