# -*- coding: utf-8 -*-
"""data/etf.json 생성 — 화면이 읽는 완성본.

수집(etf.py) + 코인·환율(market.py) 을 합쳐 하나의 정적 파일로 떨군다.
브라우저는 이 파일만 읽는다. 서버는 없다.
"""
import os, json, datetime, collections
import etf, market
from funds import BY_TICKER

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "data", "etf.json")
WEB  = os.path.join(HERE, "web", "etf.json")   # 화면이 읽는 위치
os.makedirs(os.path.dirname(OUT), exist_ok=True)
os.makedirs(os.path.dirname(WEB), exist_ok=True)

KST = datetime.timezone(datetime.timedelta(hours=9))


def _sum_recent(daily, days):
    """최근 N일 순유입 합계. 영상 속 '지난 주 / 지난 달 / 최근 3달' 카드용."""
    if not daily:
        return None
    cut = (datetime.datetime.now(KST) - datetime.timedelta(days=days)).strftime("%Y%m%d")
    return sum(d["total"] for d in daily if d["date"] > cut)


def aum_history(supply, price_hist):
    """일별 운용자산과 시총 대비 비중.

    코인마켓캡은 이 두 칸을 시계열로 보여준다. 우리도 스냅샷이 이미 하루치씩
    쌓이고 있으므로 그걸 되짚어 만들면 된다. 순유입과 같은 한계가 있다 —
    상장주식수 과거 이력이 없어 수집 시작일부터만 나온다.

    시가총액은 그날 코인 종가 × 지금 유통량으로 본다.
    유통량은 연 변동이 1% 안쪽이라 과거 유통량을 못 구해도 오차가 미미하다.
    """
    snaps = etf.load_snapshots()
    aum_daily, pct_daily = [], []
    for day in sorted(snaps):
        a = collections.defaultdict(float)
        for tkr, s in (snaps[day] or {}).items():
            meta = BY_TICKER.get(tkr, {})
            if (s.get("kind") or meta.get("kind", "spot")) != "spot":
                continue                                   # 선물·전략형은 뺀다
            u = s.get("underlying") or meta.get("underlying")
            v = s.get("aum_usd")
            if v is None and s.get("shares") and s.get("last"):
                v = s["shares"] * s["last"]
            if u and v:
                a[u] += v
        if not a:
            continue
        row = {"date": day, "BTC": round(a.get("BTC", 0.0), 2),
               "ETH": round(a.get("ETH", 0.0), 2), "ALL": round(sum(a.values()), 2)}
        aum_daily.append(row)

        # 같은 날 코인 종가가 있어야 비중을 낼 수 있다
        p = {c: (price_hist.get(c) or {}).get(day) for c in ("BTC", "ETH")}
        mc = {c: p[c] * supply[c] for c in ("BTC", "ETH") if p.get(c) and supply.get(c)}
        if mc:
            q = {"date": day}
            for c in ("BTC", "ETH"):
                if c in mc and a.get(c):
                    q[c] = round(a[c] / mc[c] * 100, 3)
            if len(mc) == 2 and row["ALL"]:
                q["ALL"] = round(row["ALL"] / (mc["BTC"] + mc["ETH"]) * 100, 3)
            if len(q) > 1:
                pct_daily.append(q)
    return aum_daily, pct_daily


