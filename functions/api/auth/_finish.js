import { origin } from "../../_lib.js";

// 로그인 창은 새 탭이 아니라 같은 창에서 돈다. 끝나면 원래 화면으로 되돌린다.
export function ok(request, cookieHeader) {
  return new Response(null, {
    status: 302,
    headers: { Location: `${origin(request)}/?login=1`, "Set-Cookie": cookieHeader },
  });
}

// 실패해도 JSON 을 던지지 않는다. 사람이 보는 화면으로 돌려보내고 이유를 띄운다.
export function fail(request, msg) {
  return new Response(null, {
    status: 302,
    headers: { Location: `${origin(request)}/?login_error=${encodeURIComponent(msg)}` },
  });
}
