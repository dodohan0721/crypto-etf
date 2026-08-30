import { me, json, setupError } from "../_lib.js";

// POST /api/report { id, reason, kind }   kind: "c"(댓글, 기본) | "p"(게시글)
export async function onRequestPost({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const u = await me(request, env);
  if (!u) return json({ error: "login_required" }, 401);

  let b = {};
  try { b = await request.json(); } catch (e) {}
  const id = Number(b.id);
  if (!id) return json({ error: "bad_id" }, 400);
  const reason = String(b.reason || "").slice(0, 100);
  const post = b.kind === "p";
  const T = post ? "posts" : "comments";
  const R = post ? "post_reports" : "reports";
  const FK = post ? "post_id" : "comment_id";

  const row = await env.DB.prepare(
    `SELECT user_id FROM ${T} WHERE id = ? AND deleted = 0`).bind(id).first();
  if (!row) return json({ error: "not_found" }, 404);
  if (row.user_id === u.id) return json({ error: "self" , msg: "내 글은 신고할 수 없습니다." }, 400);

  // 같은 사람이 같은 글을 여러 번 신고해도 한 건으로 센다.
  await env.DB.prepare(
    `INSERT INTO ${R} (${FK}, user_id, reason, created) VALUES (?, ?, ?, ?)
     ON CONFLICT(${FK}, user_id) DO UPDATE SET reason = excluded.reason`
  ).bind(id, u.id, reason, Date.now()).run();

  // 서로 다른 세 사람이 신고하면 일단 가린다. 관리자가 되살릴 수 있다.
  const c = await env.DB.prepare(
    `SELECT COUNT(*) AS n FROM ${R} WHERE ${FK} = ?`).bind(id).first();
  if (c && c.n >= 3) {
    await env.DB.prepare(`UPDATE ${T} SET deleted = 1, del_by = 'reported' WHERE id = ?`)
      .bind(id).run();
  }
  return json({ ok: true, hidden: !!(c && c.n >= 3) });
}
