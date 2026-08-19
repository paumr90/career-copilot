import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class Source(Base):
    __tablename__ = "sources"

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('PROFILE', 'CV', 'JD', 'EMAIL', 'ATS', 'USER', 'INTERVIEW', 'FEEDBACK')",
            name="ck_sources_source_type_valid",
        ),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    external_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    uri: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    snapshot_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    metadata_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    authority_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    immutable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )


class ProfileFact(Base):
    __tablename__ = "profile_facts"

    __table_args__ = (
        CheckConstraint(
            "evidence_state IN ('CONFIRMED', 'INFERRED', 'UNKNOWN')",
            name="ck_profile_facts_evidence_state_valid",
        ),
    )

    fact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    fact_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    value_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    evidence_state: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.source_id"),
        nullable=False,
    )

    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    valid_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profile_facts.fact_id"),
        nullable=True,
    )