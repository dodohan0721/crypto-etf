-- 커뮤니티 저장소 (Cloudflare D1 · SQLite)
--
-- KV 로도 되지만 "이 기사 댓글을 시간순으로", "신고 많은 순으로" 같은 걸 하려면
-- 목록과 정렬이 필요하다. 그건 SQL 이 할 일이다.

CREATE TABLE IF NOT EXISTS users (
  id             TEXT PRIMARY KEY,          -- 'kakao:123456' / 'naver:abcdef'
  nick           TEXT NOT NULL,
  avatar         TEXT,
  role           TEXT,                      -- 'admin' 또는 없음
  blocked        INTEGER NOT NULL DEFAULT 0,
  blocked_reason TEXT,
  created        INTEGER NOT NULL,
  seen           INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  news_id    TEXT NOT NULL,                 -- news.json 의 기사 id (제목 해시)
  news_title TEXT,                          -- 기사가 피드에서 밀려나도 관리자가 알아볼 수 있게
  news_url   TEXT,
  user_id    TEXT NOT NULL REFERENCES users(id),
  body       TEXT NOT NULL,
  created    INTEGER NOT NULL,
  deleted    INTEGER NOT NULL DEFAULT 0,    -- 지워도 행은 남긴다. 되살리려면 필요하다.
  del_by     TEXT                           -- 'self' | 'admin' | 'reported'
);
CREATE INDEX IF NOT EXISTS ix_comments_news ON comments(news_id, deleted, created);
CREATE INDEX IF NOT EXISTS ix_comments_user ON comments(user_id, created);

-- 호재 / 악재
--
-- 첫날엔 '좋아요' 하나였는데, 코인니스에서 사람들이 실제로 누르는 건
-- 한 방향 좋아요가 아니라 호재/악재 두 방향이다(실측 화면: 📈196 vs 📉43).
-- 한 사람이 한 기사에 하나만 — 다시 누르면 취소, 반대를 누르면 갈아탄다.
--
-- 첫날의 likes 표는 쓰지 않는다(운영 데이터 0건이었다). 지우려면:
--   npx wrangler d1 execute crypto-etf --remote --command "DROP TABLE IF EXISTS likes"
CREATE TABLE IF NOT EXISTS votes (
  news_id TEXT NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id),
  v       INTEGER NOT NULL,               -- 1 = 호재, -1 = 악재
  created INTEGER NOT NULL,
  PRIMARY KEY (news_id, user_id)
);
CREATE INDEX IF NOT EXISTS ix_votes_news ON votes(news_id, v);

CREATE TABLE IF NOT EXISTS reports (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  comment_id INTEGER NOT NULL REFERENCES comments(id),
  user_id    TEXT NOT NULL REFERENCES users(id),
  reason     TEXT,
  created    INTEGER NOT NULL,
  done       INTEGER NOT NULL DEFAULT 0,
  UNIQUE (comment_id, user_id)              -- 한 사람이 같은 글을 여러 번 신고해도 한 건
);
CREATE INDEX IF NOT EXISTS ix_reports_open ON reports(done, comment_id);
