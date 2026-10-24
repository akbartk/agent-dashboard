CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, user_id TEXT, model TEXT, title TEXT,
  parent_session_id TEXT, started_at REAL NOT NULL, ended_at REAL, end_reason TEXT);
INSERT INTO sessions VALUES ('KANARI-SID-E', 'cli', 'KANARI-user', 'KANARI-model', 'KANARI-judul', NULL, 1792812000.0, 1792813470.0, 'KANARI-alasan');
INSERT INTO sessions VALUES ('KANARI-SUB-E', 'subagent', 'KANARI-user', 'KANARI-model', 'KANARI-judul', 'KANARI-SID-E', 1792812060.0, 1792812120.0, 'KANARI-alasan');
