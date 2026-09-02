// GET /api/up?path=<업비트 경로>&<나머지 파라미터>  — 업비트 공개 시세 중계.
//
// 브라우저가 api.upbit.com 을 직접 부르면 응답에 CORS 헤더가 붙었다 안 붙었다 한다.
// 2026-09-02 실측: 같은 URL 을 12번 불러 2번만 성공, mode:"no-cors" 로는 8/8 성공 —
// 요청은 멀쩡히 닿는데 Access-Control-Allow-Origin 이 빠진 응답이 절반쯤 돌아온다.
// 서버가 대신 불러 주면 브라우저 입장에서는 같은 출처라 이 문제가 아예 사라지고,
// 엣지 캐시가 붙어 업비트를 두드리는 횟수도 방문자 수와 무관해진다.
//
// 열어 준 경로만 통과시킨다 — 공개 시세 조회 세 개다.
// 열어 두면 남의 서버를 우리 도메인으로 프록시하는 통로가 된다.
const TTL = {
  "ticker": 15,                 // 시세 — 15초면 화면 갱신 주기(60초)보다 촘촘하다
  "market/all": 3600,           // 상장 목록 — 하루에 한두 번 바뀐다
  "candles/minutes/60": 60,     // 60분봉 — 한 시간에 한 번만 바뀐다
};

const head = (ttl) => ({
  "content-type": "application/json; charset=utf-8",
  "cache-control": `public, max-age=${ttl}`,
});

export async function onRequestGet({ request }) {
  const u = new URL(request.url);
  const path = u.searchParams.get("path") || "";
  const ttl = TTL[path];
  if (!ttl) return new Response(JSON.stringify({ error: "허용되지 않은 경로" }),
                                { status: 400, headers: head(0) });

  const qs = new URLSearchParams(u.search);
  qs.delete("path");
  const target = `https://api.upbit.com/v1/${path}` + (qs.toString() ? `?${qs}` : "");

  try {
    const r = await fetch(target, {
      headers: { accept: "application/json", "user-agent": "crypto-etf/1.0" },
      cf: { cacheTtl: ttl, cacheEverything: true },
    });
    // 업비트가 429 를 주면 그 상태 그대로 넘긴다 — 화면이 "제한 걸림"을 알아야 한다.
    return new Response(await r.text(), { status: r.status, headers: head(r.ok ? ttl : 0) });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e).slice(0, 120) }),
                        { status: 502, headers: head(0) });
  }
}
