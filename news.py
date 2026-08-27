# -*- coding: utf-8 -*-
"""속보·뉴스 수집.

  RSS + 거래소 공지 + 네이버 뉴스 검색 API 를 모아
  제목·출처·발행시각·원문링크만 남기고 중복을 제거한다.
  결과는 .cache/news/YYYYMMDD.json 에 날짜별로 쌓고, 최근분을 web/news.json 으로 낸다.

  본문은 저장하지 않는다. 이유는 sources.py 머리말 참조.
"""
import os, re, json, html, time, hashlib, difflib, datetime, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from kis import CFG
import sources as S

HERE  = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache", "news")
WEB   = os.path.join(HERE, "web", "news.json")
os.makedirs(CACHE, exist_ok=True)
os.makedirs(os.path.dirname(WEB), exist_ok=True)

KST = datetime.timezone(datetime.timedelta(hours=9))
UA  = {"user-agent": "Mozilla/5.0 (compatible; crypto-etf/1.0)"}


class _R308(urllib.request.HTTPRedirectHandler):
    """파이썬 urllib 은 308(Permanent Redirect)을 따라가지 않는다.
    CoinDesk 가 308 로 응답해 수집이 통째로 실패했다(2026-08-26)."""
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_301(req, fp, 301, msg, headers)

_OPENER = urllib.request.build_opener(_R308)


def fetch(url, headers=None, timeout=15):
    h = dict(UA); h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    with _OPENER.open(req, timeout=timeout) as r:
        return r.read()


def clean(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)          # 태그 제거
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_date(s):
    """RSS 날짜는 형식이 제각각이라 되는 대로 훑는다."""
    if not s:
        return None
    s = s.strip()
    fmts = ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]
    for f in fmts:
        try:
            d = datetime.datetime.strptime(s, f)
            if d.tzinfo is None:
                d = d.replace(tzinfo=datetime.timezone.utc)
            return d.astimezone(KST)
        except ValueError:
            pass
    return None


# ══════════════════════════════════════════════════════════════════════
# 분류
# ══════════════════════════════════════════════════════════════════════
def importance(title):
    t = title.lower()
    if any(re.search(p, title) for p in getattr(S, "KEY3_RE", [])):
        return 3
    if any(k.lower() in t for k in S.KEY3):
        return 3
    if any(k.lower() in t for k in S.KEY2):
        return 2
    # 거시 뉴스는 제목이 밋밋해도 시세를 움직인다
    if any(k.lower() in t for k in S.ECON):
        return 2
    return 1


def category(title, default="coin"):
    t = title.lower()
    hit_econ = sum(1 for k in S.ECON if k.lower() in t)
    hit_coin = sum(1 for k in ("코인", "비트코인", "이더리움", "가상자산", "암호화폐",
                               "crypto", "bitcoin", "ethereum", "token")
                   if k in t)
    if hit_econ and hit_econ >= hit_coin:
        return "econ"
    return default


def coin_tags(title):
    t = title.lower()
    out = []
    for sym, words in S.COINS.items():
        if any(w in t for w in words):
            out.append(sym)
    return out


def make_id(title, url):
    key = re.sub(r"[^0-9a-z가-힣]", "", clean(title).lower())[:60] or url
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def item(title, url, source_id, source_name, dt, cat, summary=""):
    title = clean(title)
    if not title or not url:
        return None
    dt = dt or datetime.datetime.now(KST)
    return {
        "id": make_id(title, url),
        "title": title,
        "url": url,
        "source": source_name,
        "source_id": source_id,
        "at": dt.strftime("%Y%m%d%H%M"),
        "cat": category(title, cat),
        "importance": importance(title),
        "coins": coin_tags(title),
        # 노출 여부는 sources.SHOW_SUMMARY 가 결정한다. 기본은 저장하지 않음.
        "summary": clean(summary)[:180] if S.SHOW_SUMMARY else None,
    }


# ══════════════════════════════════════════════════════════════════════
# 소스별 수집
# ══════════════════════════════════════════════════════════════════════
# XML 에 들어가면 안 되는 제어문자. 국내 매체 피드에서 종종 섞여 들어와
# 파서가 통째로 죽는다(2026-08-26 코인데스크 코리아).
_BADCHR = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")


# 이스케이프되지 않은 & — 국내 매체 피드의 링크에 흔하다.
# 이미 &amp; &lt; &#39; 같은 정상 엔티티는 건드리지 않는다.
_BARE_AMP = re.compile(rb"&(?!#?\w{1,8};)")


