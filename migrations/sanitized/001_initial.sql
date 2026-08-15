PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sanitized_conversations (
  conversation_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  remote_id TEXT,
  sanitized_title TEXT NOT NULL,
  created_at TEXT,
  updated_at TEXT,
  source_file_ref TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  content_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS sanitized_messages (
  message_id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES sanitized_conversations(conversation_id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  sanitized_content TEXT NOT NULL,
  privacy_level TEXT NOT NULL,
  detected_categories_json TEXT NOT NULL DEFAULT '[]',
  privacy_actions_json TEXT NOT NULL DEFAULT '[]',
  token_references_json TEXT NOT NULL DEFAULT '[]',
  original_content_reference TEXT,
  created_at TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  content_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS sanitized_chunks (
  chunk_id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES sanitized_conversations(conversation_id) ON DELETE CASCADE,
  message_ids_json TEXT NOT NULL,
  provider TEXT NOT NULL,
  sanitized_title TEXT NOT NULL,
  sanitized_content TEXT NOT NULL,
  privacy_level TEXT NOT NULL,
  token_references_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT,
  content_hash TEXT NOT NULL UNIQUE,
  embedding_json TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS sanitized_chunks_fts USING fts5(
  sanitized_content,
  sanitized_title,
  provider,
  content='sanitized_chunks',
  content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS sanitized_chunks_ai AFTER INSERT ON sanitized_chunks BEGIN
  INSERT INTO sanitized_chunks_fts(rowid, sanitized_content, sanitized_title, provider)
  VALUES (new.rowid, new.sanitized_content, new.sanitized_title, new.provider);
END;

CREATE TRIGGER IF NOT EXISTS sanitized_chunks_ad AFTER DELETE ON sanitized_chunks BEGIN
  INSERT INTO sanitized_chunks_fts(sanitized_chunks_fts, rowid, sanitized_content, sanitized_title, provider)
  VALUES ('delete', old.rowid, old.sanitized_content, old.sanitized_title, old.provider);
END;

CREATE TABLE IF NOT EXISTS sanitized_entities (
  token TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  first_seen_message_id TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS privacy_audit_events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  subject_ref TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_jobs (
  job_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  source_path TEXT NOT NULL,
  status TEXT NOT NULL,
  imported_conversations INTEGER NOT NULL DEFAULT 0,
  imported_messages INTEGER NOT NULL DEFAULT 0,
  skipped_duplicates INTEGER NOT NULL DEFAULT 0,
  warnings_json TEXT NOT NULL DEFAULT '[]',
  failures_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS retrieval_events (
  event_id TEXT PRIMARY KEY,
  sanitized_query TEXT NOT NULL,
  filters_json TEXT NOT NULL DEFAULT '{}',
  result_ids_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL
);
