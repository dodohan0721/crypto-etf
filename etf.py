# -*- coding: utf-8 -*-
"""ETF 수집·산출.

  1) 가격 이력 : 한투 기간별시세 1회 호출 = 약 100일치. 받을 때마다 병합 누적.
  2) 상장주식수: 한투 상품기본정보. '현재 시점' 값만 오므로 매일 스냅샷을 쌓는다.
  3) 순유입    : (당일 상장주식수 − 전일 상장주식수) × 당일 종가

주의 — 상장주식수는 과거 이력이 제공되지 않는다.
따라서 순유입·AUM 시계열은 '스냅샷을 쌓기 시작한 날'부터 만들어진다.
가격 차트만 처음부터 100일이 채워진다.
"""
import os, time, json, datetime, collections
import kis
from kis import f
from funds import FUNDS, BY_TICKER

HERE   = os.path.dirname(os.path.abspath(__file__))
CACHE  = os.path.join(HERE, ".cache")
SNAPS  = os.path.join(CACHE, "shares")
PRICES = os.path.join(CACHE, "prices.json")
os.makedirs(SNAPS, exist_ok=True)

KST = datetime.timezone(datetime.timedelta(hours=9))

def today_kst():
    return datetime.datetime.now(KST).strftime("%Y%m%d")


# ══════════════════════════════════════════════════════════════════════
# 1. 오늘 스냅샷 — 현재가 + 상장주식수 + 메타
# ══════════════════════════════════════════════════════════════════════
def _fetch_one(tkr, excd, und, kind, issuer, name, px_hist=None):
    """px_hist: 이미 받아둔 {날짜: 종가}. 현재가가 안 올 때 여기서 가져온다.

    미국 장이 닫혀 있으면 현재가가 0 으로 온다. 예전에는 그때 다른 거래소를
    두드려봤는데, 22종목 × 거래소 3곳이면 호출이 66회 늘어 한투가 연결을
    끊어버렸다(2026-08-26 전 종목 실패). 우리는 이미 100일 종가를 갖고 있으므로
    추가 호출 없이 마지막 종가를 쓴다."""
    p = kis.ov_price(tkr, excd)
    i = kis.ov_info(tkr, excd)
    last, shares = f(p.get("last")), f(i.get("lstg_stck_num"))
    px_from = "실시간"

    if last <= 0 and px_hist:
        days = sorted(px_hist)
        if days:
            last, px_from = px_hist[days[-1]], f"종가 {days[-1]}"

    if last <= 0 or shares <= 0:
        raise ValueError(f"last={last} shares={shares} "
                         f"tried_prdt={i.get('_prdt_type_tried', '-')}")
    return {"ticker": tkr, "excd": excd, "underlying": und, "kind": kind,
            "issuer": issuer, "name": name,
            "last": last, "shares": shares, "aum_usd": last * shares,
            "tvol": f(p.get("tvol")),
            "px_source": px_from,
            "isin": (i.get("std_pdno") or "").strip(),
            "eng_name": (i.get("prdt_eng_name") or "").strip()}


def us_business_day(prices, fallback=None):
    """스냅샷이 실제로 담고 있는 '미국 영업일'.

    상장주식수는 미국 장 기준으로 갱신되는데 우리는 한국 시간에 돌린다.
    한국 날짜로 이름을 붙이면 같은 미국 영업일 데이터가 두 파일로 갈라지고,
    그 사이 순유입이 0 인 가짜 하루가 생긴다(2026-08-27 실측).
    기간시세의 최신 날짜가 곧 그 기준일이므로 그걸 쓴다."""
    days = [d for v in (prices or {}).values() for d in v]
    return max(days) if days else (fallback or today_kst())


