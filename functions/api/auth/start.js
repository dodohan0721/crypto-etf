import { makeState, setupError, origin, json } from "../../_lib.js";

// /api/auth/start?p=kakao|naver  → 해당 사업자 로그인 화면으로 보낸다.
export async function onRequestGet({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const p = new URL(request.url).searchParams.get("p");
  const back = origin(request);
  const state = await makeState(env.AUTH_SECRET, p);

  let url;
  if (p === "kakao") {
    if (!env.KAKAO_REST_KEY) return json({ error: "no_kakao" }, 500);
    url = "https://kauth.kakao.com/oauth/authorize?" + new URLSearchParams({
      client_id: env.KAKAO_REST_KEY,
      redirect_uri: `${back}/api/auth/kakao`,
      response_type: "code",
      state,
      scope: "profile_nickname,profile_image",
    });
  } else if (p === "naver") {
    if (!env.NAVER_LOGIN_ID) return json({ error: "no_naver" }, 500);
    url = "https://nid.naver.com/oauth2.0/authorize?" + new URLSearchParams({
      client_id: env.NAVER_LOGIN_ID,
      redirect_uri: `${back}/api/auth/naver`,
      response_type: "code",
      state,
    });
  } else {
    return json({ error: "bad_provider" }, 400);
  }
  return Response.redirect(url, 302);
}
