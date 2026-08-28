# -*- coding: utf-8 -*-
"""코인 시세 · 유통량 · 환율.

전부 무료 공개 API 또는 보유 키를 쓴다.
한 소스가 죽어도 나머지는 살아야 하므로 항목별로 try 를 분리하고,
실패하면 None 을 담아 화면에서 '—' 로 표시되게 한다.
"""
import os, json, datetime, urllib.parse, urllib.request
from kis import CFG, CACHE, http

KST = datetime.timezone(datetime.timedelta(hours=9))

# 마지막 수단 폴백 — 온체인 API가 모두 죽었을 때만 쓰인다.
FALLBACK_SUPPLY = {"BTC": 19_900_000.0, "ETH": 120_600_000.0}


def _try(fn, label, box):
    try:
        return fn()
    except Exception as e:
        box.append(f"{label}: {str(e)[:60]}")
        return None


# ══════════════════════════════════════════════════════════════════════
def upbit_krw():
    """업비트 원화 시세. 인증 불필요 · CORS 개방 → 브라우저도 직접 호출 가능."""
    url = "https://api.upbit.com/v1/ticker?markets=KRW-BTC,KRW-ETH"
    out = {}
    for r in http(url):
        sym = r["market"].split("-")[1]
        out[sym] = {"price_krw": r["trade_price"],
                    "change_rate": r["signed_change_rate"] * 100,
                    "acc_value_krw": r.get("acc_trade_price_24h")}
    return out


def _kraken_usd():
    """크라켄 달러 시세. c=현재가, o=당일 시가."""
    d = http("https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD")
    if d.get("error"):
        raise RuntimeError(str(d["error"])[:60])
    out = {}
    for k, v in (d.get("result") or {}).items():
        sym = "BTC" if "XBT" in k else ("ETH" if "ETH" in k else None)
        if not sym:
            continue
        last, op = float(v["c"][0]), float(v["o"])
        out[sym] = {"price_usd": last,
                    "change_rate": (last / op - 1) * 100 if op else None}
    if len(out) < 2:
        raise RuntimeError(f"응답에 BTC/ETH 가 없다: {list((d.get('result') or {}))}")
    return out


def _coinbase_usd():
    """코인베이스 현물가. 등락률은 안 준다."""
    out = {}
    for sym in ("BTC", "ETH"):
        d = http(f"https://api.coinbase.com/v2/prices/{sym}-USD/spot")
        out[sym] = {"price_usd": float(d["data"]["amount"]), "change_rate": None}
    return out


def _binance_usd():
    """바이낸스. 미국 아이피는 451(법적 차단)로 막힌다 — GitHub Actions 에서 못 쓴다."""
    q = urllib.parse.quote('["BTCUSDT","ETHUSDT"]')
    out = {}
    for r in http(f"https://api.binance.com/api/v3/ticker/24hr?symbols={q}"):
        sym = r["symbol"].replace("USDT", "")
        out[sym] = {"price_usd": float(r["lastPrice"]),
                    "change_rate": float(r["priceChangePercent"])}
    return out


def global_usd():
    """달러 시세 — 시가총액 계산의 근거다. 여기가 비면 '시총 대비 비중'이 통째로 빈다.

    바이낸스만 쓰다가 GitHub Actions(미국 아이피)에서 451 로 막혔다(2026-08-27 실측).
    미국에서도 열리는 크라켄을 앞에 세우고, 순서대로 살아 있는 걸 쓴다.
    업비트 원화를 환율로 나눠 쓰면 안 된다 — 김치프리미엄만큼 시총이 부풀려진다.
    """
    tried = []
    for fn, name in ((_kraken_usd, "크라켄"), (_coinbase_usd, "코인베이스"),
                     (_binance_usd, "바이낸스")):
        try:
            out = fn()
            out["_source"] = name
            return out
        except Exception as e:
            tried.append(f"{name}({str(e)[:40]})")
    raise RuntimeError("달러 시세 전부 실패 — " + " · ".join(tried))


def btc_supply():
    """비트코인 유통량. blockchain.info 는 사토시 단위 평문을 반환한다."""
    with urllib.request.urlopen("https://blockchain.info/q/totalbc", timeout=15) as r:
        return int(r.read().decode().strip()) / 1e8


def eth_supply():
    """이더리움 유통량.

    blockchair 는 응답 키가 바뀐 적이 있어(2026-08-25 'circulation' 없음)
    후보 키를 순서대로 찾고, 단위(wei/ether)도 값 크기로 판별한다."""
    d = http("https://api.blockchair.com/ethereum/stats", timeout=15)
    data = d.get("data") or {}
    for k in ("circulation", "circulation_approximate", "supply",
              "total_supply", "market_cap_supply"):
        v = data.get(k)
        if v in (None, ""):
            continue
        x = float(v)
        # wei 로 오면 1e18 로 나눈다. 이더 단위면 1억 언저리 값이다.
        if x > 1e24:
            x /= 1e18
        if 1e7 < x < 1e9:
            return x
    raise RuntimeError(f"유통량 키 없음 (받은 키: {','.join(list(data)[:8])})")


