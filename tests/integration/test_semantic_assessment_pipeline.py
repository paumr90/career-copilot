import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import (
    EvidenceTier,
    FitRecommendation,
)
from app.infrastructure.db.session import engine
from app.modules.audit.models import RuleEvaluation
from app.modules.fit.pipeline import (
    RequirementAssessmentPipeline,
)
from app.modules.fit.providers import (
    StaticSemanticAssessmentProvider,
)
from app.modules.fit.schemas import (
    ProfileEvidenceReference,
    RequirementAssessmentProposal,
)
from app.modules.opportunities.schemas import (
    JobDescriptionInput,
    JobRequirementInput,
)
from app.modules.opportunities.service import (
    OpportunityService,
)


def build_job_description() -> JobDescriptionInput:
    return JobDescriptionInput(
        company="Example Semantic Company",
        role_title="Program Manager",
        location="Barcelona",
        raw_text=(
            "Project management experience is required."
        ),
        requirements=[
            JobRequirementInput(
                requirement_key="project_management",
                description=(
                    "Experience managing complex "
                    "projects and project teams"
                ),
                priority="MUST_HAVE",
                category="EXPERIENCE",
                blocking=False,
                evidence_text=(
                    "Strong project management "
                    "experience required."
                ),
            ),
        ],
    )


def test_provider_pipeline_can_score_valid_proposal() -> None:
    opportunity_service = OpportunityService()
    pipeline = RequirementAssessmentPipeline()

    with Session(engine) as session:
        evaluations_before = session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        )

        _, opportunity, _ = (
            opportunity_service
            .create_from_job_description(
                session=session,
                job_description=(
                    build_job_description()
                ),
                external_id=(
                    "semantic-provider-valid"
                ),
            )
        )

        contexts = pipeline.prepare_context(
            session=session,
            opportunity_id=(
                opportunity.opportunity_id
            ),
        )

        primary_ranked = next(
            ranked
            for ranked
            in contexts[0]
            .ranking_result.ranked_candidates
            if (
                ranked.candidate.tier
                == EvidenceTier.PRIMARY
            )
        )

        provider = (
            StaticSemanticAssessmentProvider(
                proposals={
                    "project_management":
                        RequirementAssessmentProposal(
                            requirement_key=(
                                "project_management"
                            ),
                            proposed_status="MATCH",
                            evidence=[
                                ProfileEvidenceReference(
                                    profile_fact_id=(
                                        primary_ranked
                                        .candidate
                                        .profile_fact_id
                                    ),
                                    note=(
                                        "Primary governed "
                                        "evidence."
                                    ),
                                )
                            ],
                            rationale=(
                                "Primary evidence supports "
                                "the requirement."
                            ),
                        )
                }
            )
        )

        (
            result,
            fit_evaluation,
            assessment_evaluation,
            assessments,
            proposals,
        ) = pipeline.evaluate_with_provider_and_record(
            session=session,
            opportunity_id=(
                opportunity.opportunity_id
            ),
            provider=provider,
        )

        assert len(proposals) == 1
        assert len(assessments) == 1

        assert (
            proposals[0].requirement_key
            == "project_management"
        )

        assert (
            assessments[0].match_status.value
            == "MATCH"
        )

        assert result.score == 100.0

        assert (
            result.recommendation
            == FitRecommendation.APPLY
        )

        assert (
            assessment_evaluation.rule_set
            == "requirement_assessment"
        )

        assert (
            fit_evaluation.rule_set
            == "fit_scoring"
        )

        assert (
            assessment_evaluation
            .input_json["proposal_origin"]
            == {
                "mode": "provider",
                "provider_name": "static_local",
                "provider_version": "0.1",
                "semantic_rule_version": "0.1",
            }
        )

        assert (
            assessment_evaluation
            .input_json["rules_snapshot"]
            ["semantic_assessment"]["version"]
            == "0.1"
        )

        assert (
            assessment_evaluation
            .input_json["rules_snapshot"]
            ["semantic_assessment"]["role"]
            == "requirement_assessment_proposer"
        )

        assert session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        ) == evaluations_before + 2

        session.rollback()

    with Session(engine) as session:
        assert session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        ) == evaluations_before


def test_provider_invented_evidence_is_rejected_before_audit() -> None:
    opportunity_service = OpportunityService()
    pipeline = RequirementAssessmentPipeline()

    with Session(engine) as session:
        _, opportunity, _ = (
            opportunity_service
            .create_from_job_description(
                session=session,
                job_description=(
                    build_job_description()
                ),
                external_id=(
                    "semantic-provider-invented"
                ),
            )
        )

        evaluations_before = session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        )

        provider = (
            StaticSemanticAssessmentProvider(
                proposals={
                    "project_management":
                        RequirementAssessmentProposal(
                            requirement_key=(
                                "project_management"
                            ),
                            proposed_status="MATCH",
                            evidence=[
                                ProfileEvidenceReference(
                                    profile_fact_id=(
                                        uuid.uuid4()
                                    ),
                                    note=(
                                        "Invented provider "
                                        "evidence."
                                    ),
                                )
                            ],
                            rationale=(
                                "Provider claims a match."
                            ),
                        )
                }
            )
        )

        with pytest.raises(
            ValueError,
            match=(
                "Assessment evidence must come "
                "from the governed ranked shortlist"
            ),
        ):
            pipeline.evaluate_with_provider_and_record(
                session=session,
                opportunity_id=(
                    opportunity.opportunity_id
                ),
                provider=provider,
            )

        assert session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        ) == evaluations_before

        session.rollback()


def test_provider_missing_requirement_is_rejected_before_audit() -> None:
    opportunity_service = OpportunityService()
    pipeline = RequirementAssessmentPipeline()

    with Session(engine) as session:
        _, opportunity, _ = (
            opportunity_service
            .create_from_job_description(
                session=session,
                job_description=(
                    build_job_description()
                ),
                external_id=(
                    "semantic-provider-missing"
                ),
            )
        )

        evaluations_before = session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        )

        provider = (
            StaticSemanticAssessmentProvider(
                proposals={}
            )
        )

        with pytest.raises(
            ValueError,
            match=(
                "has no proposal configured for "
                "requirement_key"
            ),
        ):
            pipeline.evaluate_with_provider_and_record(
                session=session,
                opportunity_id=(
                    opportunity.opportunity_id
                ),
                provider=provider,
            )

        assert session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        ) == evaluations_before

        session.rollback()