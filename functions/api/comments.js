import { me, pubUser, json, setupError, checkBody, tooFast, TARGET } from "../_lib.js";

const PAGE = 50;

// GET /api/comments?n=<기사id>  — 그 기사의 댓글
export async function onRequestGet({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const q = new URL(request.url).searchParams;
  const nid = (q.get("n") || "").trim();
  if (!TARGET.test(nid)) return json({ error: "bad_news_id" }, 400);

  const u = await me(request, env);
  const { results } = await env.DB.prepare(
    `SELECT c.id, c.body, c.created, c.user_id, u.nick, u.avatar
       FROM comments c JOIN users u ON u.id = c.user_id
      WHERE c.news_id = ? AND c.deleted = 0
      ORDER BY c.created ASC LIMIT ?`).bind(nid, PAGE).all();

  return json({
    items: (results || []).map(r => ({
      id: r.id, body: r.body, at: r.created,
      nick: r.nick, avatar: r.avatar,
      mine: !!(u && u.id === r.user_id),
    })),
    me: pubUser(u),
  });
}

// POST /api/comments  { n, body, title, url }
export async function onRequestPost({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const u = await me(request, env);
  if (!u) return json({ error: "login_required" }, 401);
  if (u.blocked) return json({ error: "blocked", msg: "글쓰기가 제한된 계정입니다." }, 403);

  let b = {};
  try { b = await request.json(); } catch (e) {}
  const nid = String(b.n || "").trim();
  if (!TARGET.test(nid)) return json({ error: "bad_news_id" }, 400);

  const body = String(b.body || "").trim().replace(/\s+\n/g, "\n");
  const why = checkBody(body);
  if (why) return json({ error: "rejected", msg: why }, 400);

  const slow = await tooFast(env, u.id);
  if (slow) return json({ error: "too_fast", msg: slow }, 429);

  const now = Date.now();
  const r = await env.DB.prepare(
    `INSERT INTO comments (news_id, news_title, news_url, user_id, body, created)
     VALUES (?, ?, ?, ?, ?, ?)`
  ).bind(nid, String(b.title || "").slice(0, 300) || null,
         String(b.url || "").slice(0, 500) || null, u.id, body, now).run();

  return json({
    ok: true,
    item: { id: r.meta.last_row_id, body, at: now, nick: u.nick, avatar: u.avatar, mine: true },
  });
}

// DELETE /api/comments?id=123  — 내 글이거나 관리자
export async function onRequestDelete({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const u = await me(request, env);
  if (!u) return json({ error: "login_required" }, 401);

  const id = Number(new URL(request.url).searchParams.get("id"));
  if (!id) return json({ error: "bad_id" }, 400);

  const row = await env.DB.prepare("SELECT user_id FROM comments WHERE id = ?").bind(id).first();
  if (!row) return json({ error: "not_found" }, 404);
  const admin = u.role === "admin";
  if (row.user_id !== u.id && !admin) return json({ error: "forbidden" }, 403);

  await env.DB.prepare("UPDATE comments SET deleted = 1, del_by = ? WHERE id = ?")
    .bind(admin && row.user_id !== u.id ? "admin" : "self", id).run();
  return json({ ok: true });
}
