import { me, json, setupError } from "../../_lib.js";

// POST /api/admin/act { what: "delete"|"restore"|"block"|"unblock"|"done", id?, user?, reason? }
export async function onRequestPost({ request, env }) {
  const bad = setupError(env); if (bad) return bad;
  const u = await me(request, env);
  if (!u) return json({ error: "login_required" }, 401);
  if (u.role !== "admin") return json({ error: "forbidden" }, 403);

  let b = {};
  try { b = await request.json(); } catch (e) {}
  const id = Number(b.id) || null;
  const target = String(b.user || "").trim() || null;

  switch (b.what) {
    case "delete":
      if (!id) return json({ error: "bad_id" }, 400);
      await env.DB.prepare("UPDATE comments SET deleted = 1, del_by = 'admin' WHERE id = ?")
        .bind(id).run();
      break;
    case "restore":
      if (!id) return json({ error: "bad_id" }, 400);
      await env.DB.batch([
        env.DB.prepare("UPDATE comments SET deleted = 0, del_by = NULL WHERE id = ?").bind(id),
        env.DB.prepare("UPDATE reports SET done = 1 WHERE comment_id = ?").bind(id),
      ]);
      break;
    case "done":
      if (!id) return json({ error: "bad_id" }, 400);
      await env.DB.prepare("UPDATE reports SET done = 1 WHERE comment_id = ?").bind(id).run();
      break;
    case "block":
      if (!target) return json({ error: "bad_user" }, 400);
      if (target === u.id) return json({ error: "self", msg: "자기 자신은 막을 수 없습니다." }, 400);
      await env.DB.prepare("UPDATE users SET blocked = 1, blocked_reason = ? WHERE id = ?")
        .bind(String(b.reason || "").slice(0, 100) || null, target).run();
      break;
    case "unblock":
      if (!target) return json({ error: "bad_user" }, 400);
      await env.DB.prepare("UPDATE users SET blocked = 0, blocked_reason = NULL WHERE id = ?")
        .bind(target).run();
      break;
    default:
      return json({ error: "bad_what" }, 400);
  }
  return json({ ok: true });
}
