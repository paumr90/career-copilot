import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class Opportunity(Base):
    __tablename__ = "opportunities"

    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    jd_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.source_id"),
        nullable=False,
    )

    company: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class JobRequirement(Base):
    __tablename__ = "job_requirements"

    __table_args__ = (
        CheckConstraint(
            "priority IN ('MUST_HAVE', 'NICE_TO_HAVE', 'SECONDARY')",
            name="ck_job_requirements_priority_valid",
        ),
        CheckConstraint(
            "category IN ("
            "'EXPERIENCE', "
            "'EDUCATION', "
            "'SKILL', "
            "'LANGUAGE', "
            "'INDUSTRY', "
            "'TECHNOLOGY', "
            "'RESPONSIBILITY', "
            "'LOCATION', "
            "'WORK_MODE', "
            "'COMPENSATION', "
            "'OTHER'"
            ")",
            name="ck_job_requirements_category_valid",
        ),
        UniqueConstraint(
            "opportunity_id",
            "requirement_key",
            name="uq_job_requirements_opportunity_key",
        ),
    )

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("opportunities.opportunity_id"),
        nullable=False,
    )

    requirement_key: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )

    priority: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    blocking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    evidence_text: Mapped[str | None] = mapped_column(
        String(4000),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )