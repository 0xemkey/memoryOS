from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class NormalizedSourceRow(Base):
    __tablename__ = "normalized_sources"

    source_fingerprint: Mapped[str] = mapped_column(String, primary_key=True)
    source_path: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    conversations: Mapped[list[NormalizedConversationRow]] = relationship(back_populates="source")


class NormalizedConversationRow(Base):
    __tablename__ = "normalized_conversations"

    conversation_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_fingerprint: Mapped[str] = mapped_column(
        ForeignKey("normalized_sources.source_fingerprint"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    remote_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String, nullable=True)
    source_file: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    content_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    source: Mapped[NormalizedSourceRow] = relationship(back_populates="conversations")
    messages: Mapped[list[NormalizedMessageRow]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="NormalizedMessageRow.position",
    )


class NormalizedMessageRow(Base):
    __tablename__ = "normalized_messages"
    __table_args__ = (UniqueConstraint("conversation_id", "position"),)

    message_id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("normalized_conversations.conversation_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    content_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    conversation: Mapped[NormalizedConversationRow] = relationship(back_populates="messages")


class NormalizedImportJobRow(Base):
    __tablename__ = "normalized_import_jobs"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_path: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    imported_conversations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    failures_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(String, nullable=True)
