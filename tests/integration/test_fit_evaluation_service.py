import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import FitRecommendation
from app.infrastructure.db.session import engine
from app.modules.audit.models import RuleEvaluation
from app.modules.audit.service import RuleEvaluationService
from app.modules.fit.schemas import (
    ProfileEvidenceReference,
    RequirementAssessment,
)
from app.modules.fit.service import FitEvaluationService
from app.modules.governance.models import (
    ProfileFact,
    Source,
)
from app.modules.opportunities.models import (
    JobRequirement,
    Opportunity,
)
from app.modules.opportunities.schemas import (
    JobDescriptionInput,
    JobRequirementInput,
)
from app.modules.opportunities.service import (
    OpportunityService,
)


def get_canonical_profile_fact_id(
    session: Session,
) -> uuid.UUID:
    fact_id = session.scalar(
        select(ProfileFact.fact_id)
        .join(
            Source,
            ProfileFact.source_id == Source.source_id,
        )
        .where(
            Source.source_type == "PROFILE",
            Source.authority_level
            == "CANONICAL_PROFILE",
            Source.immutable.is_(True),
            ProfileFact.evidence_state
            == "CONFIRMED",
            ProfileFact.superseded_by.is_(None),
        )
        .limit(1)
    )

    assert fact_id is not None

    return fact_id


def build_job_description() -> JobDescriptionInput:
    return JobDescriptionInput(
        company="Example Technology Company",
        role_title=(
            "Digital Transformation Program Manager"
        ),
        location="Barcelona",
        raw_text=(
            "Project management experience is required. "
            "Cloud-platform experience is preferred."
        ),
        requirements=[
            JobRequirementInput(
                requirement_key="project_management",
                description=(
                    "Project management experience"
                ),
                priority="MUST_HAVE",
                category="EXPERIENCE",
                blocking=False,
                evidence_text=(
                    "Project management experience "
                    "is required."
                ),
            ),
            JobRequirementInput(
                requirement_key="cloud_platform",
                description=(
                    "Cloud-platform experience"
                ),
                priority="NICE_TO_HAVE",
                category="TECHNOLOGY",
                blocking=False,
                evidence_text=(
                    "Cloud-platform experience "
                    "is preferred."
                ),
            ),
        ],
    )


def build_assessments(
    profile_fact_id: uuid.UUID,
) -> list[RequirementAssessment]:
    return [
        RequirementAssessment(
            requirement_key="project_management",
            match_status="MATCH",
            evidence=[
                ProfileEvidenceReference(
                    profile_fact_id=profile_fact_id,
                    note=(
                        "Confirmed Career Master evidence."
                    ),
                )
            ],
            rationale=(
                "Career Master evidence supports "
                "the requirement."
            ),
        ),
        RequirementAssessment(
            requirement_key="cloud_platform",
            match_status="UNKNOWN",
            evidence=[],
            rationale=(
                "Career Master contains insufficient "
                "evidence about this requirement."
            ),
        ),
    ]


def test_real_opportunity_fit_can_be_audited() -> None:
    opportunity_service = OpportunityService()
    fit_service = FitEvaluationService()
    audit_service = RuleEvaluationService()

    with Session(engine) as session:
        sources_before = session.scalar(
            select(func.count()).select_from(Source)
        )

        opportunities_before = session.scalar(
            select(func.count()).select_from(
                Opportunity
            )
        )

        requirements_before = session.scalar(
            select(func.count()).select_from(
                JobRequirement
            )
        )

        evaluations_before = session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        )

        profile_fact_id = (
            get_canonical_profile_fact_id(
                session
            )
        )

        source, opportunity, _ = (
            opportunity_service.create_from_job_description(
                session=session,
                job_description=build_job_description(),
                external_id="fit-test-jd-001",
                uri="https://example.com/jobs/fit-test",
            )
        )

        result, evaluation = (
            fit_service.evaluate_opportunity_and_record(
                session=session,
                opportunity_id=(
                    opportunity.opportunity_id
                ),
                assessments=build_assessments(
                    profile_fact_id
                ),
            )
        )

        assert source.source_type == "JD"

        assert result.score == 100.0
        assert result.coverage_percent == 71.43

        assert (
            result.recommendation
            == FitRecommendation.APPLY
        )

        assert evaluation.rule_set == "fit_scoring"

        assert (
            evaluation.entity_id
            == opportunity.opportunity_id
        )

        assert (
            evaluation.input_json[
                "opportunity"
            ]["jd_snapshot_hash"]
            == source.snapshot_hash
        )

        assert len(
            evaluation.input_json["requirements"]
        ) == 2

        assert (
            evaluation.input_hash
            == audit_service.calculate_input_hash(
                evaluation.input_json
            )
        )

        assert session.scalar(
            select(func.count()).select_from(Source)
        ) == sources_before + 1

        assert session.scalar(
            select(func.count()).select_from(
                Opportunity
            )
        ) == opportunities_before + 1

        assert session.scalar(
            select(func.count()).select_from(
                JobRequirement
            )
        ) == requirements_before + 2

        assert session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        ) == evaluations_before + 1

        session.rollback()

    with Session(engine) as session:
        assert session.scalar(
            select(func.count()).select_from(Source)
        ) == sources_before

        assert session.scalar(
            select(func.count()).select_from(
                Opportunity
            )
        ) == opportunities_before

        assert session.scalar(
            select(func.count()).select_from(
                JobRequirement
            )
        ) == requirements_before

        assert session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        ) == evaluations_before


