"""normalized foundation

Revision ID: 0001_normalized_foundation
Revises:
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_normalized_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "normalized_sources",
        sa.Column("source_fingerprint", sa.String(), primary_key=True),
        sa.Column("source_path", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "normalized_conversations",
        sa.Column("conversation_id", sa.String(), primary_key=True),
        sa.Column("source_fingerprint", sa.String(), sa.ForeignKey("normalized_sources.source_fingerprint"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("remote_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
        sa.Column("source_file", sa.String(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("content_hash", sa.String(), nullable=False, unique=True),
    )
    op.create_table(
        "normalized_messages",
        sa.Column("message_id", sa.String(), primary_key=True),
        sa.Column("conversation_id", sa.String(), sa.ForeignKey("normalized_conversations.conversation_id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("content_hash", sa.String(), nullable=False, unique=True),
        sa.UniqueConstraint("conversation_id", "position"),
    )
    op.create_table(
        "normalized_import_jobs",
        sa.Column("job_id", sa.String(), primary_key=True),
        sa.Column("source_path", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("imported_conversations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_messages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_duplicates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("failures_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("completed_at", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("normalized_import_jobs")
    op.drop_table("normalized_messages")
    op.drop_table("normalized_conversations")
    op.drop_table("normalized_sources")
