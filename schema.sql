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

CREATE TABLE IF NOT EXISTS likes (
  news_id TEXT NOT NULL,
  user_id TEXT NOT NULL REFERENCES users(id),
  created INTEGER NOT NULL,
  PRIMARY KEY (news_id, user_id)
);
CREATE INDEX IF NOT EXISTS ix_likes_news ON likes(news_id);

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
