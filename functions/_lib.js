// 커뮤니티 공통 — 서명(HMAC-SHA256)으로 로그인 증표와 OAuth state 를 만든다.
// 테마보드 functions/_lib.js 의 방식을 그대로 가져왔다. 서버에 세션을 저장하지 않으므로
// Workers 처럼 상태가 없는 환경에서도 검증이 된다.
//
// 사람과 글은 D1(SQLite)에 둔다. KV 로도 되지만 목록·정렬·개수가 필요해서 SQL 이 맞다.

const enc = new TextEncoder();

async function hkey(secret) {
  return crypto.subtle.importKey("raw", enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
}

export async function mac(secret, msg) {
  return new Uint8Array(await crypto.subtle.sign("HMAC", await hkey(secret), enc.encode(msg)));
}

export function b64u(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function unb64u(s) {
  return atob(String(s).replace(/-/g, "+").replace(/_/g, "/"));
}

export function eq(a, b) {                 // 시간차 없는 비교
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

export function json(obj, status, extra) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: Object.assign(
      { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
      extra || {}),
  });
}

export function cookie(req, name) {
  const c = req.headers.get("Cookie") || "";
  for (const part of c.split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return decodeURIComponent(v.join("="));
  }
  return null;
}

// ── 로그인 증표 ───────────────────────────────────────────────────────────
export const COOKIE = "ce_s";
const DAYS = 60;

export async function issue(secret, uid) {
  const body = `${uid}|${Date.now() + DAYS * 86400000}`;
  return `${b64u(enc.encode(body))}.${b64u(await mac(secret, body))}`;
}

export async function readToken(secret, tok) {
  if (!tok || tok.indexOf(".") < 0) return null;
  const [p, s] = tok.split(".");
  let body;
  try { body = unb64u(p); } catch (e) { return null; }
  const i = body.lastIndexOf("|");
  if (i < 0) return null;
  const uid = body.slice(0, i), exp = Number(body.slice(i + 1));
  if (!exp || exp < Date.now()) return null;
  if (!eq(s, b64u(await mac(secret, body)))) return null;
  return uid;
}

export function setCookie(tok) {
  return `${COOKIE}=${tok}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${DAYS * 86400}`;
}
export const clearCookie = `${COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`;

// ── OAuth state ───────────────────────────────────────────────────────────
// 남이 만든 콜백을 우리 것인 양 들이미는 걸 막는다. 10분만 유효하다.
export async function makeState(secret, provider) {
  const body = `${provider}|${Date.now()}`;
  return `${b64u(enc.encode(body))}.${b64u(await mac(secret, body))}`;
}

export async function checkState(secret, provider, state) {
  if (!state || state.indexOf(".") < 0) return false;
  const [p, s] = state.split(".");
  let body;
  try { body = unb64u(p); } catch (e) { return false; }
  const [prov, ts] = body.split("|");
  if (prov !== provider) return false;
  if (!ts || Date.now() - Number(ts) > 10 * 60 * 1000) return false;
  return eq(s, b64u(await mac(secret, body)));
}

// ── 설정 확인 ─────────────────────────────────────────────────────────────
export function setupError(env) {
  if (!env.AUTH_SECRET || env.AUTH_SECRET.length < 16)
    return json({ error: "server_setup", msg: "AUTH_SECRET 이 없습니다." }, 500);
  if (!env.DB)
    return json({ error: "server_setup", msg: "D1 데이터베이스가 연결되지 않았습니다." }, 500);
  return null;
}

export function origin(request) {
  return new URL(request.url).origin;
}

// ── 사람 ──────────────────────────────────────────────────────────────────
export async function getUser(env, uid) {
  if (!uid) return null;
  return await env.DB.prepare(
    "SELECT id, nick, avatar, role, blocked FROM users WHERE id = ?").bind(uid).first();
}

export async function me(request, env) {
  const uid = await readToken(env.AUTH_SECRET, cookie(request, COOKIE));
  return await getUser(env, uid);
}

export async function upsertUser(env, id, nick, avatar) {
  const now = Date.now();
  await env.DB.prepare(
    `INSERT INTO users (id, nick, avatar, created, seen)
     VALUES (?, ?, ?, ?, ?)
     ON CONFLICT(id) DO UPDATE SET nick = excluded.nick,
                                   avatar = excluded.avatar,
                                   seen = excluded.seen`
  ).bind(id, nick, avatar || null, now, now).run();
  return await getUser(env, id);
}

// 댓글·투표·신고가 붙는 대상의 id.
//   속보  = 제목 해시 16자리
//   게시글 = 'p' + 글번호
export const TARGET = /^([0-9a-f]{6,40}|p[0-9]{1,12})$/;

// ── 글 검사 ───────────────────────────────────────────────────────────────
// 링크는 통째로 막는다. 코인 커뮤니티에서 링크 도배는 거의 전부 스캠이다.
const LINK = /(https?:\/\/|www\.|\b[a-z0-9-]+\.(com|net|org|io|co|kr|me|xyz|top|vip|link|site)\b)/i;
const KAKAO_OPEN = /(오픈\s*카톡|오픈채팅|open\.kakao|t\.me|텔레그램|리딩방)/i;

export function checkBody(text) {
  const t = String(text || "").trim();
  if (t.length < 2) return "너무 짧습니다.";
  if (t.length > 500) return "500자까지 쓸 수 있습니다.";
  if (LINK.test(t)) return "링크는 쓸 수 없습니다.";
  if (KAKAO_OPEN.test(t)) return "리딩방·오픈채팅 안내는 쓸 수 없습니다.";
  if (/(.)\1{15,}/.test(t)) return "같은 글자를 너무 많이 반복했습니다.";
  return null;
}

// 도배 제한 — 10초에 한 번, 1분에 3개까지.
export async function tooFast(env, uid) {
  const now = Date.now();
  const r = await env.DB.prepare(
    "SELECT COUNT(*) AS n, MAX(created) AS last FROM comments WHERE user_id = ? AND created > ?"
  ).bind(uid, now - 60000).first();
  if (r && r.last && now - r.last < 10000) return "조금 천천히 써 주세요.";
  if (r && r.n >= 3) return "1분에 3개까지 쓸 수 있습니다.";
  return null;
}

export function pubUser(u) {
  return u ? { id: u.id, nick: u.nick, avatar: u.avatar, admin: u.role === "admin" } : null;
}