def _parse_xml(raw):
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        pass
    cleaned = _BADCHR.sub(b"", raw)
    try:
        return ET.fromstring(cleaned)
    except ET.ParseError:
        pass
    cleaned = _BARE_AMP.sub(b"&amp;", cleaned)
    try:
        return ET.fromstring(cleaned)
    except ET.ParseError:
        # 그래도 안 되면 마지막 온전한 </item> 까지만 잘라 살린다
        for tag in (b"</item>", b"</entry>"):
            i = cleaned.rfind(tag)
            if i > 0:
                head = cleaned[:200].decode("utf-8", "ignore")
                root_tag = "rss" if "<rss" in head else "feed"
                body = cleaned[:i + len(tag)]
                if root_tag == "rss":
                    body += b"</channel></rss>"
                else:
                    body += b"</feed>"
                try:
                    return ET.fromstring(body)
                except ET.ParseError:
                    continue
        raise


# XML 파서로는 도저히 안 되는 피드가 있다(2026-08-26 코인데스크 코리아,
# 제어문자 제거·& 이스케이프·잘라내기 3단을 모두 통과 못 함).
# 마지막 수단으로 파서를 버리고 정규식으로 <item> 을 직접 긁는다.
_ITEM_RE = re.compile(r"<(item|entry)[^>]*>(.*?)</\1>", re.S | re.I)
_CDATA_RE = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.S)

def _tag(block, *names):
    for n in names:
        m = re.search(rf"<{n}[^>]*>(.*?)</{n}>", block, re.S | re.I)
        if m:
            v = m.group(1)
            c = _CDATA_RE.search(v)
            return (c.group(1) if c else v).strip()
    return ""


def _items_by_regex(raw):
    """인코딩도 되는 대로 맞춰가며 <item> 을 긁어낸다."""
    txt = None
    m = re.search(rb'encoding=["\']([\w-]+)["\']', raw[:200])
    for enc in ([m.group(1).decode()] if m else []) + ["utf-8", "euc-kr", "cp949"]:
        try:
            txt = raw.decode(enc)
            break
        except Exception:
            continue
    if txt is None:
        txt = raw.decode("utf-8", "ignore")
    out = []
    for _tagname, b in _ITEM_RE.findall(txt):
        link = _tag(b, "link", "guid", "id")
        if not link:                       # Atom: <link href="..."/>
            m2 = re.search(r'<link[^>]*href=["\']([^"\']+)', b, re.I)
            link = m2.group(1) if m2 else ""
        out.append((_tag(b, "title"),
                    link,
                    _tag(b, "pubDate", "dc:date", "published", "updated", "date"),
                    _tag(b, "description", "summary", "content")))
    return out


# 피드 주소가 죽으면 매체는 대개 홈페이지 HTML 을 돌려준다.
# 워드프레스·대부분의 CMS 는 그 HTML 안에
#   <link rel="alternate" type="application/rss+xml" href="...">
# 로 진짜 피드 위치를 알려준다. 그걸 따라가면 주소가 바뀌어도 살아남는다.
_ALT_RE = re.compile(
    rb"""<link[^>]+type=["']application/(?:rss|atom)\+xml["'][^>]*>""", re.I)
_HREF_RE = re.compile(rb"""href=["']([^"']+)["']""", re.I)
_TITLE_RE = re.compile(rb"""title=["']([^"']*)["']""", re.I)


def _looks_html(raw):
    head = raw[:400].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def discover_feed(raw, base):
    """HTML 안에서 진짜 피드 주소를 찾는다. 댓글 피드는 거른다."""
    cands = []
    for tag in _ALT_RE.findall(raw):
        h = _HREF_RE.search(tag)
        if not h:
            continue
        href = h.group(1).decode("utf-8", "ignore")
        t = _TITLE_RE.search(tag)
        title = t.group(1).decode("utf-8", "ignore") if t else ""
        # 댓글 피드는 기사가 아니다
        if "댓글" in title or "comment" in title.lower() or "/comments/" in href:
            continue
        cands.append(urllib.parse.urljoin(base, href))
    return cands[0] if cands else None


