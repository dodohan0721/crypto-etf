import { checkState, issue, setupError, setCookie, upsertUser, origin } from "../../_lib.js";
import { fail, ok } from "./_finish.js";

// 카카오가 되돌려 보내는 자리.
export async function onRequestGet({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const q = new URL(request.url).searchParams;
  const code = q.get("code");
  if (!code) return fail(request, q.get("error_description") || "카카오 로그인이 취소되었습니다.");
  if (!(await checkState(env.AUTH_SECRET, "kakao", q.get("state"))))
    return fail(request, "로그인 요청이 만료되었습니다. 다시 시도해 주세요.");

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: env.KAKAO_REST_KEY,
    redirect_uri: `${origin(request)}/api/auth/kakao`,
    code,
  });
  if (env.KAKAO_CLIENT_SECRET) body.set("client_secret", env.KAKAO_CLIENT_SECRET);

  const tr = await fetch("https://kauth.kakao.com/oauth/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded;charset=utf-8" },
    body,
  });
  const t = await tr.json();
  if (!tr.ok || !t.access_token)
    return fail(request, `카카오 토큰 발급 실패 (${t.error_description || tr.status})`);

  const ur = await fetch("https://kapi.kakao.com/v2/user/me", {
    headers: { Authorization: `Bearer ${t.access_token}` },
  });
  const u = await ur.json();
  if (!ur.ok || !u.id) return fail(request, `카카오 사용자 조회 실패 (${ur.status})`);

  const prof = (u.kakao_account && u.kakao_account.profile) || u.properties || {};
  const nick = (prof.nickname || "").trim() || `카카오${String(u.id).slice(-4)}`;
  const user = await upsertUser(env, `kakao:${u.id}`, nick,
    prof.profile_image_url || prof.thumbnail_image_url || null);

  return ok(request, setCookie(await issue(env.AUTH_SECRET, user.id)));
}
