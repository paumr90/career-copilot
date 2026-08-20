from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.db.session import engine
from app.modules.governance.models import Source
from app.modules.opportunities.models import JobRequirement, Opportunity
from app.modules.opportunities.schemas import (
    JobDescriptionInput,
    JobRequirementInput,
)
from app.modules.opportunities.service import OpportunityService


def test_job_description_can_be_created_with_rollback() -> None:
    service = OpportunityService()

    job_description = JobDescriptionInput(
        company="Example Technology Company",
        role_title="Digital Transformation Program Manager",
        location="Barcelona",
        raw_text=(
            "We are looking for a Digital Transformation Program Manager. "
            "Candidates must have project management experience. "
            "Experience with AI transformation is preferred."
        ),
        requirements=[
            JobRequirementInput(
                requirement_key="project_management",
                description="Project management experience",
                priority="MUST_HAVE",
                category="EXPERIENCE",
                blocking=True,
                evidence_text=(
                    "Candidates must have project management experience."
                ),
            ),
            JobRequirementInput(
                requirement_key="ai_transformation",
                description="Experience with AI transformation",
                priority="NICE_TO_HAVE",
                category="TECHNOLOGY",
                blocking=False,
                evidence_text=(
                    "Experience with AI transformation is preferred."
                ),
            ),
        ],
    )

    with Session(engine) as session:
        sources_before = session.scalar(
            select(func.count()).select_from(Source)
        )

        opportunities_before = session.scalar(
            select(func.count()).select_from(Opportunity)
        )

        requirements_before = session.scalar(
            select(func.count()).select_from(JobRequirement)
        )

        source, opportunity, requirements = (
            service.create_from_job_description(
                session=session,
                job_description=job_description,
                external_id="example-jd-001",
                uri="https://example.com/jobs/001",
            )
        )

        assert source.source_id is not None
        assert source.source_type == "JD"
        assert source.authority_level == "CANONICAL_JD"
        assert source.immutable is True
        assert source.snapshot_hash is not None
        assert len(source.snapshot_hash) == 64

        assert opportunity.opportunity_id is not None
        assert opportunity.jd_source_id == source.source_id
        assert opportunity.company == "Example Technology Company"
        assert opportunity.role_title == (
            "Digital Transformation Program Manager"
        )

        assert len(requirements) == 2

        assert requirements[0].priority == "MUST_HAVE"
        assert requirements[0].blocking is True

        assert requirements[1].priority == "NICE_TO_HAVE"
        assert requirements[1].blocking is False

        assert session.scalar(
            select(func.count()).select_from(Source)
        ) == sources_before + 1

        assert session.scalar(
            select(func.count()).select_from(Opportunity)
        ) == opportunities_before + 1

        assert session.scalar(
            select(func.count()).select_from(JobRequirement)
        ) == requirements_before + 2

        session.rollback()

    with Session(engine) as session:
        assert session.scalar(
            select(func.count()).select_from(Source)
        ) == sources_before

        assert session.scalar(
            select(func.count()).select_from(Opportunity)
        ) == opportunities_before

        assert session.scalar(
            select(func.count()).select_from(JobRequirement)
        ) == requirements_before