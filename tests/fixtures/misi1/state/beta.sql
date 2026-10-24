CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, user_id TEXT, model TEXT, title TEXT,
  parent_session_id TEXT, started_at REAL NOT NULL, ended_at REAL, end_reason TEXT);
INSERT INTO sessions VALUES ('KANARI-SID-G', 'cli', 'KANARI-user', 'KANARI-model', 'KANARI-judul', NULL, 1792742400.0, 1792743600.0, 'KANARI-alasan');
INSERT INTO sessions VALUES ('KANARI-SID-B1', 'cli', 'KANARI-user', 'KANARI-model', 'KANARI-judul', NULL, 1792811160.0, 1792814280.0, 'KANARI-alasan');
INSERT INTO sessions VALUES ('KANARI-SUB-1', 'subagent', 'KANARI-user', 'KANARI-model', 'KANARI-judul', 'KANARI-SID-B1', 1792812000.0, 1792813200.0, 'KANARI-alasan');
INSERT INTO sessions VALUES ('KANARI-KOMPRESI', 'cli', 'KANARI-user', 'KANARI-model', 'KANARI-judul', 'KANARI-SID-B1', 1792813500.0, NULL, 'KANARI-alasan');
INSERT INTO sessions VALUES ('KANARI-SID-B2', 'cli', 'KANARI-user', 'KANARI-model', 'KANARI-judul', NULL, 1792814400.0, NULL, 'KANARI-alasan');
INSERT INTO sessions VALUES ('KANARI-SUB-2', 'subagent', 'KANARI-user', 'KANARI-model', 'KANARI-judul', 'KANARI-SID-B2', 1792815000.0, NULL, 'KANARI-alasan');
INSERT INTO sessions VALUES ('KANARI-SUB-LAIN', 'subagent', 'KANARI-user', 'KANARI-model', 'KANARI-judul', 'KANARI-SID-LAIN', 1792815300.0, NULL, 'KANARI-alasan');
