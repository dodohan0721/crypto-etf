# -*- coding: utf-8 -*-
"""밤사이 한국증시 — EWY(MSCI 한국 ETF) 시세.

고객이 요청한 건 코스피200 야간선물이었다. 그건 CME 상품이라 실시간 시세에
거래소 이용료가 붙는다 — 무료 원칙과 안 맞는다.

대신 EWY 를 쓴다. 뉴욕에 상장된 MSCI 한국 ETF 로, 한국이 잠든 22:30~05:00 KST 에
미국 시장에서 거래된다. 한국 증시가 밤사이 어떻게 평가됐는지 보는 대용 지표로
실제 시장에서 널리 쓰인다. 우리는 이미 같은 한투 해외주식 API 로 ETF 21종목을
받고 있으므로 종목 하나가 늘 뿐이다 — 추가 비용도, 새 연동도 없다.

호출은 두 번(현재가·일봉)이라 속보 루프에 얹어도 부담이 없다.
실패하면 아무것도 쓰지 않는다. 화면은 파일이 없으면 그 칸을 접는다.
"""
import os, json, datetime
import kis

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "data", "night.json")
WEB  = os.path.join(HERE, "web", "night.json")
KST  = datetime.timezone(datetime.timedelta(hours=9))

SYMBOL = "EWY"
# EWY 는 뉴욕 아카(NYSE Arca) 상장이다. 한투 코드로는 AMS 로 잡히는데,
# 분류가 바뀐 적이 있어 순서대로 두드린다. 성공한 거래소만 쓴다.
EXCHANGES = ["AMS", "NYS", "NAS"]


def f(v, d=0.0):
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return d


def quote():
    """현재가. 미국 장이 닫혀 있으면 last 가 0 으로 온다 — 그때는 일봉 종가를 쓴다."""
    last_err = None
    for excd in EXCHANGES:
        try:
            p = kis.ov_price(SYMBOL, excd) or {}
            if f(p.get("last")) > 0 or f(p.get("base")) > 0:
                return excd, p
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    raise RuntimeError("EWY 현재가가 어느 거래소에서도 안 온다")


def history(excd, days=20):
    """일봉. 스파크라인용이라 20일이면 넉넉하다."""
    rows = kis.ov_daily(SYMBOL, excd) or []
    out = []
    for r in rows:
        d, c = (r.get("xymd") or "").strip(), f(r.get("clos"))
        if len(d) == 8 and c > 0:
            out.append({"date": d, "close": round(c, 2)})
    out.sort(key=lambda x: x["date"])
    return out[-days:]


def collect(verbose=True):
    excd, p = quote()
    hist = []
    try:
        hist = history(excd)
    except Exception:
        pass                      # 스파크라인은 없어도 숫자는 나온다

    last, base = f(p.get("last")), f(p.get("base"))
    src = "실시간"
    if last <= 0:
        if len(hist) >= 2:
            last, base, src = hist[-1]["close"], hist[-2]["close"], f"종가 {hist[-1]['date']}"
        elif hist:
            last, src = hist[-1]["close"], f"종가 {hist[-1]['date']}"

    if last <= 0:
        raise RuntimeError("EWY 가격을 못 구했다")

    rate = f(p.get("rate")) if src == "실시간" else (
        (last / base - 1) * 100 if base else 0.0)

    out = {
        "ts": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "symbol": SYMBOL,
        "name": "MSCI 한국 ETF",
        "excd": excd,
        "last": round(last, 2),
        "prev": round(base, 2) if base else None,
        "rate": round(rate, 2),
        "source": src,
        "history": hist,
    }
    for path in (OUT, WEB):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(out, open(path, "w", encoding="utf-8"),
                  ensure_ascii=False, separators=(",", ":"))
    if verbose:
        print(f"[밤사이 한국증시] {SYMBOL}@{excd} ${out['last']:,.2f} "
              f"{out['rate']:+.2f}%  ({src} · 일봉 {len(hist)}일)")
    return out


if __name__ == "__main__":
    try:
        collect()
    except Exception as e:
        # 여기서 죽으면 속보 루프까지 멈춘다. 조용히 넘긴다.
        print(f"!! 밤사이 한국증시 수집 실패 — {str(e)[:80]}")
