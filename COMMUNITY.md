# 커뮤니티 — 로그인 · 댓글 · 좋아요 · 신고

속보 하나하나에 **호재/악재를 찍고** 한마디를 남길 수 있게 했습니다.
빈 게시판을 먼저 여는 대신 **이미 하루 200건씩 들어오는 속보에 붙였습니다** —
사람이 없을 때도 화면이 비어 보이지 않기 때문입니다.

```bash
cd ~/Desktop/crypto-etf
bash setup_community.sh
```

---

## 어떻게 돌아가나

화면은 그대로 정적 파일입니다. 커뮤니티만 `/api/*` 를 부르고,
그 뒤는 **Cloudflare Pages Functions** 가 받습니다. 서버를 따로 띄우지 않습니다.

```
  브라우저 ──▶ crypto-etf.pages.dev
                ├── index.html · etf.json · news.json   (그냥 파일)
                └── /api/*  ─▶ Pages Functions ─▶ D1 (SQLite)
```

| 저장소 | 무료 한도 | 우리가 쓰는 양 |
|---|---|---|
| Pages Functions | 하루 10만 요청 | 방문자 1명당 3~5회 |
| D1 (SQLite) | 5GB · 하루 500만 읽기 / 10만 쓰기 | 댓글·투표 1건 = 1쓰기 |

## 커뮤니티 탭 (자유 게시판)

속보 댓글만으로는 사람들이 스스로 이야기를 꺼낼 자리가 없습니다. 게시판을 따로 뒀습니다.

글에 붙는 **호재/악재·댓글·신고는 속보에 쓰던 배관을 그대로** 씁니다.
대상 id 자리에 `p<글번호>` 를 넣을 뿐입니다 — 표를 두 벌로 만들면
신고 처리와 관리자 화면도 두 벌로 유지해야 합니다.

| | |
|---|---|
| 글쓰기 | 제목 2~80자 · 본문 2000자 · **30초에 하나** |
| 링크·리딩방 | 제목과 본문 모두 거부 |
| 삭제 | 본인 또는 관리자 (행은 남겨 두므로 되살릴 수 있음) |
| 신고 | 서로 다른 세 사람이면 자동으로 가려짐 |
| 공유 | `?p=<번호>` 주소가 그 글로 곧장 데려갑니다 |

관리자 **신고함**은 게시글과 댓글을 나눠서 보여줍니다.

## 호재 / 악재

코인니스에서 사람들이 실제로 누르는 건 댓글이 아니라 이겁니다 — 실측 화면에서
한 기사가 📈196 · 📉43 · 💬0 이었습니다. 그래서 첫날 만든 '좋아요'를 두 방향으로 바꿨습니다.

한 사람이 한 기사에 하나만 듭니다. 다시 누르면 취소, 반대를 누르면 갈아탑니다.
합계가 부풀지 않습니다.

첫날의 `likes` 표는 이제 안 씁니다(운영 데이터 0건이었습니다). 지우시려면:

```bash
npx wrangler d1 execute crypto-etf --remote --command "DROP TABLE IF EXISTS likes"
```

## 로그인

카카오·네이버 둘 다 받습니다. **닉네임과 프로필 사진만** 가져옵니다 —
이메일·연락처는 요청하지 않습니다. 받지 않으면 지킬 일도 없습니다.

세션은 서버에 저장하지 않고 **HMAC 서명한 쿠키** 하나로 끝냅니다.
테마보드에서 쓰시던 방식 그대로입니다. Workers 처럼 상태가 없는 환경에 맞습니다.

## 도배·스캠 대비

코인 커뮤니티가 망하는 길은 대체로 리딩방 도배입니다. 미리 막아 둡니다.

| 막는 것 | 어떻게 |
|---|---|
| 링크 | 아예 못 씁니다. `http`, `www.`, 흔한 도메인 꼬리까지 |
| 리딩방·오픈채팅 안내 | 낱말로 걸러냅니다 |
| 도배 | 10초에 하나, 1분에 셋까지 |
| 같은 글자 반복 | 16자 넘게 이어지면 거부 |
| 신고 | 서로 다른 세 사람이 신고하면 자동으로 가려집니다 |

관리자는 머리말의 **신고함** 에서 글 삭제·되살리기·이용자 차단을 합니다.
지운 글도 행은 남겨 두므로 잘못 지웠으면 되살릴 수 있습니다.

## 첫 관리자

"먼저 가입한 사람이 관리자" 로 하면 남이 먼저 들어왔을 때 사이트를 통째로 내줍니다.
그래서 설정 스크립트가 **한 번짜리 암호**를 만들고, 그걸 아는 사람만 관리자가 됩니다.

```
https://crypto-etf.pages.dev/?admin=<암호>
```

등록한 뒤에는 암호를 지워도 됩니다.

```bash
npx wrangler pages secret delete ADMIN_CLAIM_CODE --project-name crypto-etf
```

## 넣어야 할 값 (Cloudflare Pages 쪽)

GitHub Secrets 가 아니라 **Cloudflare Pages 프로젝트**에 들어갑니다.
Functions 가 실행될 때 읽는 값이라 그렇습니다. 설정 스크립트가 다 넣습니다.

| 이름 | 무엇 |
|---|---|
| `AUTH_SECRET` | 쿠키 서명 열쇠 (스크립트가 무작위로 만듭니다) |
| `ADMIN_CLAIM_CODE` | 첫 관리자 등록용 한 번짜리 암호 |
| `KAKAO_REST_KEY` | 카카오 REST API 키 |
| `NAVER_LOGIN_ID` / `NAVER_LOGIN_SECRET` | 네이버 로그인 |

## 손으로 만져야 할 때

```bash
# 댓글 몇 개나 쌓였나
npx wrangler d1 execute crypto-etf --remote \
  --command "SELECT COUNT(*) FROM comments WHERE deleted=0"

# 특정 이용자 차단
npx wrangler d1 execute crypto-etf --remote \
  --command "UPDATE users SET blocked=1 WHERE id='kakao:12345'"

# 관리자 한 명 더
npx wrangler d1 execute crypto-etf --remote \
  --command "UPDATE users SET role='admin' WHERE nick='홍길동'"
```

## 시험

`wrangler pages dev` 로 Workers 런타임과 D1 을 그대로 띄워
52가지를 확인했습니다 — 위조 증표, 남의 글 삭제, 링크 거부, 도배 제한,
신고 누적 자동 가림, 관리자 권한 우회, 자기 자신 차단 시도,
호재→악재 갈아타기에서 합계가 안 늘어나는지,
게시판의 30초 제한과 신고 누적 가림까지.
