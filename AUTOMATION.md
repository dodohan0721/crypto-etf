# 맥을 꺼놔도 스스로 도는 상태로

지금은 맥에서 `python3 build.py` · `python3 news.py` 를 직접 돌려야 화면이 바뀝니다.
아래 한 줄이면 **GitHub 서버가 대신 돌리고, 결과를 자동으로 배포**합니다.

```bash
cd ~/Desktop/crypto-etf
bash setup_github.sh
```

---

## 무엇이 언제 도는가

| 한국시간 | 하는 일 |
|---|---|
| 07:00 | 미국 장 마감 뒤 **ETF 집계** — 상장주식수·종가·AUM·순유입 |
| 07:00 ~ 12:30 | **속보 20분마다** 다시 긁고 배포 |
| 13:00 ~ 18:30 | 오후 작업이 이어받아 계속 |
| 19:00 ~ 00:30 | 저녁 작업이 이어받아 계속 |

ETF 집계는 하루 한 번이면 충분합니다. 미국 장은 하루 한 번 닫히고,
상장주식수도 그때 한 번 바뀝니다. 속보만 하루 종일 들어옵니다.

> **왜 크론을 20분마다 걸지 않았나**
> GitHub 의 schedule 은 "최선을 다하지만 보장하지 않는" 방식이라
> 잦은 주기는 대부분 무시됩니다(테마보드 실측: 하루 28회 예상 → 실제 5회).
> 그래서 크론은 하루 세 번만 쓰고, **실행된 작업 안에서 반복**합니다.

## 순유입 이력은 저장소에 남습니다

순유입은 `(오늘 상장주식수 − 어제 상장주식수) × 종가` 로 냅니다.
**어제 값이 없으면 하루치가 통째로 빕니다.** 그래서 매 실행마다
`data/` 와 `.cache/shares/` 를 저장소로 되돌려 커밋합니다.
GitHub Actions 캐시는 일주일이면 지워지기 때문에 거기에만 두면 안 됩니다.

## 등록해야 할 Secrets

| 이름 | 어디서 |
|---|---|
| `KIS_APP_KEY` `KIS_APP_SECRET` | `config.py` — 스크립트가 자동 등록 |
| `ECOS_API_KEY` | 〃 (한국은행 환율) |
| `NAVER_CLIENT_ID` `NAVER_CLIENT_SECRET` | 〃 (네이버 뉴스) |
| `CLOUDFLARE_ACCOUNT_ID` | 테마보드 설정에서 자동으로 찾아 씁니다 |
| `CLOUDFLARE_API_TOKEN` | **직접 발급** — dash.cloudflare.com → My Profile → API Tokens |

`config.py` 는 `.gitignore` 로 막혀 있어 저장소에 올라가지 않습니다.
스크립트가 커밋 직전에 실제로 제외됐는지 검사도 합니다.

## 확인

저장소 → **Actions** 탭 → `크립토 ETF 갱신` → **Run workflow**.
또는 터미널에서:

```bash
gh workflow run '크립토 ETF 갱신'
gh run watch
```

## 저장소를 공개(public)로 두는 이유

공개면 Actions 실행 시간이 **무제한 무료**입니다.
비공개는 월 2,000분인데, 하루 5시간짜리 작업 세 개면 금방 넘깁니다.
키는 `.gitignore` 와 Secrets 로 분리돼 있어 공개해도 새지 않습니다.
