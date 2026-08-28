import { checkState, issue, setupError, setCookie, upsertUser } from "../../_lib.js";
import { fail, ok } from "./_finish.js";

// 네이버가 되돌려 보내는 자리.
export async function onRequestGet({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const q = new URL(request.url).searchParams;
  const code = q.get("code"), state = q.get("state");
  if (!code) return fail(request, q.get("error_description") || "네이버 로그인이 취소되었습니다.");
  if (!(await checkState(env.AUTH_SECRET, "naver", state)))
    return fail(request, "로그인 요청이 만료되었습니다. 다시 시도해 주세요.");

  const tu = "https://nid.naver.com/oauth2.0/token?" + new URLSearchParams({
    grant_type: "authorization_code",
    client_id: env.NAVER_LOGIN_ID,
    client_secret: env.NAVER_LOGIN_SECRET || "",
    code, state,
  });
  const tr = await fetch(tu);
  const t = await tr.json();
  if (!tr.ok || !t.access_token)
    return fail(request, `네이버 토큰 발급 실패 (${t.error_description || tr.status})`);

  const ur = await fetch("https://openapi.naver.com/v1/nid/me", {
    headers: { Authorization: `Bearer ${t.access_token}` },
  });
  const u = await ur.json();
  const r = u && u.response;
  if (!ur.ok || !r || !r.id) return fail(request, `네이버 사용자 조회 실패 (${ur.status})`);

  // 닉네임 동의를 안 받았을 수 있다. 그때는 이름, 그것도 없으면 아이디 뒷자리로 만든다.
  const nick = (r.nickname || r.name || "").trim() || `네이버${String(r.id).slice(-4)}`;
  const user = await upsertUser(env, `naver:${r.id}`, nick, r.profile_image || null);

  return ok(request, setCookie(await issue(env.AUTH_SECRET, user.id)));
}