def from_rss(sid, name, url, lang, cat):
    raw = fetch(url)
    if _looks_html(raw):
        alt = discover_feed(raw, url)
        if not alt:
            raise RuntimeError(
                f"피드가 아니라 HTML 이 왔고 대체 주소도 못 찾음 ({len(raw):,}바이트)")
        print(f"     · {name}: 피드 주소 변경 감지 → {alt}")
        raw = fetch(alt)
        if _looks_html(raw):
            raise RuntimeError(f"대체 주소도 HTML 이었음: {alt}")
    try:
        root = _parse_xml(raw)
    except Exception as e:
        rows = _items_by_regex(raw)
        if not rows:
            p = os.path.join(os.path.dirname(CACHE), f"feed_fail_{sid}.xml")
            try:
                open(p, "wb").write(raw)
            except Exception:
                pass
            head = raw[:160].decode("utf-8", "ignore").replace("\n", " ")
            n_item = raw.lower().count(b"<item")
            n_entry = raw.lower().count(b"<entry")
            raise RuntimeError(
                f"{str(e)[:40]} · {len(raw):,}바이트 · item {n_item} · entry {n_entry}"
                f" · 원문 저장 .cache/feed_fail_{sid}.xml · 시작 {head[:70]!r}")
        out = []
        for title, link, pub, desc in rows:
            it = item(title, link.strip(), sid, name, parse_date(pub), cat, desc)
            if it:
                out.append(it)
        print(f"     · {name}: XML 파싱 실패 → 정규식으로 {len(out)}건 복구")
        return out

    out = []
    nodes = root.iter("item")
    for n in nodes:
        g = lambda k: (n.findtext(k) or "")
        dt = parse_date(g("pubDate") or g("{http://purl.org/dc/elements/1.1/}date"))
        it = item(g("title"), (g("link") or "").strip(), sid, name, dt, cat, g("description"))
        if it:
            out.append(it)
    if not out:                                   # Atom 형식 폴백
        ns = "{http://www.w3.org/2005/Atom}"
        for n in root.iter(f"{ns}entry"):
            link = ""
            for l in n.findall(f"{ns}link"):
                link = l.get("href") or link
            dt = parse_date(n.findtext(f"{ns}updated") or n.findtext(f"{ns}published"))
            it = item(n.findtext(f"{ns}title"), link, sid, name, dt, cat,
                      n.findtext(f"{ns}summary"))
            if it:
                out.append(it)
    return out


def from_upbit():
    sid, name, url = S.UPBIT_NOTICE
    d = json.loads(fetch(url))
    rows = (d.get("data") or {}).get("notices") or []
    out = []
    for r in rows:
        # listed_at 은 이미 KST(+09:00)다.
        # 오프셋을 떼고 parse_date 에 넘기면 UTC 로 오해해서 9시간을 더 얹는다
        # → 오후 2시 공지가 밤 11시로 찍혔다(2026-08-27 실측). 원문 그대로 넘긴다.
        raw = (r.get("listed_at") or r.get("created_at") or "").strip()
        if re.search(r"(Z|[+-]\d{2}:?\d{2})$", raw):
            dt = parse_date(raw)                   # 오프셋이 붙어 있으면 그대로 믿는다
        else:
            # parse_date 는 오프셋 없는 값을 UTC 로 본다. 업비트는 KST 다.
            try:
                dt = datetime.datetime.fromisoformat(raw).replace(tzinfo=KST)
            except ValueError:
                dt = None
        if dt is not None:
            dt = dt.astimezone(KST)
        link = f"https://upbit.com/service_center/notice?id={r.get('id')}"
        it = item(r.get("title"), link, sid, name, dt, "coin")
        if it:
            it["importance"] = max(it["importance"], 2)   # 거래소 공지는 최소 '상'
            out.append(it)
    return out


def from_naver(query):
    cid, sec = CFG.get("NAVER_CLIENT_ID"), CFG.get("NAVER_CLIENT_SECRET")
    if not (cid and sec):
        raise RuntimeError("NAVER_CLIENT_ID/SECRET 없음")
    url = ("https://openapi.naver.com/v1/search/news.json?"
           + urllib.parse.urlencode({"query": query, "display": 30, "sort": "date"}))
    d = json.loads(fetch(url, {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}))
    out = []
    for r in d.get("items", []):
        dt = parse_date(r.get("pubDate"))
        # originallink 가 언론사 원문. 없으면 네이버 링크.
        link = (r.get("originallink") or r.get("link") or "").strip()
        it = item(r.get("title"), link, "naver", "네이버 뉴스", dt, "coin", r.get("description"))
        if it:
            out.append(it)
    return out


# ══════════════════════════════════════════════════════════════════════
def _norm_title(t):
    return re.sub(r"[^0-9a-z가-힣]", "", (t or "").lower())


