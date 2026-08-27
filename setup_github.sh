#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
#  크립토 ETF — 자동 갱신 · 배포 설정 (한 번만 실행)
#
#    cd ~/Desktop/crypto-etf
#    bash setup_github.sh
#
#  하는 일
#    1. 키가 절대 안 올라가는지 검사
#    2. git 저장소 초기화 + 첫 커밋
#    3. GitHub 저장소 생성 + 업로드 + Secrets 등록  (gh CLI 가 있으면 자동)
#    4. Cloudflare Pages 프로젝트 만들고 첫 배포
# ══════════════════════════════════════════════════════════════════════════
set -u
cd "$(dirname "$0")"
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
ok(){   echo -e "  ${G}✓${N} $1"; }
warn(){ echo -e "  ${Y}!${N} $1"; }
err(){  echo -e "  ${R}✗${N} $1"; }
hd(){   echo -e "\n${B}$1${N}"; }

REPO="crypto-etf"          # GitHub 저장소 이름
PROJECT="crypto-etf"       # Cloudflare Pages 프로젝트 이름

echo -e "${B}══════════════════════════════════════════════════════════${N}"
echo -e "${B} 크립토 ETF — 맥을 꺼놔도 스스로 도는 상태로 만들기${N}"
echo -e "${B}══════════════════════════════════════════════════════════${N}"

# ── 1. 키 파일 확인 ────────────────────────────────────────────────────────
hd "[1/4] 키 확인"
CFG=""
for p in config.py ../config.py "$HOME/Desktop/config.py"; do
  [ -f "$p" ] && CFG="$p" && break
done
[ -z "$CFG" ] && { err "config.py 를 못 찾았습니다"; exit 1; }
ok "설정 파일: $CFG"

getval(){ grep -m1 -E "^[[:space:]]*$1[[:space:]]*=" "$CFG" 2>/dev/null \
          | sed -E 's/^[^=]*=[[:space:]]*//; s/^"//; s/"[[:space:]]*$//; s/^'"'"'//; s/'"'"'[[:space:]]*$//; s/[[:space:]]*$//'; }

KEYS=(KIS_APP_KEY KIS_APP_SECRET ECOS_API_KEY NAVER_CLIENT_ID NAVER_CLIENT_SECRET)
MISS=0
for k in "${KEYS[@]}"; do
  v="$(getval "$k")"
  if [ -z "$v" ]; then err "$k 없음"; MISS=1; else ok "$k  (${#v}자)"; fi
done
[ $MISS -eq 1 ] && warn "빠진 키는 나중에 직접 등록하셔야 합니다"

# Cloudflare 계정 ID — 테마보드에서 이미 쓰던 값을 찾아 쓴다
CFACC=""
for p in .wrangler/cache/pages.json ../theme-board/.wrangler/cache/pages.json \
         "$HOME/theme-board/.wrangler/cache/pages.json" \
         "$HOME/Desktop/theme-board/.wrangler/cache/pages.json"; do
  [ -f "$p" ] || continue
  CFACC=$(python3 -c "import json;print(json.load(open('$p')).get('account_id',''))" 2>/dev/null)
  [ -n "$CFACC" ] && { ok "Cloudflare 계정 ID 확인 (${p})"; break; }
done
[ -z "$CFACC" ] && warn "Cloudflare 계정 ID 를 못 찾았습니다 — 아래에서 직접 넣어주세요"

# ── 2. git ────────────────────────────────────────────────────────────────
hd "[2/4] git 저장소"
[ -d .git ] || { git init -q -b main && ok "git init"; }
git add -A >/dev/null 2>&1
if git diff --cached --quiet 2>/dev/null; then ok "커밋할 변경 없음"
else git commit -q -m "크립토 ETF — 자동 갱신 설정" && ok "커밋 완료"; fi

# 안전 확인 — 키가 커밋에 들어갔는지
BAD=0
for f in config.py .env .cache/kis_token.json; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 && { err "$f 가 git 에 들어가 있습니다!"; BAD=1; }
done
if [ $BAD -eq 1 ]; then
  echo "     git rm --cached config.py .env .cache/kis_token.json"
  echo "     git commit -m 'remove secrets'"
  exit 1
