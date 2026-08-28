#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════
#  크립토 ETF — 커뮤니티(로그인·댓글·좋아요·신고) 설정 (한 번만 실행)
#
#    cd ~/Desktop/crypto-etf
#    bash setup_community.sh
#
#  하는 일
#    1. Cloudflare D1 데이터베이스를 만들고 wrangler.toml 에 id 를 박는다
#    2. 표(스키마)를 올린다
#    3. 로그인 열쇠·관리자 등록 암호를 만들어 Cloudflare 에 넣는다
#    4. 카카오·네이버 키를 config.py 에서 읽어 함께 넣는다
#    5. 배포하고, 관리자 등록 주소를 알려준다
#
#  ※ 카카오·네이버 개발자 화면에서 먼저 해두실 게 있습니다.
#     아래 [사전 준비] 를 보세요.
# ══════════════════════════════════════════════════════════════════════════
set -u
cd "$(dirname "$0")"
G='\033[0;32m'; Y='\033[0;33m'; R='\033[0;31m'; N='\033[0m'; B='\033[1m'
ok(){   echo -e "  ${G}✓${N} $1"; }
warn(){ echo -e "  ${Y}!${N} $1"; }
err(){  echo -e "  ${R}✗${N} $1"; }
hd(){   echo -e "\n${B}$1${N}"; }
W="npx --yes wrangler@latest"
PROJECT="crypto-etf"
SITE="https://${PROJECT}.pages.dev"

echo -e "${B}══════════════════════════════════════════════════════════${N}"
echo -e "${B} 크립토 ETF — 커뮤니티 붙이기${N}"
echo -e "${B}══════════════════════════════════════════════════════════${N}"

echo -e "\n${B}[사전 준비]${N} 아직 안 하셨으면 지금 하세요."
cat <<EOT

  ● 카카오  developers.kakao.com → 내 애플리케이션
      · 앱 만들기 (또는 기존 앱)
      · 앱 설정 > 플랫폼 > Web 사이트 도메인:   ${SITE}
      · 제품 설정 > 카카오 로그인 : 활성화 ON
      · Redirect URI:                          ${SITE}/api/auth/kakao
      · 동의항목 : 닉네임(필수), 프로필 사진(선택)
      · 앱 키의 REST API 키 를 씁니다

  ● 네이버  developers.naver.com → 내 애플리케이션
      · 사용 API 에 '네이버 로그인' 추가 (검색 API 쓰던 앱에 같이 켜도 됩니다)
      · 서비스 URL:                            ${SITE}
      · Callback URL:                          ${SITE}/api/auth/naver
      · 제공 정보 : 닉네임 · 프로필 사진
      · Client ID / Client Secret 을 씁니다

EOT
read -r -p "  준비되셨으면 Enter (건너뛰려면 Ctrl+C) " _

# ── 0. 키 읽기 ────────────────────────────────────────────────────────────
hd "[0/5] 키 확인"
CFG=""
for p in config.py ../config.py "$HOME/Desktop/config.py"; do
  [ -f "$p" ] && CFG="$p" && break
done
getval(){ [ -n "$CFG" ] && grep -m1 -E "^[[:space:]]*$1[[:space:]]*=" "$CFG" 2>/dev/null \
          | sed -E 's/^[^=]*=[[:space:]]*//; s/^"//; s/"[[:space:]]*$//; s/^'"'"'//; s/'"'"'[[:space:]]*$//; s/[[:space:]]*$//'; }
[ -n "$CFG" ] && ok "설정 파일: $CFG" || warn "config.py 를 못 찾았습니다 — 값을 직접 물어보겠습니다"

ask(){   # ask 변수명 "설명" 기본값
  local cur="$3"
  if [ -n "$cur" ]; then
    read -r -p "  $2 [$(echo "$cur" | cut -c1-6)…] 그대로 쓰려면 Enter: " v
    echo "${v:-$cur}"
  else
    read -r -p "  $2: " v; echo "$v"
  fi
}
KAKAO_KEY=$(ask KAKAO "카카오 REST API 키" "$(getval KAKAO_REST_API_KEY)")
NAVER_ID=$(ask NID  "네이버 Client ID"     "$(getval NAVER_CLIENT_ID)")
NAVER_SEC=$(ask NSEC "네이버 Client Secret" "$(getval NAVER_CLIENT_SECRET)")
[ -z "$KAKAO_KEY$NAVER_ID" ] && { err "카카오·네이버 중 하나는 있어야 합니다"; exit 1; }