def test_fake_opportunity_is_rejected() -> None:
    fit_service = FitEvaluationService()

    with Session(engine) as session:
        with pytest.raises(
            ValueError,
            match=(
                "Fit evaluation requires an existing "
                "Opportunity"
            ),
        ):
            fit_service.evaluate_opportunity_and_record(
                session=session,
                opportunity_id=uuid.uuid4(),
                assessments=[],
            )

        session.rollback()


def test_missing_assessment_is_rejected() -> None:
    opportunity_service = OpportunityService()
    fit_service = FitEvaluationService()

    with Session(engine) as session:
        profile_fact_id = (
            get_canonical_profile_fact_id(
                session
            )
        )

        _, opportunity, _ = (
            opportunity_service.create_from_job_description(
                session=session,
                job_description=build_job_description(),
                external_id="fit-test-jd-missing",
            )
        )

        assessments = build_assessments(
            profile_fact_id
        )

        with pytest.raises(
            ValueError,
            match=(
                "Assessment keys must exactly match "
                "the canonical JobRequirements"
            ),
        ):
            fit_service.evaluate_opportunity_and_record(
                session=session,
                opportunity_id=(
                    opportunity.opportunity_id
                ),
                assessments=assessments[:1],
            )

        session.rollback()


def test_fake_profile_evidence_is_rejected() -> None:
    opportunity_service = OpportunityService()
    fit_service = FitEvaluationService()

    with Session(engine) as session:
        _, opportunity, _ = (
            opportunity_service.create_from_job_description(
                session=session,
                job_description=build_job_description(),
                external_id="fit-test-jd-fake-evidence",
            )
        )

        assessments = [
            RequirementAssessment(
                requirement_key="project_management",
                match_status="MATCH",
                evidence=[
                    ProfileEvidenceReference(
                        profile_fact_id=uuid.uuid4(),
                        note="Fake evidence.",
                    )
                ],
                rationale=(
                    "This uses invalid evidence."
                ),
            ),
            RequirementAssessment(
                requirement_key="cloud_platform",
                match_status="UNKNOWN",
                evidence=[],
                rationale=(
                    "Insufficient evidence."
                ),
            ),
        ]

        with pytest.raises(
            ValueError,
            match=(
                "Fit evidence must reference active, "
                "confirmed, canonical Career Master facts"
            ),
        ):
            fit_service.evaluate_opportunity_and_record(
                session=session,
                opportunity_id=(
                    opportunity.opportunity_id
                ),
                assessments=assessments,
            )

        session.rollback()


def test_non_jd_opportunity_is_rejected() -> None:
    fit_service = FitEvaluationService()

    with Session(engine) as session:
        profile_source = session.scalar(
            select(Source)
            .where(
                Source.source_type == "PROFILE"
            )
            .limit(1)
        )

        assert profile_source is not None

        rogue_opportunity = Opportunity(
            jd_source_id=profile_source.source_id,
            company="Invalid Example",
            role_title="Invalid Opportunity",
            location="Barcelona",
            raw_text="Invalid JD provenance.",
        )

        session.add(rogue_opportunity)
        session.flush()

        with pytest.raises(
            ValueError,
            match=(
                "Fit evaluation requires an existing "
                "Opportunity"
            ),
        ):
            fit_service.evaluate_opportunity_and_record(
                session=session,
                opportunity_id=(
                    rogue_opportunity.opportunity_id
                ),
                assessments=[],
            )

        session.rollback()