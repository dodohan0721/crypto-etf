import { me, json, setupError } from "../_lib.js";

// POST /api/like { n }  — 눌렀으면 취소, 안 눌렀으면 추가.
export async function onRequestPost({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const u = await me(request, env);
  if (!u) return json({ error: "login_required" }, 401);
  if (u.blocked) return json({ error: "blocked" }, 403);

  let b = {};
  try { b = await request.json(); } catch (e) {}
  const nid = String(b.n || "").trim();
  if (!/^[0-9a-f]{6,40}$/.test(nid)) return json({ error: "bad_news_id" }, 400);

  const had = await env.DB.prepare(
    "SELECT 1 AS x FROM likes WHERE news_id = ? AND user_id = ?").bind(nid, u.id).first();
  if (had) {
    await env.DB.prepare("DELETE FROM likes WHERE news_id = ? AND user_id = ?")
      .bind(nid, u.id).run();
  } else {
    await env.DB.prepare("INSERT INTO likes (news_id, user_id, created) VALUES (?, ?, ?)")
      .bind(nid, u.id, Date.now()).run();
  }
  const c = await env.DB.prepare("SELECT COUNT(*) AS n FROM likes WHERE news_id = ?")
    .bind(nid).first();
  return json({ ok: true, on: !had, n: (c && c.n) || 0 });
}
