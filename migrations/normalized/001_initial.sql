PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS normalized_sources (
  source_fingerprint TEXT PRIMARY KEY,
  source_path TEXT NOT NULL,
  provider TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS normalized_conversations (
  conversation_id TEXT PRIMARY KEY,
  source_fingerprint TEXT NOT NULL REFERENCES normalized_sources(source_fingerprint),
  provider TEXT NOT NULL,
  remote_id TEXT,
  title TEXT NOT NULL,
  created_at TEXT,
  updated_at TEXT,
  source_file TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  content_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS normalized_messages (
  message_id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES normalized_conversations(conversation_id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  position INTEGER NOT NULL,
  created_at TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  content_hash TEXT NOT NULL UNIQUE,
  UNIQUE(conversation_id, position)
);

CREATE TABLE IF NOT EXISTS normalized_import_jobs (
  job_id TEXT PRIMARY KEY,
  source_path TEXT NOT NULL,
  provider TEXT NOT NULL,
  status TEXT NOT NULL,
  imported_conversations INTEGER NOT NULL DEFAULT 0,
  imported_messages INTEGER NOT NULL DEFAULT 0,
  skipped_duplicates INTEGER NOT NULL DEFAULT 0,
  warnings_json TEXT NOT NULL DEFAULT '[]',
  failures_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  completed_at TEXT
);
