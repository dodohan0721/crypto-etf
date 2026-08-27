# -*- coding: utf-8 -*-
"""코인 시세 · 유통량 · 환율.

전부 무료 공개 API 또는 보유 키를 쓴다.
한 소스가 죽어도 나머지는 살아야 하므로 항목별로 try 를 분리하고,
실패하면 None 을 담아 화면에서 '—' 로 표시되게 한다.
"""
import json, datetime, urllib.parse, urllib.request
from kis import CFG, http

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


def binance_usd():
    """바이낸스 달러 시세."""
    q = urllib.parse.quote('["BTCUSDT","ETHUSDT"]')
    out = {}
    for r in http(f"https://api.binance.com/api/v3/ticker/24hr?symbols={q}"):
        sym = r["symbol"].replace("USDT", "")
        out[sym] = {"price_usd": float(r["lastPrice"]),
                    "change_rate": float(r["priceChangePercent"])}
    return out


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
def collect(verbose=True):
    errs = []
    krw = _try(upbit_krw,   "업비트",   errs)
    usd = _try(binance_usd, "바이낸스", errs)
    fx  = _try(fx_usdkrw,   "ECOS환율", errs)

    supply = {}
    b = _try(btc_supply, "BTC유통량", errs)
    e = _try(eth_supply, "ETH유통량", errs)
    supply["BTC"] = b or FALLBACK_SUPPLY["BTC"]
    supply["ETH"] = e or FALLBACK_SUPPLY["ETH"]
    supply["_fallback"] = [k for k, v in (("BTC", b), ("ETH", e)) if not v]
    # ETH 유통량은 연 변동이 1% 미만이라 폴백 상수를 써도 시총 오차는 미미하다.

    mcap, kimchi = {}, {}
    for sym in ("BTC", "ETH"):
        if usd and sym in usd:
            mcap[sym] = usd[sym]["price_usd"] * supply[sym]
        if krw and usd and fx and sym in krw and sym in usd:
            implied = krw[sym]["price_krw"] / fx["rate"]
            kimchi[sym] = (implied / usd[sym]["price_usd"] - 1) * 100

    out = {"krw": krw, "usd": usd, "fx": fx, "supply": supply,
           "mcap_usd": mcap, "kimchi_pct": kimchi, "errors": errs}

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
                  + (f" 시총 ${mcap[sym]/1e9:>8,.1f}B" if sym in mcap else "")
                  + (f"  김프 {kimchi[sym]:+.2f}%" if sym in kimchi else ""))
        if supply["_fallback"]:
            print(f"  ! 유통량 폴백 사용: {', '.join(supply['_fallback'])}")
        for x in errs:
            print(f"  ! {x}")
    return out


if __name__ == "__main__":
    collect()
