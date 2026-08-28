import { me, json, setupError } from "../_lib.js";

// GET /api/counts  — 최근 활동이 있는 기사의 댓글 수·호재/악재 수를 통째로.
//
// 처음엔 보이는 기사 id 를 전부 붙여 물었는데, D1 은 한 질의에 넘길 수 있는
// 값이 100개까지다. 300개를 붙이니 500 이 났다(2026-08-27 실측).
// 뒤집어서, 활동이 있는 기사만 돌려준다 — 그쪽이 훨씬 적고 값도 안 묶는다.
const WINDOW = 45 * 86400000;      // 45일치. 피드가 3일치니 넉넉하다.
const CAP = 3000;

export async function onRequestGet({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const since = Date.now() - WINDOW;

  const [c, v] = await env.DB.batch([
    env.DB.prepare(`SELECT news_id, COUNT(*) AS n FROM comments
                     WHERE deleted = 0 AND created > ?
                     GROUP BY news_id LIMIT ?`).bind(since, CAP),
    env.DB.prepare(`SELECT news_id, SUM(v = 1) AS up, SUM(v = -1) AS down FROM votes
                     WHERE created > ?
                     GROUP BY news_id LIMIT ?`).bind(since, CAP),
  ]);

  const comments = {}, up = {}, down = {};
  for (const r of c.results || []) comments[r.news_id] = r.n;
  for (const r of v.results || []) { up[r.news_id] = r.up || 0; down[r.news_id] = r.down || 0; }

  const mine = {};
  const u = await me(request, env);
  if (u) {
    const { results } = await env.DB.prepare(
      "SELECT news_id, v FROM votes WHERE user_id = ? AND created > ? LIMIT ?"
    ).bind(u.id, since, CAP).all();
    for (const r of results || []) mine[r.news_id] = r.v;
  }
  return json({ comments, up, down, mine });
}