# ── 1. D1 ─────────────────────────────────────────────────────────────────
hd "[1/5] 데이터베이스(D1) 만들기"
if grep -q '__D1_ID__' wrangler.toml; then
  OUT=$($W d1 create "$PROJECT" 2>&1)
  ID=$(echo "$OUT" | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1)
  if [ -z "$ID" ]; then
    # 이미 있으면 목록에서 찾는다
    ID=$($W d1 list --json 2>/dev/null \
         | python3 -c "import json,sys;d=json.load(sys.stdin);print(next((x['uuid'] for x in d if x['name']=='$PROJECT'),''))" 2>/dev/null)
  fi
  [ -z "$ID" ] && { err "D1 생성 실패:"; echo "$OUT" | tail -5; exit 1; }
  python3 - "$ID" <<'PY'
import sys, re
p = "wrangler.toml"
s = open(p, encoding="utf-8").read().replace("__D1_ID__", sys.argv[1])
open(p, "w", encoding="utf-8").write(s)
PY
  ok "데이터베이스 생성 — id 를 wrangler.toml 에 넣었습니다"
else
  ok "이미 연결돼 있습니다 (wrangler.toml)"
fi

hd "[2/5] 표 올리기"
$W d1 execute "$PROJECT" --remote --file=schema.sql --yes >/dev/null 2>&1 \
  && ok "users · comments · likes · reports" \
  || { err "표 생성 실패 — 아래를 직접 실행해 보세요"; echo "     npx wrangler d1 execute $PROJECT --remote --file=schema.sql"; exit 1; }

# ── 3. 비밀값 ─────────────────────────────────────────────────────────────
hd "[3/5] 비밀값 넣기"
AUTH_SECRET=$(python3 -c "import secrets;print(secrets.token_hex(32))")
CLAIM=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))")

put(){  # put 이름 값
  [ -z "$2" ] && return 0
  printf '%s' "$2" | $W pages secret put "$1" --project-name "$PROJECT" >/dev/null 2>&1 \
    && ok "$1" || warn "$1 등록 실패 — 나중에 직접 넣으세요"
}
put AUTH_SECRET      "$AUTH_SECRET"
put ADMIN_CLAIM_CODE "$CLAIM"
put KAKAO_REST_KEY   "$KAKAO_KEY"
put NAVER_LOGIN_ID   "$NAVER_ID"
put NAVER_LOGIN_SECRET "$NAVER_SEC"

# ── 4. 배포 ───────────────────────────────────────────────────────────────
hd "[4/5] 배포"
if $W pages deploy; then
  ok "배포 완료"
else
  err "배포 실패 — 로그인 상태를 확인하세요: npx wrangler login"; exit 1
fi

# ── 5. 관리자 등록 ────────────────────────────────────────────────────────
hd "[5/5] 관리자 등록"
cat <<EOT

  ① ${SITE} 에 들어가 ${B}카카오 또는 네이버로 로그인${N} 하세요.
  ② 그 상태로 아래 주소를 여세요. 딱 한 번이면 됩니다.

     ${B}${SITE}/?admin=${CLAIM}${N}

  ③ "관리자로 등록되었습니다" 가 뜨면 머리말에 ${B}신고함${N} 이 생깁니다.

  이 암호는 여기 말고는 안 나옵니다. 등록하신 뒤에는 없애셔도 됩니다:
     npx wrangler pages secret delete ADMIN_CLAIM_CODE --project-name ${PROJECT}

EOT
echo -e "${B}══════════════════════════════════════════════════════════${N}"
echo -e " 끝. 저장소에도 올려두세요:"
echo -e "   ${B}git add -A && git commit -m '커뮤니티' && git push${N}"
echo -e "${B}══════════════════════════════════════════════════════════${N}"
