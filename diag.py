# -*- coding: utf-8 -*-
"""한투 API 어디까지 살아있는지 계층적으로 확인한다.

  국내주식이 되면 → 계정·토큰은 정상, 해외 엔드포인트만 문제
  국내주식도 안 되면 → 계정 권한이나 한투 전체 장애
"""
import datetime, kis

KST = datetime.timezone(datetime.timedelta(hours=9))
now = datetime.datetime.now(KST)
print("=" * 68)
print(f" 한투 API 계층 진단   {now:%Y-%m-%d %H:%M} KST  (UTC {now.astimezone(datetime.timezone.utc):%H:%M})")
print("=" * 68)

try:
    print(f"  토큰                       OK ({len(kis.token())}자)")
except Exception as e:
    print(f"  토큰                       실패 {str(e)[:60]}"); raise SystemExit

def probe(label, path, tr, params, pick=None):
    try:
        r = kis.get(path, tr, params, retry=0)
        rt, msg = r.get("rt_cd"), (r.get("msg1") or "").strip()[:34]
        o = r.get("output") or r.get("output1") or {}
        extra = ""
        if pick and isinstance(o, dict):
            extra = "  ".join(f"{k}={o.get(k)}" for k in pick if o.get(k) not in (None, ""))
        if not extra and r.get("output2"):
            extra = f"{len(r['output2'])}일"
        print(f"  {label:<26} OK   rt_cd={rt}  {extra or msg}")
        return True
    except Exception as e:
        print(f"  {label:<26} 실패 {str(e)[:44]}")
        return False

print("\n── 국내주식 (theme-board 에서 쓰던 계열) ──")
dom = probe("국내 현재가", "/uapi/domestic-stock/v1/quotations/inquire-price",
            "FHKST01010100", {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930"},
            ["stck_prpr", "hts_avls"])
probe("국내 거래량순위", "/uapi/domestic-stock/v1/quotations/volume-rank",
      "FHPST01710", {"FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20171",
                     "FID_INPUT_ISCD": "0000", "FID_DIV_CLS_CODE": "0",
                     "FID_BLNG_CLS_CODE": "3", "FID_TRGT_CLS_CODE": "111111111",
                     "FID_TRGT_EXLS_CLS_CODE": "000000", "FID_INPUT_PRICE_1": "",
                     "FID_INPUT_PRICE_2": "", "FID_VOL_CNT": "", "FID_INPUT_DATE_1": ""})

print("\n── 해외주식 ──")
probe("해외 기간시세 (살아있던 것)", "/uapi/overseas-price/v1/quotations/dailyprice",
      "HHDFS76240000", {"AUTH": "", "EXCD": "NAS", "SYMB": "IBIT",
                        "GUBN": "0", "BYMD": "", "MODP": "1"})
probe("해외 현재가  AUTH 빈값", "/uapi/overseas-price/v1/quotations/price",
      "HHDFS00000300", {"AUTH": "", "EXCD": "NAS", "SYMB": "IBIT"}, ["last", "tvol"])
probe("해외 현재가  AUTH 생략", "/uapi/overseas-price/v1/quotations/price",
      "HHDFS00000300", {"EXCD": "NAS", "SYMB": "IBIT"}, ["last"])
probe("해외 현재가  AAPL", "/uapi/overseas-price/v1/quotations/price",
      "HHDFS00000300", {"AUTH": "", "EXCD": "NAS", "SYMB": "AAPL"}, ["last"])
probe("해외 현재가상세 price-detail", "/uapi/overseas-price/v1/quotations/price-detail",
      "HHDFS76200200", {"AUTH": "", "EXCD": "NAS", "SYMB": "IBIT"},
      ["last", "tomv", "perx", "t_xprc"])
probe("해외 상품기본정보", "/uapi/overseas-price/v1/quotations/search-info",
      "CTPF1702R", {"PRDT_TYPE_CD": "512", "PDNO": "IBIT"}, ["lstg_stck_num", "std_pdno"])
probe("해외 체결추이", "/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice",
      "HHDFS76950200", {"AUTH": "", "EXCD": "NAS", "SYMB": "IBIT",
                        "NMIN": "1", "PINC": "1", "NEXT": "", "NREC": "10",
                        "FILL": "", "KEYB": ""})

print("-" * 68)
if dom:
    print(" 국내는 되고 해외만 죽음 → 계정·토큰 정상. 해외 시세 엔드포인트 장애다.")
    print(" price-detail 이 되면 그걸로 갈아타면 된다.")
else:
    print(" 국내도 안 됨 → 한투 전체 장애이거나 계정 권한 문제. 잠시 뒤 재확인.")

# ── 살아있는 dailyprice 에서 뭘 더 건질 수 있나 ──────────────────────
print("\n── 기간시세(dailyprice) 응답 필드 전수 ──")
try:
    r = kis.get("/uapi/overseas-price/v1/quotations/dailyprice", "HHDFS76240000",
                {"AUTH": "", "EXCD": "NAS", "SYMB": "IBIT",
                 "GUBN": "0", "BYMD": "", "MODP": "1"}, retry=0)
    o1 = r.get("output1") or {}
    if o1:
        print("  output1 (종목 요약):")
        for k in sorted(o1):
            if o1[k] not in ("", None):
                print(f"     {k:<12} = {o1[k]}")
    rows = r.get("output2") or []
    if rows:
        print(f"  output2 (일별, {len(rows)}건) 첫 행 전체 필드:")
        for k in sorted(rows[0]):
            print(f"     {k:<12} = {rows[0][k]}")
except Exception as e:
    print(f"  실패 {str(e)[:60]}")
print("\n  → tvol(거래량)이 있으면 거래량은 여기서 얻는다.")
print("  → 상장주식수가 없으면 발행사 공개 데이터로 보충해야 한다.")