def fx_usdkrw():
    """원/달러 매매기준율 — 한국은행 ECOS. 통계표 731Y001 · 항목 0000001."""
    key = CFG.get("ECOS_API_KEY")
    if not key:
        raise RuntimeError("ECOS_API_KEY 없음")
    end   = datetime.datetime.now(KST)
    start = end - datetime.timedelta(days=10)          # 휴장일 대비 여유
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/20/"
           f"731Y001/D/{start:%Y%m%d}/{end:%Y%m%d}/0000001")
    d = http(url, timeout=15)
    rows = d.get("StatisticSearch", {}).get("row") or []
    if not rows:
        raise RuntimeError(f"ECOS 응답 비어 있음: {str(d)[:120]}")
    last = rows[-1]
    return {"rate": float(last["DATA_VALUE"]), "date": last["TIME"]}




# ══════════════════════════════════════════════════════════════════════
# 코인 일별 종가 — "돈이 들어올 때 값이 어떻게 움직였나"를 겹쳐 그리려면 이력이 있어야 한다.
# 현재가만으로는 못 그린다.
# ══════════════════════════════════════════════════════════════════════
_HIST = os.path.join(CACHE, "coin_prices.json")
KRAKEN_PAIR = {"BTC": "XBTUSD", "ETH": "ETHUSD"}


def _load_hist():
    try:
        d = json.load(open(_HIST, encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def coin_history(days=400):
    """크라켄 일봉으로 BTC·ETH 달러 종가를 받아 캐시에 합친다.

    받아온 게 없어도 캐시가 남아 있으면 그걸 쓴다 —
    하루 실패했다고 차트가 통째로 비면 안 된다.
    """
    hist = _load_hist()
    got = 0
    for sym, pair in KRAKEN_PAIR.items():
        try:
            d = http(f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=1440")
            if d.get("error"):
                raise RuntimeError(str(d["error"])[:60])
            rows = next((v for k, v in (d.get("result") or {}).items()
                         if isinstance(v, list)), None)
            if not rows:
                raise RuntimeError("일봉이 비어 있다")
            cur = hist.setdefault(sym, {})
            for r in rows:
                # [시각, 시가, 고가, 저가, 종가, vwap, 거래량, 체결수]
                day = datetime.datetime.fromtimestamp(
                    int(r[0]), datetime.timezone.utc).strftime("%Y%m%d")
                cur[day] = round(float(r[4]), 2)
                got += 1
        except Exception as e:
            raise RuntimeError(f"{sym} {str(e)[:50]}")

    # 오래된 건 버린다. 400일이면 '전체' 보기에도 넉넉하다.
    cut = (datetime.datetime.now(datetime.timezone.utc)
           - datetime.timedelta(days=days)).strftime("%Y%m%d")
    for sym in list(hist):
        hist[sym] = {k: v for k, v in hist[sym].items() if k >= cut}
    if got:
        json.dump(hist, open(_HIST, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
    return hist

# ══════════════════════════════════════════════════════════════════════
def collect(verbose=True):
    errs = []
    krw = _try(upbit_krw,  "업비트",    errs)
    usd = _try(global_usd, "달러시세",  errs)
    fx  = _try(fx_usdkrw,  "ECOS환율",  errs)
    hist = _try(coin_history, "코인 일봉", errs) or _load_hist()

    supply = {}
    b = _try(btc_supply, "BTC유통량", errs)
    e = _try(eth_supply, "ETH유통량", errs)
    supply["BTC"] = b or FALLBACK_SUPPLY["BTC"]
    supply["ETH"] = e or FALLBACK_SUPPLY["ETH"]
    supply["_fallback"] = [k for k, v in (("BTC", b), ("ETH", e)) if not v]
    # ETH 유통량은 연 변동이 1% 미만이라 폴백 상수를 써도 시총 오차는 미미하다.

    mcap = {}
    for sym in ("BTC", "ETH"):
        if usd and sym in usd:
            mcap[sym] = usd[sym]["price_usd"] * supply[sym]

    out = {"krw": krw, "usd": usd, "fx": fx, "supply": supply, "history": hist,
           "mcap_usd": mcap, "usd_source": (usd or {}).get("_source"), "errors": errs}

    if verbose:
        print("\n[코인·환율]")
        if fx:
            print(f"  환율     {fx['rate']:,.2f} 원/달러  ({fx['date']} 고시)")
        for sym in ("BTC", "ETH"):
            p_krw = krw[sym]["price_krw"] if krw and sym in krw else None
            p_usd = usd[sym]["price_usd"] if usd and sym in usd else None
            print(f"  {sym:<4} "
                  + (f"{p_krw:>13,.0f}원 " if p_krw else f"{'—':>14} ")
                  + (f"${p_usd:>11,.2f} " if p_usd else f"{'—':>13} ")
                  + (f" 시총 ${mcap[sym]/1e9:>8,.1f}B" if sym in mcap else ""))
        if usd and usd.get("_source"):
            print(f"  달러 시세 출처: {usd['_source']}")
        n_hist = {k: len(v) for k, v in (hist or {}).items()}
        if n_hist:
            print(f"  코인 일봉  " + " · ".join(f"{k} {v}일" for k, v in n_hist.items()))
        if supply["_fallback"]:
            print(f"  ! 유통량 폴백 사용: {', '.join(supply['_fallback'])}")
        for x in errs:
            print(f"  ! {x}")
    return out


if __name__ == "__main__":
    collect()
