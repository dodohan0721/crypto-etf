import { me, json, setupError, TARGET } from "../_lib.js";

// POST /api/vote { n, v }   v = 1(호재) | -1(악재)
//
// 한 사람이 한 기사에 하나만 든다.
//   · 같은 걸 다시 누르면 취소
//   · 반대를 누르면 갈아탄다
export async function onRequestPost({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const u = await me(request, env);
  if (!u) return json({ error: "login_required" }, 401);
  if (u.blocked) return json({ error: "blocked" }, 403);

  let b = {};
  try { b = await request.json(); } catch (e) {}
  const nid = String(b.n || "").trim();
  const v = Number(b.v);
  if (!TARGET.test(nid)) return json({ error: "bad_news_id" }, 400);
  if (v !== 1 && v !== -1) return json({ error: "bad_vote" }, 400);

  const cur = await env.DB.prepare(
    "SELECT v FROM votes WHERE news_id = ? AND user_id = ?").bind(nid, u.id).first();

  let mine = v;
  if (cur && cur.v === v) {
    await env.DB.prepare("DELETE FROM votes WHERE news_id = ? AND user_id = ?")
      .bind(nid, u.id).run();
    mine = 0;
  } else {
    await env.DB.prepare(
      `INSERT INTO votes (news_id, user_id, v, created) VALUES (?, ?, ?, ?)
       ON CONFLICT(news_id, user_id) DO UPDATE SET v = excluded.v, created = excluded.created`
    ).bind(nid, u.id, v, Date.now()).run();
  }

  const c = await env.DB.prepare(
    `SELECT SUM(v = 1) AS up, SUM(v = -1) AS down FROM votes WHERE news_id = ?`
  ).bind(nid).first();

  return json({ ok: true, mine, up: (c && c.up) || 0, down: (c && c.down) || 0 });
}
