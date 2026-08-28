import { me, json, setupError } from "../../_lib.js";

// POST /api/admin/claim { code }
// 첫 관리자를 정하는 자리. 설정 스크립트가 만든 한 번짜리 암호를 아는 사람만 관리자가 된다.
// "먼저 가입한 사람이 관리자" 로 하면 남이 먼저 들어왔을 때 사이트를 통째로 내준다.
export async function onRequestPost({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const u = await me(request, env);
  if (!u) return json({ error: "login_required" }, 401);
  if (!env.ADMIN_CLAIM_CODE || env.ADMIN_CLAIM_CODE.length < 12)
    return json({ error: "disabled", msg: "관리자 등록 암호가 설정되지 않았습니다." }, 400);

  let b = {};
  try { b = await request.json(); } catch (e) {}
  const given = String(b.code || "");
  const want = env.ADMIN_CLAIM_CODE;
  // 시간차 없는 비교
  if (given.length !== want.length) return json({ error: "wrong_code" }, 403);
  let d = 0;
  for (let i = 0; i < want.length; i++) d |= given.charCodeAt(i) ^ want.charCodeAt(i);
  if (d !== 0) return json({ error: "wrong_code" }, 403);

  await env.DB.prepare("UPDATE users SET role = 'admin' WHERE id = ?").bind(u.id).run();
  return json({ ok: true, id: u.id, nick: u.nick });
}
