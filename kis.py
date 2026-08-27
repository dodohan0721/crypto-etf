# -*- coding: utf-8 -*-
"""한국투자증권 OpenAPI 클라이언트 — 해외주식(ETF) 전용.

theme-board/server.py 에서 검증된 토큰 캐시·레이트리미터를 그대로 가져오고,
조회부만 domestic-stock → overseas-price 로 교체했다.

  · 접근토큰은 24시간 유효하고 1분에 1회만 발급 가능 → 반드시 파일 캐시
  · 호출 유량은 초당 20건 제한 → 토큰버킷으로 16건까지만 통과
"""
import os, re, sys, json, time, threading, urllib.parse, urllib.request

HERE  = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
os.makedirs(CACHE, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════
# 설정 로딩 — config.py 를 import 하지 않고 정규식으로 읽는다.
#   import 하면 그 파일에 문법 오류가 있을 때 이쪽까지 죽는다.
#   환경변수가 있으면 그쪽이 우선 (GitHub Actions 대응).
# ══════════════════════════════════════════════════════════════════════
KEYS = ("KIS_APP_KEY", "KIS_APP_SECRET", "KIS_ENV", "ACCOUNT",
        "ECOS_API_KEY", "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET",
        "FRED_API_KEY", "ANTHROPIC_API_KEY")

def load_config():
    cfg, files, from_env = {}, [], []
    for d in (HERE, os.path.dirname(HERE), os.path.expanduser("~/Desktop"), os.getcwd()):
        for fn in ("config.py", ".env"):
            p = os.path.join(d, fn)
            if not os.path.exists(p) or p in files:
                continue
            try:
                s = open(p, encoding="utf-8").read()
            except Exception:
                continue
            files.append(p)
            for k, v in re.findall(r'^\s*([A-Z_]+)\s*=\s*["\']([^"\']*)["\']', s, re.M):
                cfg.setdefault(k, v.strip())
    for k in KEYS:                      # 환경변수 우선
        v = os.environ.get(k)
        if v:
            cfg[k] = v.strip()
            from_env.append(k)
    cfg["_files"], cfg["_env"] = files, from_env
    return cfg

CFG = load_config()

def need(k):
    v = CFG.get(k)
    if not v:
        sys.exit(f"[설정오류] {k} 없음\n  확인한 파일: {CFG.get('_files') or '(없음)'}")
    return v

IS_REAL  = (CFG.get("KIS_ENV", "real").lower() != "vps")
KIS_HOST = ("https://openapi.koreainvestment.com:9443" if IS_REAL
            else "https://openapivts.koreainvestment.com:29443")

# ══════════════════════════════════════════════════════════════════════
# HTTP
# ══════════════════════════════════════════════════════════════════════
def http(url, method="GET", body=None, headers=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    h = {"content-type": "application/json; charset=utf-8",
         "user-agent": "crypto-etf/1.0"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

# ══════════════════════════════════════════════════════════════════════
# 토큰 — 24시간 유효 · 1분 1회 발급 제한 → 파일 캐시 필수
# ══════════════════════════════════════════════════════════════════════
_tok_lock = threading.Lock()

def token():
    p = os.path.join(CACHE, "kis_token.json")
    with _tok_lock:
        if os.path.exists(p):
            try:
                d = json.load(open(p))
                if d.get("expire", 0) > time.time() + 600:
                    return d["token"]
            except Exception:
                pass
        r = http(f"{KIS_HOST}/oauth2/tokenP", "POST", {
            "grant_type": "client_credentials",
            "appkey":     need("KIS_APP_KEY"),
            "appsecret":  need("KIS_APP_SECRET")})
        if "access_token" not in r:
            raise RuntimeError(f"토큰 발급 실패: {r}")
        d = {"token": r["access_token"],
             "expire": time.time() + int(r.get("expires_in", 86400))}
        json.dump(d, open(p, "w"))
        print(f"  [KIS] 새 토큰 발급 (유효 {int(r.get('expires_in', 86400)) / 3600:.0f}시간)")
        return d["token"]

# ══════════════════════════════════════════════════════════════════════
# 레이트리미터 — 공식 제한 초당 20건, 여유를 두고 16건
# ══════════════════════════════════════════════════════════════════════
class _Rate:
    def __init__(self, per_sec=16):
        self.gap  = 1.0 / per_sec
        self.lock = threading.Lock()
        self.last = 0.0
    def wait(self):
        with self.lock:
            now = time.time()
            nxt = max(now, self.last + self.gap)
            self.last = nxt
        d = nxt - now
        if d > 0:
            time.sleep(d)

# 초당 16건은 규정상 통과하지만, 수십 건을 연속으로 던지면 한투가
# 연결을 끊어버린다(2026-08-25 Errno 54 다발). 6건/초로 낮춘다.
RATE = _Rate(6)

def get(path, tr_id, params, retry=3):
    h = {"authorization": f"Bearer {token()}",
         "appkey":    need("KIS_APP_KEY"),
         "appsecret": need("KIS_APP_SECRET"),
         "tr_id":     tr_id,
         "custtype":  "P"}
    url = f"{KIS_HOST}{path}?{urllib.parse.urlencode(params)}"
    last_err = None
    for i in range(retry + 1):
        RATE.wait()
        try:
            return http(url, headers=h)
        except Exception as e:
            last_err = e
            msg = str(e)
            # 500 은 한투 서버 내부 오류다. 몇 번을 더 던져도 같은 답이 온다.
            # 22종목 × 재시도만큼 헛발질하며 시간만 버리므로 즉시 포기한다.
            if "HTTP Error 500" in msg or "HTTP Error 503" in msg:
                raise
            # 연결이 끊긴 경우는 서버가 "잠깐 쉬라"고 말하는 것이다.
            # 0.6초 뒤 재시도하면 같은 벽에 다시 부딪힌다.
            reset = ("reset by peer" in msg or "Errno 54" in msg
                     or "Connection aborted" in msg or "Errno 8" in msg)
            time.sleep((2.5 * (i + 1)) if reset else (0.6 * (i + 1)))
    raise last_err

# ══════════════════════════════════════════════════════════════════════
# 해외주식 조회 3종 — 2026-08-25 실측 확인
# ══════════════════════════════════════════════════════════════════════
def ov_price(symbol, excd):
    """현재가. excd: NAS(나스닥) / AMS(아멕스·Cboe) / NYS(뉴욕)"""
    r = get("/uapi/overseas-price/v1/quotations/price", "HHDFS00000300",
            {"AUTH": "", "EXCD": excd, "SYMB": symbol})
    return r.get("output") or {}

def ov_daily(symbol, excd):
    """기간별시세 — 1회 호출에 약 100일치 OHLC 가 온다."""
    r = get("/uapi/overseas-price/v1/quotations/dailyprice", "HHDFS76240000",
            {"AUTH": "", "EXCD": excd, "SYMB": symbol,
             "GUBN": "0", "BYMD": "", "MODP": "1"})
    return r.get("output2") or []

# 상품기본정보의 PRDT_TYPE_CD 는 거래소마다 다르다.
# 512 로 고정하면 나스닥 종목만 상장주식수가 오고 나머지는 0 이 온다(2026-08-25 실측).
# 확실한 문서를 못 찾았으므로 후보를 순서대로 시도하고, 성공한 코드를 캐시한다.
# 2026-08-25 실측 확정: NAS=512, AMS=529.  NYS 는 미확인(추적 종목에 없음).
PRDT_TYPE_BY_EXCD = {"NAS": "512", "NYS": "513", "AMS": "529"}
# 매핑이 빗나갈 때만 쓰는 예비. 길게 두면 호출이 폭증해 연결이 끊긴다.
PRDT_TYPE_CANDIDATES = ["512", "529"]
_PT_CACHE = os.path.join(CACHE, "prdt_type.json")

def _pt_load():
    try:
        return json.load(open(_PT_CACHE))
    except Exception:
        return {}

def _pt_save(d):
    try:
        json.dump(d, open(_PT_CACHE, "w"))
    except Exception:
        pass

def ov_info(symbol, excd=None):
    """상품기본정보 — lstg_stck_num(상장주식수), std_pdno(ISIN) 가 여기 있다.

    거래소별 PRDT_TYPE_CD 를 찾아가며 상장주식수가 실제로 담긴 응답을 고른다."""
    cache = _pt_load()
    order = []
    if cache.get(symbol):
        order.append(cache[symbol])
    if excd and PRDT_TYPE_BY_EXCD.get(excd):
        order.append(PRDT_TYPE_BY_EXCD[excd])
    order += PRDT_TYPE_CANDIDATES
    seen, tried = set(), []
    best = {}
    for code in order:
        if code in seen:
            continue
        seen.add(code); tried.append(code)
        try:
            r = get("/uapi/overseas-price/v1/quotations/search-info", "CTPF1702R",
                    {"PRDT_TYPE_CD": code, "PDNO": symbol})
        except Exception:
            continue
        o = r.get("output") or {}
        if not best and o:
            best = o
        if f(o.get("lstg_stck_num")) > 0:
            if cache.get(symbol) != code:
                cache[symbol] = code
                _pt_save(cache)
            o["_prdt_type_cd"] = code
            return o
    best["_prdt_type_tried"] = ",".join(tried)
    return best

def f(v, default=0.0):
    """한투 응답은 전부 문자열이고 빈 값이 섞여 온다."""
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return default

if __name__ == "__main__":
    print(f"설정 파일 : {CFG.get('_files')}")
    print(f"환경변수  : {CFG.get('_env') or '(없음)'}")
    print(f"KIS 환경  : {'실전투자' if IS_REAL else '모의투자'}  {KIS_HOST}")
    o = ov_price("IBIT", "NAS")
    print(f"IBIT 현재가: {o.get('last')}  → 연결 정상" if o.get("last") else f"응답 이상: {o}")
