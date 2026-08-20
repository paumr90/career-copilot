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
from app.modules.audit.service import RuleEvaluationService
from app.modules.fit.pipeline import (
    RequirementAssessmentPipeline,
)
from app.modules.fit.schemas import (
    ProfileEvidenceReference,
    RequirementAssessmentProposal,
)
from app.modules.governance.models import Source
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


def build_job_description() -> JobDescriptionInput:
    return JobDescriptionInput(
        company="Example Technology Company",
        role_title="Transformation Program Manager",
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


def test_pipeline_prepares_governed_context() -> None:
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
                    "assessment-pipeline-context"
                ),
            )
        )

        contexts = pipeline.prepare_context(
            session=session,
            opportunity_id=(
                opportunity.opportunity_id
            ),
        )

        assert len(contexts) == 1

        context = contexts[0]

        assert (
            context.requirement.requirement_key
            == "project_management"
        )

        assert (
            context.ranking_result.requirement_key
            == "project_management"
        )

        assert (
            context.ranking_result
            .retrieval_rule_version
            == "0.1"
        )

        assert (
            context.ranking_result
            .ranking_rule_version
            == "0.1"
        )

        assert (
            context.ranking_result
            .total_candidate_count
            > 0
        )

        assert (
            context.ranking_result
            .ranked_candidates
        )

        session.rollback()


def test_pipeline_can_validate_score_and_audit_proposal() -> None:
    opportunity_service = OpportunityService()
    pipeline = RequirementAssessmentPipeline()
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

        _, opportunity, _ = (
            opportunity_service
            .create_from_job_description(
                session=session,
                job_description=(
                    build_job_description()
                ),
                external_id=(
                    "assessment-pipeline-fit"
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

        proposal = (
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
                            "Primary Career Master "
                            "evidence."
                        ),
                    )
                ],
                rationale=(
                    "Primary evidence supports "
                    "the requirement."
                ),
            )
        )

        (
            result,
            fit_evaluation,
            assessment_evaluation,
            assessments,
        ) = pipeline.evaluate_proposals_and_record(
            session=session,
            opportunity_id=(
                opportunity.opportunity_id
            ),
            proposals=[proposal],
        )

        assert len(assessments) == 1

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
            assessment_evaluation.ruleset_version
            == "0.1"
        )

        assert (
            assessment_evaluation.entity_id
            == opportunity.opportunity_id
        )

        assert (
            assessment_evaluation
            .input_json["rules_snapshot"]
            ["evidence_retrieval"]["version"]
            == "0.1"
        )

        assert (
            assessment_evaluation
            .input_json["rules_snapshot"]
            ["evidence_ranking"]["version"]
            == "0.1"
        )

        assert (
            assessment_evaluation
            .input_json["rules_snapshot"]
            ["requirement_assessment"]["version"]
            == "0.1"
        )

        assert (
            assessment_evaluation.input_hash
            == audit_service.calculate_input_hash(
                assessment_evaluation.input_json
            )
        )

        assert (
            assessment_evaluation.result_json
            == {
                "assessments": [
                    assessment.model_dump(
                        mode="json"
                    )
                    for assessment
                    in assessments
                ]
            }
        )

        assert (
            fit_evaluation.rule_set
            == "fit_scoring"
        )

        assert (
            fit_evaluation.entity_id
            == opportunity.opportunity_id
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
        ) == requirements_before + 1

        assert session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        ) == evaluations_before + 2

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


def test_missing_proposal_is_rejected_without_audit() -> None:
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
                    "assessment-pipeline-missing"
                ),
            )
        )

        evaluations_before = session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        )

        with pytest.raises(
            ValueError,
            match=(
                "Assessment proposal keys must "
                "exactly match"
            ),
        ):
            pipeline.evaluate_proposals_and_record(
                session=session,
                opportunity_id=(
                    opportunity.opportunity_id
                ),
                proposals=[],
            )

        assert session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        ) == evaluations_before

        session.rollback()


def test_fake_opportunity_is_rejected() -> None:
    pipeline = RequirementAssessmentPipeline()

    with Session(engine) as session:
        with pytest.raises(
            ValueError,
            match=(
                "Requirement assessment requires "
                "an existing Opportunity"
            ),
        ):
            pipeline.prepare_context(
                session=session,
                opportunity_id=uuid.uuid4(),
            )

        session.rollback()