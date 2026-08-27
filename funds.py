# -*- coding: utf-8 -*-
"""추적 대상 ETF 정의.

거래소 코드(excd)는 2026-08-25 전수 탐색으로 확정한 값이다.
한투는 Cboe BZX 상장 종목도 AMS 로 매핑한다.

kind
  spot    현물 보유. '시총 대비 비중' 계산에 들어간다.
  strat   선물·전략형. 현물 코인을 들고 있지 않으므로 비중 계산에서 뺀다.
          (넣으면 ETF가 실제보다 많은 코인을 흡수한 것처럼 보인다)
"""

FUNDS = [
    # 티커     거래소  기초    종류      발행사          표시명
    ("IBIT",  "NAS",  "BTC",  "spot",  "BlackRock",    "iShares Bitcoin Trust"),
    ("FBTC",  "AMS",  "BTC",  "spot",  "Fidelity",     "Fidelity Wise Origin Bitcoin"),
    ("GBTC",  "AMS",  "BTC",  "spot",  "Grayscale",    "Grayscale Bitcoin Trust"),
    ("BTC",   "AMS",  "BTC",  "spot",  "Grayscale",    "Grayscale Bitcoin Mini Trust"),
    ("BITB",  "AMS",  "BTC",  "spot",  "Bitwise",      "Bitwise Bitcoin ETF"),
    ("ARKB",  "AMS",  "BTC",  "spot",  "ARK/21Shares", "ARK 21Shares Bitcoin ETF"),
    ("BTCO",  "AMS",  "BTC",  "spot",  "Invesco",      "Invesco Galaxy Bitcoin ETF"),
    ("EZBC",  "AMS",  "BTC",  "spot",  "Franklin",     "Franklin Bitcoin ETF"),
    ("BRRR",  "NAS",  "BTC",  "spot",  "CoinShares",   "CoinShares Bitcoin ETF"),
    ("HODL",  "AMS",  "BTC",  "spot",  "VanEck",       "VanEck Bitcoin ETF"),
    ("BTCW",  "AMS",  "BTC",  "spot",  "WisdomTree",   "WisdomTree Bitcoin Fund"),
    # 선물·전략형 — 현물 미보유
    ("BITO",  "AMS",  "BTC",  "strat", "ProShares",    "ProShares Bitcoin Strategy"),
    ("BITS",  "NAS",  "BTC",  "strat", "Global X",     "Global X Blockchain & Bitcoin"),

    ("ETHA",  "NAS",  "ETH",  "spot",  "BlackRock",    "iShares Ethereum Trust"),
    ("ETHE",  "AMS",  "ETH",  "spot",  "Grayscale",    "Grayscale Ethereum Trust"),
    ("FETH",  "AMS",  "ETH",  "spot",  "Fidelity",     "Fidelity Ethereum Fund"),
    ("ETHW",  "AMS",  "ETH",  "spot",  "Bitwise",      "Bitwise Ethereum ETF"),
    ("QETH",  "AMS",  "ETH",  "spot",  "Invesco",      "Invesco Galaxy Ethereum ETF"),
    ("EZET",  "AMS",  "ETH",  "spot",  "Franklin",     "Franklin Ethereum ETF"),
    # 2026-08-25 1차 수집에서 빠져 있던 종목 — ETH 비중이 낮게 나온 원인
    ("ETH",   "AMS",  "ETH",  "spot",  "Grayscale",    "Grayscale Ethereum Mini Trust"),
    ("ETHV",  "AMS",  "ETH",  "spot",  "VanEck",       "VanEck Ethereum ETF"),
    ("CETH",  "AMS",  "ETH",  "spot",  "21Shares",     "21Shares Core Ethereum ETF"),
]

BY_TICKER = {t: dict(ticker=t, excd=e, underlying=u, kind=k, issuer=i, name=n)
             for t, e, u, k, i, n in FUNDS}

TICKERS = [t for t, *_ in FUNDS]
SPOT    = [t for t, e, u, k, *_ in FUNDS if k == "spot"]
