import { me, pubUser, json, setupError, checkBody, tooFast } from "../_lib.js";

const PAGE = 20;

// GET /api/posts?before=<id>  — 최신순 목록. 댓글 수·호재/악재까지 한 번에.
export async function onRequestGet({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const q = new URL(request.url).searchParams;
  const before = Number(q.get("before")) || 0;
  const u = await me(request, env);

  const where = before ? "p.deleted = 0 AND p.id < ?" : "p.deleted = 0";
  const binds = before ? [before, PAGE + 1] : [PAGE + 1];

  const { results } = await env.DB.prepare(
    `SELECT p.id, p.title, p.body, p.created, p.user_id, us.nick,
            (SELECT COUNT(*) FROM comments c
              WHERE c.news_id = 'p' || p.id AND c.deleted = 0) AS comments,
            (SELECT COUNT(*) FROM votes v
              WHERE v.news_id = 'p' || p.id AND v.v = 1)  AS up,
            (SELECT COUNT(*) FROM votes v
              WHERE v.news_id = 'p' || p.id AND v.v = -1) AS down
       FROM posts p JOIN users us ON us.id = p.user_id
      WHERE ${where}
      ORDER BY p.id DESC LIMIT ?`).bind(...binds).all();

  const rows = results || [];
  const more = rows.length > PAGE;
  const items = rows.slice(0, PAGE).map(r => ({
    id: r.id, title: r.title, body: r.body, at: r.created,
    nick: r.nick, comments: r.comments, up: r.up, down: r.down,
    mine: !!(u && u.id === r.user_id),
  }));

  // 내가 어디에 표를 줬는지
  let mine = {};
  if (u && items.length) {
    const keys = items.map(x => "p" + x.id);
    const marks = keys.map(() => "?").join(",");
    const v = await env.DB.prepare(
      `SELECT news_id, v FROM votes WHERE user_id = ? AND news_id IN (${marks})`
    ).bind(u.id, ...keys).all();
    for (const r of v.results || []) mine[r.news_id] = r.v;
  }
  return json({ items, more, mine, me: pubUser(u) });
}

// POST /api/posts { title, body }
export async function onRequestPost({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const u = await me(request, env);
  if (!u) return json({ error: "login_required" }, 401);
  if (u.blocked) return json({ error: "blocked", msg: "글쓰기가 제한된 계정입니다." }, 403);

  let b = {};
  try { b = await request.json(); } catch (e) {}
  const title = String(b.title || "").trim().replace(/\s+/g, " ");
  const body = String(b.body || "").trim();
  if (title.length < 2 || title.length > 80)
    return json({ error: "rejected", msg: "제목은 2~80자로 써 주세요." }, 400);
  const why = checkBody(title) || checkBody(body);
  if (why) return json({ error: "rejected", msg: why }, 400);
  if (body.length > 2000) return json({ error: "rejected", msg: "본문은 2000자까지입니다." }, 400);

  // 댓글과 같은 제한을 쓴다. 글은 더 무거우니 30초에 하나.
  const slow = await tooFast(env, u.id);
  if (slow) return json({ error: "too_fast", msg: slow }, 429);
  const last = await env.DB.prepare(
    "SELECT MAX(created) AS t FROM posts WHERE user_id = ?").bind(u.id).first();
  if (last && last.t && Date.now() - last.t < 30000)
    return json({ error: "too_fast", msg: "글은 30초에 하나까지 쓸 수 있습니다." }, 429);

  const now = Date.now();
  const r = await env.DB.prepare(
    "INSERT INTO posts (user_id, title, body, created) VALUES (?, ?, ?, ?)"
  ).bind(u.id, title, body, now).run();

  return json({ ok: true, item: {
    id: r.meta.last_row_id, title, body, at: now,
    nick: u.nick, comments: 0, up: 0, down: 0, mine: true } });
}

// DELETE /api/posts?id=  — 내 글이거나 관리자
export async function onRequestDelete({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const u = await me(request, env);
  if (!u) return json({ error: "login_required" }, 401);

  const id = Number(new URL(request.url).searchParams.get("id"));
  if (!id) return json({ error: "bad_id" }, 400);
  const row = await env.DB.prepare("SELECT user_id FROM posts WHERE id = ?").bind(id).first();
  if (!row) return json({ error: "not_found" }, 404);
  const admin = u.role === "admin";
  if (row.user_id !== u.id && !admin) return json({ error: "forbidden" }, 403);

  await env.DB.prepare("UPDATE posts SET deleted = 1, del_by = ? WHERE id = ?")
    .bind(admin && row.user_id !== u.id ? "admin" : "self", id).run();
  return json({ ok: true });
}
