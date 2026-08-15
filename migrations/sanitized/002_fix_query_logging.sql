-- Milestone 6 Privacy Violation Fix: Query logging should store length only, not raw query text
-- This migration replaces sanitized_query TEXT with query_length INTEGER to prevent
-- audit tables from storing searchable query patterns.
-- See: test_query_logging_does_not_store_raw_text()

PRAGMA foreign_keys = ON;

-- Drop and recreate the table with the correct schema (idempotent: DROP IF EXISTS)
DROP TABLE IF EXISTS retrieval_events;

-- Create new table with count-only audit fields
CREATE TABLE retrieval_events (
  event_id TEXT PRIMARY KEY,
  query_length INTEGER NOT NULL,
  result_count INTEGER NOT NULL DEFAULT 0,
  filters_json TEXT NOT NULL DEFAULT '{}',
  result_ids_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL
);