def collect_snapshot(prices=None, verbose=True):
    day  = us_business_day(prices)
    path = os.path.join(SNAPS, f"{day}.json")

    # 같은 날 스냅샷이 이미 있으면 그 위에 덮어쓴다.
    # 부분 실패한 실행이 기존 스냅샷을 통째로 날리면
    # 다음 날 순유입에서 그 종목들이 통으로 빠진다.
    rows = {}
    if os.path.exists(path):
        try:
            rows = json.load(open(path)).get("rows") or {}
        except Exception:
            rows = {}

    if verbose:
        print(f"\n[2/3] 스냅샷 수집 — {len(FUNDS)}종목  ·  기준일 {day} (미국 영업일)"
              + (f"  · 기존 {len(rows)}종목에 병합" if rows else ""))
        print(f"  {'티커':<7}{'종가':>10}{'상장주식수':>16}{'AUM($B)':>10}")
        print("  " + "-" * 44)

    prices = prices or {}
    fails = []
    # 서버 오류(500)가 연달아 나오면 그날 API 가 죽은 것이다.
    # 남은 종목을 계속 두드려봐야 같은 답만 오고 시간만 버린다.
    server_down, BREAK_AT = 0, 4
    for tkr, excd, und, kind, issuer, name in FUNDS:
        if server_down >= BREAK_AT:
            fails.append((tkr, excd, und, kind, issuer, name, "건너뜀 (서버 오류 연속)"))
            continue
        try:
            r = _fetch_one(tkr, excd, und, kind, issuer, name, prices.get(tkr))
            rows[tkr] = r
            if verbose:
                print(f"  {tkr:<7}{r['last']:>10.4f}{r['shares']:>16,.0f}"
                      f"{r['aum_usd']/1e9:>10.2f}")
        except Exception as e:
            m = str(e)
            server_down = server_down + 1 if ("HTTP Error 5" in m) else 0
            if server_down == BREAK_AT and verbose:
                print(f"  ── 서버 오류 {BREAK_AT}회 연속 → 남은 종목 건너뜀 ──")
            fails.append((tkr, excd, und, kind, issuer, name, m[:70]))

    # 실패분 재시도 — 연결이 끊겼던 것이라면 잠시 쉬면 대개 살아난다
    if fails and server_down < BREAK_AT:
        if verbose:
            print(f"  ── {len(fails)}종목 실패, 20초 쉬고 재시도 ──")
        time.sleep(20)
        still = []
        for tkr, excd, und, kind, issuer, name, msg in fails:
            try:
                r = _fetch_one(tkr, excd, und, kind, issuer, name, prices.get(tkr))
                rows[tkr] = r
                if verbose:
                    print(f"  {tkr:<7}{r['last']:>10.4f}{r['shares']:>16,.0f}"
                          f"{r['aum_usd']/1e9:>10.2f}  (재시도 성공)")
            except Exception as e:
                still.append((tkr, str(e)[:70]))
        fails = still
    else:
        if fails and verbose:
            print(f"  ── 서버 오류라 재시도 생략 ({len(fails)}종목) ──")
        # 재시도를 건너뛰면 fails 가 7칸 튜플 그대로 남는다.
        # 아래 출력부는 (티커, 메시지) 두 칸을 기대하므로 여기서 모양을 맞춘다.
        fails = [(f[0], f[-1]) for f in fails]

    # 못 받은 종목은 살아있는 조각으로 최대한 메운다.
    #   상장주식수는 직전 스냅샷 값을, 종가는 오늘 받은 기간시세를 쓴다.
    #   (2026-08-26 한투 현재가·상품정보가 500 인데 기간시세는 살아있었다)
    # 통째로 어제 값을 쓰는 것보다 AUM 이 정확하고, 화면도 비지 않는다.
    carried = partial = 0
    missing = [t for t, *_ in FUNDS if t not in rows]
    if missing:
        prev_rows = {}
        for fn in reversed([f for f in sorted(os.listdir(SNAPS))
                            if f.endswith(".json") and f != f"{day}.json"]):
            try:
                cand = json.load(open(os.path.join(SNAPS, fn))).get("rows") or {}
            except Exception:
                continue
            if cand:
                prev_rows, prev_day = cand, fn[:8]
                break
        for tkr in missing:
            o = prev_rows.get(tkr)
            if not o:
                continue
            ph = prices.get(tkr) or {}
            days_ = sorted(ph)
            if days_ and ph[days_[-1]] > 0:
                last = ph[days_[-1]]
                rows[tkr] = dict(o, last=last, aum_usd=last * o["shares"],
                                 px_source=f"종가 {days_[-1]}",
                                 shares_from=prev_day)
                partial += 1
            else:
                rows[tkr] = dict(o, stale_from=prev_day)
                carried += 1
        if verbose and (partial or carried):
            msg = []
            if partial:
                msg.append(f"{partial}종목은 오늘 종가 + {prev_day} 상장주식수로 메움")
            if carried:
                msg.append(f"{carried}종목은 {prev_day} 값 그대로")
            print(f"  ── {' · '.join(msg)} ──")

    json.dump({"date": day, "rows": rows, "carried": carried,
               "partial": partial}, open(path, "w"),
              ensure_ascii=False, indent=1)

    if verbose:
        tot = sum(r["aum_usd"] for r in rows.values()) / 1e9
        print(f"  → {len(rows)}/{len(FUNDS)}종목 저장  총 AUM ${tot:.1f}B"
              f"   미수집 {len(fails)}건")
        for f in fails:
            print(f"     ! {f[0]}: {f[-1]}")
        missing = [t for t, *_ in FUNDS if t not in rows]
        if missing:
            print(f"     미수집 종목: {', '.join(missing)}")
    return day, rows