def squash(rows):
    """같은 기사를 하나로 줄인다.

    id 가 같으면 당연히 같은 기사고, 매체가 제목만 몇 글자 손봐 다시 내보낸 것도 같은 기사다.
    앞 12자로 후보를 좁힌 뒤 유사도로만 묶는다 — 앞자리만 보고 묶으면 남의 기사까지 삼킨다.
    먼저 나온 기사(원본)를 남기고, 중요도만 높은 쪽으로 끌어올린다.
    """
    out, bucket = {}, {}
    for r in sorted(rows, key=lambda x: x.get("at", "")):
        cur = out.get(r["id"])
        if cur is None:
            k = _norm_title(r["title"])
            if len(k) >= 16:
                b = (r["source_id"], k[:12])
                for kid, kk in bucket.get(b, ()):
                    if difflib.SequenceMatcher(None, k, kk).ratio() >= .85:
                        cur = out[kid]
                        break
                else:
                    bucket.setdefault(b, []).append((r["id"], k))
        if cur is not None:
            cur["importance"] = max(cur["importance"], r["importance"])
            continue
        out[r["id"]] = r
    return sorted(out.values(), key=lambda x: x["at"], reverse=True)


def collect(verbose=True):
    items, errs = {}, []

    def add(rows):
        for r in rows:
            items.setdefault(r["id"], r)

    if verbose:
        print("\n[뉴스] 수집")

    for sid, name, url, lang, cat in S.RSS:
        try:
            rows = from_rss(sid, name, url, lang, cat)
            add(rows)
            if verbose:
                print(f"  {name:<18} {len(rows):>3}건")
        except Exception as e:
            errs.append(f"{name}: {str(e)[:150]}")
            if verbose:
                print(f"  {name:<18}   ! {str(e)[:150]}")

    try:
        rows = from_upbit(); add(rows)
        if verbose:
            print(f"  {'업비트 공지':<18} {len(rows):>3}건")
    except Exception as e:
        errs.append(f"업비트 공지: {str(e)[:60]}")
        if verbose:
            print(f"  {'업비트 공지':<18}   ! {str(e)[:50]}")

    nv = 0
    for q in S.NAVER_QUERIES:
        try:
            rows = from_naver(q); add(rows); nv += len(rows)
            time.sleep(0.2)
        except Exception as e:
            errs.append(f"네이버({q}): {str(e)[:60]}")
            break
    if verbose and nv:
        print(f"  {'네이버 뉴스':<18} {nv:>3}건")

    rows = squash(items.values())

    # 날짜별 캐시에 병합 — 이미 본 기사는 최초 수집 시각을 유지한다
    for r in rows:
        day = r["at"][:8]
        p = os.path.join(CACHE, f"{day}.json")
        try:
            store = json.load(open(p))
        except Exception:
            store = {}
        store.setdefault(r["id"], r)
        json.dump(store, open(p, "w"), ensure_ascii=False, separators=(",", ":"))

    if verbose:
        n3 = sum(1 for r in rows if r["importance"] == 3)
        ec = sum(1 for r in rows if r["cat"] == "econ")
        print(f"  → 중복 제거 후 {len(rows)}건  (중요 {n3} · 경제 {ec})"
              + (f"  실패 {len(errs)}건" if errs else ""))
    return rows, errs


def build_feed(days=3, limit=300, verbose=True):
    """최근 N일치를 합쳐 web/news.json 으로 낸다."""
    rows, errs = collect(verbose)
    cut = (datetime.datetime.now(KST) - datetime.timedelta(days=days)).strftime("%Y%m%d%H%M")
    merged = {}
    for fn in sorted(os.listdir(CACHE)):
        if not fn.endswith(".json"):
            continue
        try:
            for k, v in json.load(open(os.path.join(CACHE, fn))).items():
                if v.get("at", "") >= cut:
                    merged[k] = v
        except Exception:
            pass
    for r in rows:
        merged[r["id"]] = r
    out_rows = squash(merged.values())[:limit]

    out = {"ts": datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
           "items": out_rows,
           "show_summary": S.SHOW_SUMMARY,
           "errors": errs}
    json.dump(out, open(WEB, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    if verbose:
        kb = os.path.getsize(WEB) / 1024
        print(f"  → web/news.json  {len(out_rows)}건 · {kb:,.0f} KB")
    return out


if __name__ == "__main__":
    build_feed()
