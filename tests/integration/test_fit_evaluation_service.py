import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import FitRecommendation
from app.infrastructure.db.session import engine
from app.modules.audit.models import RuleEvaluation
from app.modules.audit.service import RuleEvaluationService
from app.modules.fit.schemas import (
    FitScoringRequirement,
    ProfileEvidenceReference,
    RequirementAssessment,
)
from app.modules.fit.service import FitEvaluationService
from app.modules.governance.models import (
    ProfileFact,
    Source,
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
            Source.authority_level == "CANONICAL_PROFILE",
            Source.immutable.is_(True),
            ProfileFact.evidence_state == "CONFIRMED",
            ProfileFact.superseded_by.is_(None),
        )
        .limit(1)
    )

    assert fact_id is not None

    return fact_id


def build_evidence(
    profile_fact_id: uuid.UUID,
) -> ProfileEvidenceReference:
    return ProfileEvidenceReference(
        profile_fact_id=profile_fact_id,
        note="Confirmed Career Master evidence.",
    )


def test_fit_evaluation_can_be_audited_with_rollback() -> None:
    service = FitEvaluationService()
    audit_service = RuleEvaluationService()

    opportunity_id = uuid.uuid4()

    with Session(engine) as session:
        profile_fact_id = get_canonical_profile_fact_id(
            session
        )

        requirements = [
            FitScoringRequirement(
                requirement_key="project_management",
                priority="MUST_HAVE",
                blocking=False,
                assessment=RequirementAssessment(
                    requirement_key="project_management",
                    match_status="MATCH",
                    evidence=[
                        build_evidence(
                            profile_fact_id
                        )
                    ],
                    rationale=(
                        "Career Master evidence supports "
                        "the requirement."
                    ),
                ),
            ),
            FitScoringRequirement(
                requirement_key="cloud_platform",
                priority="NICE_TO_HAVE",
                blocking=False,
                assessment=RequirementAssessment(
                    requirement_key="cloud_platform",
                    match_status="UNKNOWN",
                    evidence=[],
                    rationale=(
                        "Career Master contains insufficient "
                        "evidence about this requirement."
                    ),
                ),
            ),
        ]

        evaluations_before = session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        )

        result, evaluation = (
            service.evaluate_and_record(
                session,
                opportunity_id=opportunity_id,
                requirements=requirements,
            )
        )

        assert result.score == 100.0
        assert result.coverage_percent == 71.43
        assert (
            result.recommendation
            == FitRecommendation.APPLY
        )

        assert evaluation.evaluation_id is not None
        assert evaluation.rule_set == "fit_scoring"
        assert evaluation.ruleset_version == "0.1"
        assert evaluation.entity_type == "opportunity"
        assert evaluation.entity_id == opportunity_id

        assert (
            evaluation.input_json[
                "rules_snapshot"
            ]["version"]
            == "0.1"
        )

        assert len(
            evaluation.input_json["requirements"]
        ) == 2

        assert (
            evaluation.input_json["requirements"][0][
                "assessment"
            ]["evidence"][0]["profile_fact_id"]
            == str(profile_fact_id)
        )

        assert evaluation.input_hash == (
            audit_service.calculate_input_hash(
                evaluation.input_json
            )
        )

        assert evaluation.result_json == (
            result.model_dump(mode="json")
        )

        assert session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        ) == evaluations_before + 1

        session.rollback()

    with Session(engine) as session:
        assert session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        ) == evaluations_before


def test_fake_profile_evidence_is_rejected() -> None:
    service = FitEvaluationService()

    fake_profile_fact_id = uuid.uuid4()

    requirements = [
        FitScoringRequirement(
            requirement_key="project_management",
            priority="MUST_HAVE",
            blocking=False,
            assessment=RequirementAssessment(
                requirement_key="project_management",
                match_status="MATCH",
                evidence=[
                    build_evidence(
                        fake_profile_fact_id
                    )
                ],
                rationale=(
                    "This assessment uses invalid evidence."
                ),
            ),
        )
    ]

    with Session(engine) as session:
        evaluations_before = session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        )

        with pytest.raises(
            ValueError,
            match=(
                "Fit evidence must reference active, "
                "confirmed, canonical Career Master facts"
            ),
        ):
            service.evaluate_and_record(
                session,
                opportunity_id=uuid.uuid4(),
                requirements=requirements,
            )

        assert session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        ) == evaluations_before

        session.rollback()