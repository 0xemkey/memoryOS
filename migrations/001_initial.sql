PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS conversations (
  conversation_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  remote_id TEXT,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  source_file TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  summary TEXT,
  content_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS messages (
  message_id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  ordinal INTEGER NOT NULL,
  content_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  path TEXT,
  provider TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  content_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
  chunk_id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  conversation_title TEXT NOT NULL,
  message_ids_json TEXT NOT NULL,
  roles_json TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  source_path TEXT,
  source_type TEXT NOT NULL,
  content_hash TEXT NOT NULL UNIQUE,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  embedding_json TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  content,
  conversation_title,
  provider,
  content='chunks',
  content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, content, conversation_title, provider)
  VALUES (new.rowid, new.content, new.conversation_title, new.provider);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, content, conversation_title, provider)
  VALUES ('delete', old.rowid, old.content, old.conversation_title, old.provider);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, content, conversation_title, provider)
  VALUES ('delete', old.rowid, old.content, old.conversation_title, old.provider);
  INSERT INTO chunks_fts(rowid, content, conversation_title, provider)
  VALUES (new.rowid, new.content, new.conversation_title, new.provider);
END;

CREATE TABLE IF NOT EXISTS import_jobs (
  job_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  source_path TEXT NOT NULL,
  status TEXT NOT NULL,
  imported INTEGER NOT NULL DEFAULT 0,
  skipped INTEGER NOT NULL DEFAULT 0,
  duplicated INTEGER NOT NULL DEFAULT 0,
  failed INTEGER NOT NULL DEFAULT 0,
  errors_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS user_settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS retrieval_events (
  event_id TEXT PRIMARY KEY,
  query TEXT NOT NULL,
  filters_json TEXT NOT NULL DEFAULT '{}',
  result_ids_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL
);
