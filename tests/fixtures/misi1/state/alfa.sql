CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, user_id TEXT, model TEXT, title TEXT,
  parent_session_id TEXT, started_at REAL NOT NULL, ended_at REAL, end_reason TEXT);
INSERT INTO sessions VALUES ('KANARI-SID-C', 'cli', 'KANARI-user', 'KANARI-model', 'KANARI-judul', NULL, 1792811460.0, 1792813260.0, 'KANARI-alasan');