fi
ok "키 파일은 모두 제외됨 (안전)"

# ── 3. GitHub ─────────────────────────────────────────────────────────────
hd "[3/4] GitHub"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  ok "gh CLI 로그인 확인 — 자동으로 진행합니다"
  if git remote get-url origin >/dev/null 2>&1; then
    git push -u origin main -q && ok "업로드 완료"
  else
    echo "  저장소를 만듭니다 (공개 — Actions 실행시간 무제한 무료)"
    gh repo create "$REPO" --public --source=. --remote=origin --push \
      && ok "저장소 생성 + 업로드 완료" || err "저장소 생성 실패"
  fi
  echo "  Secrets 등록 중 …"
  for k in "${KEYS[@]}"; do
    v="$(getval "$k")"
    [ -n "$v" ] && gh secret set "$k" --body "$v" >/dev/null 2>&1 && ok "  $k"
  done
  [ -n "$CFACC" ] && gh secret set CLOUDFLARE_ACCOUNT_ID --body "$CFACC" >/dev/null 2>&1 \
    && ok "  CLOUDFLARE_ACCOUNT_ID"
  echo
  warn "CLOUDFLARE_API_TOKEN 하나는 직접 넣으셔야 합니다:"
  echo "     1) dash.cloudflare.com → 우측 상단 아이콘 → My Profile → API Tokens"
  echo "     2) Create Token → 'Edit Cloudflare Workers' 템플릿 → 만들기"
  echo "     3) gh secret set CLOUDFLARE_API_TOKEN --body \"<복사한값>\""
else
  warn "gh CLI 가 없거나 로그인되지 않았습니다 — 수동으로 진행합니다"
  # 값을 터미널에 뿌리지 않는다. 파일로 떨궈서 열어 보고 지우게 한다.
  OUT="_secrets_등록용.txt"
  { echo "GitHub → 저장소 → Settings → Secrets and variables → Actions"
    echo "아래를 하나씩 'New repository secret' 으로 등록하세요."
    echo "등록이 끝나면 이 파일은 지우세요."
    echo
    for k in "${KEYS[@]}"; do v="$(getval "$k")"; [ -n "$v" ] && printf "%s = %s\n" "$k" "$v"; done
    [ -n "$CFACC" ] && printf "%s = %s\n" "CLOUDFLARE_ACCOUNT_ID" "$CFACC"
    echo "CLOUDFLARE_API_TOKEN = (dash.cloudflare.com → My Profile → API Tokens 에서 발급)"
  } > "$OUT"
  grep -qx "$OUT" .gitignore 2>/dev/null || echo "$OUT" >> .gitignore
  ok "$OUT 에 적어 뒀습니다 — 등록 후 삭제하세요"
  echo -e "  ① GitHub 에서 새 저장소 '$REPO' 를 ${B}공개(public)${N}로 만드세요"
  echo "  ② git remote add origin https://github.com/<아이디>/$REPO.git"
  echo "     git push -u origin main"
  echo "  ③ 위 파일의 값들을 Secrets 로 등록"
fi

# ── 4. Cloudflare Pages ───────────────────────────────────────────────────
hd "[4/4] Cloudflare Pages 첫 배포"
echo "  브라우저가 열리면 로그인해 주세요 (처음 한 번만)"
npx --yes wrangler@latest pages project create "$PROJECT" --production-branch main 2>/dev/null \
  && ok "프로젝트 생성" || warn "이미 있거나 건너뜁니다"
if npx --yes wrangler@latest pages deploy web --project-name "$PROJECT" --branch main --commit-dirty=true; then
  ok "배포 완료 — 위에 찍힌 주소가 고객님이 들어올 주소입니다"
else
  err "배포 실패 — 로그인 상태를 확인하세요: npx wrangler login"
fi

echo -e "\n${B}══════════════════════════════════════════════════════════${N}"
echo -e " 끝. 이후로는 ${B}맥을 꺼놔도${N} 한국시간 07시·13시·19시에 자동으로 돌고,"
echo -e " 그 사이 속보는 20분마다 다시 긁습니다."
echo -e " 지금 바로 시험하려면:  ${B}gh workflow run '크립토 ETF 갱신'${N}"
echo -e "${B}══════════════════════════════════════════════════════════${N}"
