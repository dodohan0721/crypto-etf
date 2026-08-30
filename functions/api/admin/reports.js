import { me, json, setupError } from "../../_lib.js";

// GET /api/admin/reports  — 신고가 쌓인 글을 많은 순으로.
export async function onRequestGet({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const u = await me(request, env);
  if (!u) return json({ error: "login_required" }, 401);
  if (u.role !== "admin") return json({ error: "forbidden" }, 403);

  const posts = await env.DB.prepare(
    `SELECT p.id, p.title, p.body, p.created, p.deleted, p.del_by,
            p.user_id, us.nick, us.blocked,
            COUNT(r.id) AS reports,
            GROUP_CONCAT(DISTINCT r.reason) AS reasons
       FROM post_reports r
       JOIN posts p  ON p.id = r.post_id
       JOIN users us ON us.id = p.user_id
      WHERE r.done = 0
      GROUP BY p.id
      ORDER BY reports DESC, p.created DESC
      LIMIT 50`).all();

  const { results } = await env.DB.prepare(
    `SELECT c.id, c.body, c.created, c.deleted, c.del_by, c.news_title, c.news_url,
            c.user_id, us.nick, us.blocked,
            COUNT(r.id) AS reports,
            GROUP_CONCAT(DISTINCT r.reason) AS reasons
       FROM reports r
       JOIN comments c ON c.id = r.comment_id
       JOIN users   us ON us.id = c.user_id
      WHERE r.done = 0
      GROUP BY c.id
      ORDER BY reports DESC, c.created DESC
      LIMIT 100`).all();

  return json({ items: results || [], posts: posts.results || [] });
}
