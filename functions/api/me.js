import { me, pubUser, json, setupError } from "../_lib.js";

export async function onRequestGet({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const u = await me(request, env);
  return json({
    user: pubUser(u),
    blocked: !!(u && u.blocked),
    providers: {
      kakao: !!env.KAKAO_REST_KEY,
      naver: !!env.NAVER_LOGIN_ID,
    },
  });
}
