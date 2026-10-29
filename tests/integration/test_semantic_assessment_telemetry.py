from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import EvidenceTier
from app.infrastructure.db.session import engine
from app.modules.audit.models import RuleEvaluation
from app.modules.fit.pipeline import (
    RequirementAssessmentPipeline,
)
from app.modules.fit.schemas import (
    ProfileEvidenceReference,
    RequirementAssessmentProposal,
    SemanticAssessmentRequest,
)
from app.modules.fit.telemetry import (
    SemanticAssessmentProviderResult,
    SemanticAssessmentTelemetry,
)
from app.modules.opportunities.schemas import (
    JobDescriptionInput,
    JobRequirementInput,
)
from app.modules.opportunities.service import (
    OpportunityService,
)


class FakeTelemetrySemanticProvider:
    def __init__(
        self,
        *,
        proposal: RequirementAssessmentProposal,
    ) -> None:
        self._proposal = proposal.model_copy(
            deep=True
        )

    @property
    def provider_name(self) -> str:
        return "fake_telemetry"

    @property
    def provider_version(self) -> str:
        return "0.1"

    def propose(
        self,
        *,
        request: SemanticAssessmentRequest,
    ) -> RequirementAssessmentProposal:
        raise AssertionError(
            "Pipeline should use propose_with_telemetry "
            "when the provider exposes it."
        )

    def propose_with_telemetry(
        self,
        *,
        request: SemanticAssessmentRequest,
    ) -> SemanticAssessmentProviderResult:
        return SemanticAssessmentProviderResult(
            proposal=self._proposal.model_copy(
                deep=True
            ),
            telemetry=(
                SemanticAssessmentTelemetry(
                    provider_name=(
                        self.provider_name
                    ),
                    provider_version=(
                        self.provider_version
                    ),
                    model_name="fake-model",
                    response_id=(
                        "resp_semantic_pipeline"
                    ),
                    input_tokens=300,
                    output_tokens=50,
                    total_tokens=350,
                    latency_ms=125.0,
                )
            ),
        )


def build_job_description() -> JobDescriptionInput:
    return JobDescriptionInput(
        company="Example Telemetry Company",
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
                    "Project management experience "
                    "is required."
                ),
            ),
        ],
    )


def test_provider_telemetry_is_recorded_in_assessment_audit() -> None:
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
                    "semantic-provider-telemetry"
                ),
            )
        )

        contexts = pipeline.prepare_context(
            session=session,
            opportunity_id=(
                opportunity.opportunity_id
            ),
        )

        semantic_request = (
            pipeline.semantic_request_builder
            .build(
                requirement=(
                    contexts[0].requirement
                ),
                ranking_result=(
                    contexts[0].ranking_result
                ),
            )
        )

        primary_evidence = next(
            evidence
            for evidence
            in semantic_request.ranked_evidence
            if evidence.tier == EvidenceTier.PRIMARY
        )

        provider = FakeTelemetrySemanticProvider(
            proposal=RequirementAssessmentProposal(
                requirement_key="project_management",
                proposed_status="MATCH",
                evidence=[
                    ProfileEvidenceReference(
                        profile_fact_id=(
                            primary_evidence
                            .profile_fact_id
                        ),
                        note=(
                            "Primary governed evidence."
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
            _,
            _,
            assessment_evaluation,
            _,
            _,
        ) = pipeline.evaluate_with_provider_and_record(
            session=session,
            opportunity_id=(
                opportunity.opportunity_id
            ),
            provider=provider,
        )

        telemetry = (
            assessment_evaluation
            .input_json["provider_telemetry"]
            ["project_management"]
        )

        assert telemetry == {
            "discarded_unknown_evidence_ids": [],
            "provider_name": "fake_telemetry",
            "provider_version": "0.1",
            "model_name": "fake-model",
            "response_id": "resp_semantic_pipeline",
            "input_tokens": 300,
            "output_tokens": 50,
            "total_tokens": 350,
            "latency_ms": 125.0,
        }

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