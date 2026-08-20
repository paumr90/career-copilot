import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class RuleEvaluation(Base):
    __tablename__ = "rule_evaluations"

    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    rule_set: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    ruleset_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    entity_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    input_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    input_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    result_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )