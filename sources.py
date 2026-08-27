# -*- coding: utf-8 -*-
"""뉴스·속보 소스 정의.

저작권 원칙 — 기사 본문은 저장하지 않는다.
  · 기본 저장·노출 항목: 제목 + 언론사 + 발행시각 + 원문 링크
  · 요약문(description)은 수집은 하되 SHOW_SUMMARY 가 False 면 출력에서 제외한다.
    한국저작권보호원 기준상 '요약하여 게재'도 이용허락 대상이며,
    영리 목적이면 손해배상 책임이 생길 수 있다.
    언론사 또는 한국언론진흥재단과 계약을 맺은 뒤에만 True 로 바꾼다.
"""

SHOW_SUMMARY = False

# ── RSS ──────────────────────────────────────────────────────────────
# cat: coin(코인 속보) / econ(경제 속보)
RSS = [
    ("blockmedia",   "블록미디어",        "https://www.blockmedia.co.kr/feed",              "ko", "coin"),
    ("tokenpost",    "토큰포스트",        "https://www.tokenpost.kr/rss",                   "ko", "coin"),
    ("coindeskkr",   "코인데스크 코리아", "https://www.coindeskkorea.com/feed/"                ,"ko", "coin"),
    ("cointelegraph","Cointelegraph",     "https://cointelegraph.com/rss",                  "en", "coin"),
    ("coindesk",     "CoinDesk",          "https://www.coindesk.com/arc/outboundfeeds/rss/","en", "coin"),
    ("decrypt",      "Decrypt",           "https://decrypt.co/feed",                        "en", "coin"),
    ("theblock",     "The Block",         "https://www.theblock.co/rss.xml",                "en", "coin"),
]

# ── 거래소 공지 ──────────────────────────────────────────────────────
# 상장·입출금 중단 같은 공지는 언론 기사가 아니라 거래소가 스스로 낸 고지라
# 저작권 제약이 다르고, 실제로 시세를 가장 크게 움직인다.
UPBIT_NOTICE = ("upbit", "업비트 공지",
                "https://api-manager.upbit.com/api/v1/announcements"
                "?os=web&page=1&per_page=30&category=all")

# ── 네이버 뉴스 검색 API ─────────────────────────────────────────────
NAVER_QUERIES = ["비트코인", "이더리움", "가상자산", "암호화폐 규제", "비트코인 ETF"]

# ── 중요도 판정 ──────────────────────────────────────────────────────
# 3 = 최상(주황 강조) · 2 = 상 · 1 = 보통 · 0 = 낮음
# 한국어 기사 제목은 "입출금 일시 중단"처럼 사이에 말이 끼어든다.
# 긴 구절을 통째로 넣으면 못 잡으므로 짧고 확실한 조각으로 둔다.
# "상장사·상장기업"은 주식 얘기지 코인 상장이 아니다. 정규식으로 걸러낸다.
KEY3_RE = [r"상장(?!사|기업|업체|지수|주)"]

KEY3 = ["상장폐지", "거래지원", "입출금", "출금 중단", "거래 중단",
        "해킹", "도난", "탈취", "유의종목", "긴급",
        "급등", "급락", "폭락", "폭등", "사상 최고", "신고가", "붕괴",
        "승인", "부결", "제재", "기소", "압수", "파산", "청산",
        "listing", "delist", "hack", "exploit", "stolen", "approve", "reject",
        "all-time high", "plunge", "surge", "halt", "suspend"]

KEY2 = ["ETF", "순유입", "순유출", "규제", "금융위", "금감원", "SEC",
        "스테이블코인", "발행", "매입", "매도", "고래", "돌파",
        "상회", "하회", "경신", "전망", "목표가", "보유",
        "inflow", "outflow", "regulat", "custody", "whale", "liquidation",
        "tops", "falls below", "outperform"]

# ── 경제 속보로 분류할 신호 ──────────────────────────────────────────
# 경제 속보 분류용 신호. 이 단어가 걸리면 중요도도 최소 2로 올린다
# (거시 뉴스는 제목이 밋밋해도 시세를 크게 움직인다).
ECON = ["연준", "FOMC", "기준금리", "금리", "국채", "채권", "CPI", "물가", "고용",
        "환율", "달러", "재무부", "재무장관", "무역", "관세", "유동성",
        "증시", "나스닥", "S&P", "다우",
        "fed", "treasury", "inflation", "yield", "jobs", "tariff", "liquidity"]

# ── 코인 태깅 ────────────────────────────────────────────────────────
COINS = {
    "BTC": ["비트코인", "bitcoin", "btc"],
    "ETH": ["이더리움", "ethereum", "eth"],
    "XRP": ["리플", "엑스알피", "xrp", "ripple"],
    "SOL": ["솔라나", "solana", "sol"],
    "DOGE": ["도지", "dogecoin", "doge"],
    "ADA": ["에이다", "카르다노", "cardano", "ada"],
    "USDT": ["테더", "tether", "usdt"],
    "USDC": ["usdc", "서클", "circle"],
}