def build(verbose=True):
    r  = etf.run(verbose)
    mk = market.collect(verbose)

    snapshot, flows = r["snapshot"], r["flows"]
    # 오늘 조회가 실패해 직전 스냅샷을 이어받았으면 화면에 알린다.
    stale_from = next((v.get("stale_from") for v in snapshot.values()
                       if v.get("stale_from")), None)
    shares_from = next((v.get("shares_from") for v in snapshot.values()
                        if v.get("shares_from")), None)
    n_shares_from = sum(1 for v in snapshot.values() if v.get("shares_from"))
    px_stale = sum(1 for v in snapshot.values()
                   if (v.get("px_source") or "").startswith("종가"))

    # ── 펀드 테이블 ────────────────────────────────────────────────
    funds = []
    for tkr, s in snapshot.items():
        meta = BY_TICKER.get(tkr, {})
        funds.append({
            "ticker": tkr,
            "name": s.get("eng_name") or meta.get("name", tkr),
            "issuer": meta.get("issuer", ""),
            "underlying": s["underlying"],
            "kind": s.get("kind") or meta.get("kind", "spot"),
            "exchange": s["excd"],
            "isin": s.get("isin", ""),
            "last": round(s["last"], 4),
            "shares": s["shares"],
            "aum_usd": round(s["aum_usd"], 2),
            # 한투 해외 거래량은 커버리지가 고르지 않다. 0 은 미제공으로 본다.
            "tvol": s.get("tvol") or None,
        })
    funds.sort(key=lambda x: -x["aum_usd"])

    # ── 총 AUM · 시총 대비 비중 ────────────────────────────────────
    aum      = collections.defaultdict(float)   # 전체(현물+전략형)
    aum_spot = collections.defaultdict(float)   # 현물만
    for x in funds:
        aum[x["underlying"]] += x["aum_usd"]
        if x["kind"] == "spot":
            aum_spot[x["underlying"]] += x["aum_usd"]
    aum_all      = sum(aum.values())
    aum_spot_all = sum(aum_spot.values())

    # 시총 대비 비중은 '현물 ETF가 실제로 흡수한 코인'을 보는 지표다.
    # 선물·전략형은 현물을 들고 있지 않으므로 넣으면 과대계상된다.
    pct = {}
    mcap = mk.get("mcap_usd") or {}
    aum_daily, pct_daily = aum_history(
        {k: v for k, v in (mk.get("supply") or {}).items() if not k.startswith("_")},
        mk.get("history") or {})
    for u in ("BTC", "ETH"):
        if mcap.get(u):
            pct[u] = round(aum_spot[u] / mcap[u] * 100, 2)
    if mcap.get("BTC") and mcap.get("ETH"):
        pct["ALL"] = round(aum_spot_all / (mcap["BTC"] + mcap["ETH"]) * 100, 2)

    # ── 순유입 일별 집계 ───────────────────────────────────────────
    by_day = collections.defaultdict(lambda: collections.defaultdict(float))
    for x in flows:
        u = BY_TICKER.get(x["ticker"], {}).get("underlying", "?")
        by_day[x["date"]][u] += x["flow_usd"]
    daily = [{"date": d,
              "BTC": round(v.get("BTC", 0.0), 2),
              "ETH": round(v.get("ETH", 0.0), 2),
              "total": round(sum(v.values()), 2)}
             for d, v in sorted(by_day.items())]

    # ── 펀드별 순유입 (차트의 '펀드별' 토글용) ──────────────────────
    by_fund = collections.defaultdict(lambda: collections.defaultdict(float))
    for x in flows:
        by_fund[x["date"]][x["ticker"]] += x["flow_usd"]

    # ── 가격 이력 (100일) ──────────────────────────────────────────
    price_days = sorted({d for v in r["prices"].values() for d in v})

    out = {
        "ts": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "date": r["date"],
        "fx": mk.get("fx"),
        "coins": {
            "krw": mk.get("krw"), "usd": mk.get("usd"),
            "supply": {k: v for k, v in (mk.get("supply") or {}).items() if not k.startswith("_")},
            "mcap_usd": mcap, "usd_source": mk.get("usd_source"),
            # 순유입 막대 위에 겹쳐 그릴 코인 일별 종가(달러)
            "history": mk.get("history") or {},
        },
        "funds": funds,
        "totals": {
            "aum_usd": {"BTC": round(aum["BTC"], 2), "ETH": round(aum["ETH"], 2),
                        "ALL": round(aum_all, 2)},
            "aum_spot_usd": {"BTC": round(aum_spot["BTC"], 2),
                             "ETH": round(aum_spot["ETH"], 2),
                             "ALL": round(aum_spot_all, 2)},
            "pct_of_mcap": pct,
            "aum_daily": aum_daily,
            "pct_daily": pct_daily,
        },
        "flows": {
            "daily": daily,
            "latest": daily[-1] if daily else None,
            "by_fund": {d: {k: round(v, 2) for k, v in f.items()} for d, f in by_fund.items()},
            "sum": {"week": _sum_recent(daily, 7),
                    "month": _sum_recent(daily, 30),
                    "quarter": _sum_recent(daily, 90)},
        },
        "prices": r["prices"],
        "stale_from": stale_from,
        "shares_from": shares_from,
        "n_shares_from": n_shares_from,
        "px_from_close": px_stale,
        "coverage": {
            "snapshot_days": len(etf.load_snapshots()),
            "price_days": len(price_days),
            "price_range": [price_days[0], price_days[-1]] if price_days else None,
            "note": ("상장주식수는 과거 이력이 제공되지 않아 순유입·AUM 시계열은 "
                     "수집 시작일부터 쌓입니다. 가격 차트는 100일이 채워집니다."),
        },
        "errors": mk.get("errors") or [],
    }

    for p in (OUT, WEB):
        json.dump(out, open(p, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))

    if verbose:
        kb = os.path.getsize(OUT) / 1024
        print("\n" + "=" * 56)
        print(f" data/etf.json · web/etf.json 생성  ({kb:,.0f} KB)")
        print("=" * 56)
        print(f"  펀드        {len(funds)}종목"
              + (f"   ⚠ {stale_from} 스냅샷 이어받음" if stale_from else "")
              + (f"   ⚠ {n_shares_from}종목 상장주식수는 {shares_from} 값"
                 if shares_from else "")
              + (f"   ({px_stale}종목은 최근 종가 사용)" if px_stale else ""))
        print(f"  총 AUM      BTC ${aum['BTC']/1e9:,.1f}B · ETH ${aum['ETH']/1e9:,.1f}B"
              f" · 합계 ${aum_all/1e9:,.1f}B")
        print(f"  현물만      BTC ${aum_spot['BTC']/1e9:,.1f}B · ETH ${aum_spot['ETH']/1e9:,.1f}B"
              f" · 합계 ${aum_spot_all/1e9:,.1f}B")
        if pct:
            print("  시총 대비   " + " · ".join(f"{k} {v}%" for k, v in pct.items())
                  + "   (현물 ETF 기준)")
        if daily:
            l = daily[-1]
            print(f"  최신 순유입 {l['date']}  BTC ${l['BTC']/1e6:+,.1f}M"
                  f" · ETH ${l['ETH']/1e6:+,.1f}M · 합계 ${l['total']/1e6:+,.1f}M")
        else:
            print("  최신 순유입 —  (스냅샷 2일치가 모이면 산출됩니다)")
        print(f"  가격 이력   {len(price_days)}일"
              + (f"  {price_days[0]} ~ {price_days[-1]}" if price_days else ""))
        print(f"  스냅샷      {out['coverage']['snapshot_days']}일치")
    return out


if __name__ == "__main__":
    build()
