#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
#  크립토 ETF — 고치고 나서 이거 하나만 치세요
#
#    bash push.sh                       (기본 메시지로 커밋)
#    bash push.sh "무엇을 고쳤는지"       (메시지를 직접)
#
#  하는 일
#    1. 바뀐 게 있으면 커밋
#    2. 봇이 올린 데이터를 받아 합침 (충돌 나면 데이터는 봇 것으로)
#    3. push
#    4. schema.sql 이 바뀌었으면 D1 에 적용할지 물어봄
#    5. 배포 워크플로 실행
#
#  왜 필요한가
#    봇이 하루 세 번 데이터를 저장소에 올립니다. 그래서 손으로 뭘 올리려 하면
#    거의 매번 "rejected — fetch first" 가 납니다. 매번 같은 실랑이를 하지 않으려고
#    만들었습니다.
# ══════════════════════════════════════════════════════════════════════════
set -u
cd "$(dirname "$0")" || exit 1
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
ok(){ echo -e "  ${G}✓${N} $1"; }
warn(){ echo -e "  ${Y}!${N} $1"; }
err(){ echo -e "  ${R}✗${N} $1"; }
hd(){ echo -e "\n${B}$1${N}"; }

MSG="${1:-갱신 $(date '+%Y-%m-%d %H:%M')}"
BR=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)
DATA_PATHS=(data .cache)

echo -e "${B}══════════════════════════════════════════════════════════${N}"
echo -e "${B} 올리기 — ${BR}${N}"
echo -e "${B}══════════════════════════════════════════════════════════${N}"

# ── 0. pull 이 stash 때문에 죽는 걸 막는다 (이 저장소에만 적용) ──────────────
git config pull.rebase false
git config pull.autoStash false
git config rebase.autoStash false

# ── 1. 커밋 ───────────────────────────────────────────────────────────────
hd "[1/5] 커밋"
git add -A
if git diff --cached --quiet; then
  ok "바뀐 게 없습니다"
else
  git commit -q -m "$MSG" && ok "커밋: $MSG"
fi

# 키가 섞여 들어갔는지 확인 — 커밋한 뒤에 봐야 의미가 있다
for f in config.py .env .dev.vars .cache/kis_token.json; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    err "$f 가 저장소에 들어가 있습니다! 올리기 전에 빼세요:"
    echo "     git rm --cached $f && git commit -m 'remove secrets'"
    exit 1
  fi
done
ok "키 파일은 제외됨"

# ── 2. 받아서 합치기 ──────────────────────────────────────────────────────
hd "[2/5] 봇이 올린 데이터 받기"
git fetch -q origin || { err "fetch 실패 — 인터넷이나 인증을 확인하세요"; exit 1; }

if git merge --no-edit "origin/$BR" >/tmp/_merge.log 2>&1; then
  if grep -q "Already up to date" /tmp/_merge.log; then
    ok "받을 게 없습니다"
  else
    ok "합쳤습니다 ($(grep -cE '^ .+\| +[0-9]' /tmp/_merge.log | tr -d ' \n')개 파일)"
  fi
else
  # 충돌. 데이터 파일이면 봇 것으로 맞춘다 — 어차피 다음 실행이 다시 만든다.
  CONF=$(git diff --name-only --diff-filter=U)
  OTHER=$(echo "$CONF" | grep -Ev '^(data/|\.cache/)' || true)
  if [ -n "$OTHER" ]; then
    err "코드에서 충돌이 났습니다. 직접 봐주셔야 합니다:"
    echo "$OTHER" | sed 's/^/     /'
    echo "     정리한 뒤:  git add -A && git commit --no-edit && bash push.sh"
    exit 1
  fi
  git checkout --theirs -- "${DATA_PATHS[@]}" 2>/dev/null
  git add -A "${DATA_PATHS[@]}" 2>/dev/null
  git commit -q --no-edit && ok "데이터 충돌을 봇 것으로 맞췄습니다"
fi

# ── 3. push ───────────────────────────────────────────────────────────────
hd "[3/5] 올리기"
if git push -q origin "$BR" 2>/tmp/_push.log; then
  ok "올렸습니다 — $(git rev-parse --short HEAD)"
else
  warn "한 번 거절됐습니다. 봇이 그새 또 올린 모양입니다. 다시 시도합니다…"
  git fetch -q origin && git merge --no-edit -q "origin/$BR" >/dev/null 2>&1
  if git push -q origin "$BR" 2>/tmp/_push.log; then
    ok "두 번째 시도에 성공 — $(git rev-parse --short HEAD)"
  else
    err "올리지 못했습니다:"; sed 's/^/     /' /tmp/_push.log; exit 1
  fi
fi

# ── 4. 표(schema) ─────────────────────────────────────────────────────────
hd "[4/5] 데이터베이스 표"
if git diff --name-only HEAD@{1} HEAD 2>/dev/null | grep -q '^schema\.sql$'; then
  warn "schema.sql 이 바뀌었습니다. D1 에 적용하지 않으면 새 기능이 500 을 냅니다."
  read -r -p "  지금 적용할까요? [Y/n] " a
  if [ "${a:-y}" != "n" ] && [ "${a:-y}" != "N" ]; then
    npx --yes wrangler@latest d1 execute crypto-etf --remote --file=schema.sql --yes \
      && ok "표 적용 완료" || err "표 적용 실패 — 직접 실행해 보세요"
  else
    warn "건너뜁니다. 나중에: npx wrangler d1 execute crypto-etf --remote --file=schema.sql"
  fi
else
  ok "바뀐 표 없음"
fi

# ── 5. 배포 ───────────────────────────────────────────────────────────────
hd "[5/5] 배포"
if command -v gh >/dev/null 2>&1; then
  gh workflow run '크립토 ETF 갱신' >/dev/null 2>&1 \
    && ok "워크플로를 걸었습니다" \
    || warn "워크플로 실행 실패 — 저장소 Actions 탭에서 직접 돌려주세요"
  echo
  echo "  진행 상황:"
  echo "    gh run watch \$(gh run list --workflow=update.yml --limit 1 --json databaseId -q '.[0].databaseId')"
else
  warn "gh 가 없습니다 — GitHub Actions 탭에서 직접 실행해 주세요"
fi

echo -e "\n${B}══════════════════════════════════════════════════════════${N}"
echo -e " 끝. 몇 분 뒤 https://crypto-etf.pages.dev 에서 확인하세요."
echo -e "${B}══════════════════════════════════════════════════════════${N}"
