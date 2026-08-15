PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS vault_entities (
  token TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  encrypted_original_value BLOB NOT NULL,
  normalized_fingerprint TEXT NOT NULL,
  key_version TEXT NOT NULL DEFAULT 'v1',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vault_messages (
  message_ref TEXT PRIMARY KEY,
  encrypted_raw_content BLOB NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vault_review_items (
  review_item_id TEXT PRIMARY KEY,
  message_ref TEXT NOT NULL,
  token TEXT,
  entity_type TEXT NOT NULL,
  recommended_action TEXT NOT NULL,
  status TEXT NOT NULL,
  confidence REAL NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vault_audit_events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  subject_ref TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
