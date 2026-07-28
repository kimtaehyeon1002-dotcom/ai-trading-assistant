#!/usr/bin/env bash
# 생성물(docs/·data/) 커밋 → 원격 변경 흡수 → 푸시. docs를 커밋하는 전 워크플로 공용.
#
#   scripts/ci_commit_push.sh "<커밋 메시지>" [저장소경로=.] [git add 인자...=docs data]
#
# 왜 공용 스크립트인가: main에는 여러 주체가 같은 생성물을 쓴다(뉴스 30분·매크로 60분·
# stock/financials cron·데스크톱 수동 배포 push). 워크플로마다 있던
#     git pull --rebase --autostash || true
#     git push
# 는 이 경합을 두 군데서 놓쳤다 —
#   (1) rebase가 생성물 충돌로 멈추면 `|| true`가 실패를 삼키고, 저장소는 충돌이 남은
#       detached HEAD 상태로 남는다. 뒤따르는 push가 exit 128로 죽으면서 그 실행의
#       커밋은 통째로 유실된다(실측: 2026-07-27 14:25Z Trades Dashboard, 데스크톱이
#       23:25/23:26/23:29 연속 push한 직후 morning·trades가 겹쳐 발생).
#   (2) fetch와 push 사이에 다른 워크플로가 먼저 푸시하면 non-fast-forward로 거부되는데,
#       재시도가 없어 그대로 실패한다.
# 충돌하는 파일은 전부 재생성 가능한 산출물이므로 `-X theirs`(=재적용되는 이번 실행의
# 커밋)로 해소한다 — 다음 주기의 재생성이 어차피 최신 데이터로 덮는다. 거부는 원격을
# 다시 흡수하며 재시도한다.
set -uo pipefail

MESSAGE="${1:?커밋 메시지가 필요합니다}"
shift
REPO_DIR="${1:-.}"
[ $# -gt 0 ] && shift
ADD_ARGS=("$@")
[ ${#ADD_ARGS[@]} -eq 0 ] && ADD_ARGS=(docs data)
RETRIES="${PUSH_RETRIES:-5}"

# TH_DATA(vault) 브릿지는 토큰 미설정/만료 시 체크아웃이 skip된다 — 없으면 조용히 통과.
if [ ! -d "$REPO_DIR/.git" ]; then
  echo "저장소 없음: $REPO_DIR — 커밋 건너뜀"
  exit 0
fi
cd "$REPO_DIR" || exit 1

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$branch" = "HEAD" ]; then
  branch="${GITHUB_REF_NAME:?분리 HEAD 상태 — 푸시 대상 브랜치를 알 수 없습니다}"
fi

git add "${ADD_ARGS[@]}" || exit 1
if git diff --cached --quiet; then
  echo "변경 없음 — 커밋 생략"
  exit 0
fi
git commit -m "$MESSAGE" || exit 1

for attempt in $(seq 1 "$RETRIES"); do
  git fetch origin "$branch" || true
  if ! git rebase --autostash -X theirs "origin/$branch"; then
    git rebase --abort || true
    echo "::error::rebase 충돌을 -X theirs로도 해소하지 못했습니다 — 수동 확인 필요"
    exit 1
  fi
  if git push origin "HEAD:$branch"; then
    echo "푸시 완료 (시도 ${attempt}/${RETRIES})"
    exit 0
  fi
  echo "푸시 거부 (시도 ${attempt}/${RETRIES}) — 원격 변경을 다시 흡수한 뒤 재시도"
  sleep $((attempt * 5))
done

echo "::error::푸시 실패 — ${RETRIES}회 재시도 후 포기"
exit 1