# ══════════════════════════════════════════════════════════════════════
# 2. 가격 이력 — 100일씩 받아 병합
# ══════════════════════════════════════════════════════════════════════
def backfill_prices(verbose=True):
    hist = {}
    if os.path.exists(PRICES):
        try:
            hist = json.load(open(PRICES))
        except Exception:
            hist = {}
    if verbose:
        print(f"\n[1/3] 가격 이력 백필")

    for tkr, excd, *_ in FUNDS:
        try:
            rows = kis.ov_daily(tkr, excd)
        except Exception as e:
            if verbose:
                print(f"  ! {tkr}: {str(e)[:50]}")
            continue
        cur = hist.setdefault(tkr, {})
        added = 0
        for r in rows:
            d, c = (r.get("xymd") or "").strip(), f(r.get("clos"))
            if len(d) == 8 and c > 0:
                if d not in cur:
                    added += 1
                cur[d] = c
        if verbose:
            print(f"  {tkr:<7} 수신 {len(rows):>3}일  신규 {added:>3}일  누적 {len(cur):>4}일")

    json.dump(hist, open(PRICES, "w"), separators=(",", ":"))
    if verbose:
        days = sorted({d for v in hist.values() for d in v})
        print(f"  → 저장  종목 {len(hist)}개 · 날짜 {len(days)}일"
              + (f" ({days[0]} ~ {days[-1]})" if days else ""))
    return hist


# ══════════════════════════════════════════════════════════════════════
# 3. 순유입 산출 — 스냅샷 두 개 이상일 때만
# ══════════════════════════════════════════════════════════════════════
def load_snapshots():
    out = {}
    for fn in sorted(os.listdir(SNAPS)):
        if fn.endswith(".json"):
            try:
                d = json.load(open(os.path.join(SNAPS, fn)))
                out[d["date"]] = d["rows"]
            except Exception:
                pass
    return out


def compute_flows(verbose=True):
    snaps = load_snapshots()
    days  = sorted(snaps)
    if verbose:
        print(f"\n[3/3] 순유입 산출 — 스냅샷 {len(days)}일치")

    flows = []                       # [{date, ticker, shares_delta, flow_usd}]
    for prev, cur in zip(days, days[1:]):
        a, b = snaps[prev], snaps[cur]
        for tkr, r in b.items():
            o = a.get(tkr)
            if not o:
                continue
            # 이어받은 값은 그날 실제로 조회한 게 아니라 변화량이 0 으로 보인다.
            # 없는 날로 취급해야 나중에 진짜 값이 들어왔을 때 제대로 계산된다.
            if (r.get("stale_from") or o.get("stale_from")
                    or r.get("shares_from") or o.get("shares_from")):
                continue
            ds = r["shares"] - o["shares"]
            flows.append({"date": cur, "ticker": tkr,
                          "shares_delta": ds, "flow_usd": ds * r["last"]})

    if verbose:
        if len(days) < 2:
            print("  스냅샷이 1일치뿐 — 내일 한 번 더 돌리면 순유입이 나옵니다.")
        else:
            by_day = collections.defaultdict(float)
            for x in flows:
                by_day[x["date"]] += x["flow_usd"]
            for d in sorted(by_day)[-5:]:
                print(f"  {d}  총 순유입 ${by_day[d]/1e6:+,.1f}M")
    return flows


# ══════════════════════════════════════════════════════════════════════
def run(verbose=True):
    # 가격 이력을 먼저 받는다. 현재가가 안 올 때 스냅샷이 이걸 쓴다.
    prices    = backfill_prices(verbose)
    day, rows = collect_snapshot(prices, verbose)
    flows     = compute_flows(verbose)
    return {"date": day, "snapshot": rows, "prices": prices, "flows": flows}


if __name__ == "__main__":
    print("=" * 56)
    print(" ETF 수집기 — Day 1")
    print("=" * 56)
    r = run()
    print("\n" + "=" * 56)
    print(f" 완료  종목 {len(r['snapshot'])}개 · 가격이력 {len(r['prices'])}종목 · 순유입 {len(r['flows'])}건")
    print("=" * 56)
