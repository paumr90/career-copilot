from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.orm import Session

import pytest

from app.infrastructure.db.session import engine
from app.modules.audit.models import (
    RuleEvaluation,
)
from app.modules.governance.models import Source
from app.modules.opportunities.intake import (
    JDIntakeService,
)
from app.modules.opportunities.models import (
    JobRequirement,
    Opportunity,
)
from app.modules.opportunities.providers import (
    StaticJDExtractionProvider,
)
from app.modules.opportunities.schemas import (
    JDExtractionProposal,
    JDExtractionProviderResult,
    JDExtractionRequest,
    JDExtractionTelemetry,
    JobRequirementInput,
    RawJobDescriptionInput,
)


RAW_JD = (
    "Candidates must have at least 5 years "
    "of project management experience."
)


def build_raw_job() -> RawJobDescriptionInput:
    return RawJobDescriptionInput(
        company="Telemetry Example",
        role_title="Program Manager",
        location="Barcelona",
        raw_text=RAW_JD,
        source_url=(
            "https://example.com/jobs/"
            "telemetry-test"
        ),
    )


def build_proposal() -> JDExtractionProposal:
    return JDExtractionProposal(
        requirements=[
            JobRequirementInput(
                requirement_key=(
                    "project_management_experience"
                ),
                description=(
                    "At least 5 years of project "
                    "management experience"
                ),
                priority="MUST_HAVE",
                category="EXPERIENCE",
                blocking=False,
                evidence_text=(
                    "must have at least 5 years "
                    "of project management experience"
                ),
            )
        ]
    )


class TestTelemetryProvider:
    @property
    def provider_name(self) -> str:
        return "telemetry_test"

    @property
    def provider_version(self) -> str:
        return "0.1"

    def extract(
        self,
        *,
        request: JDExtractionRequest,
    ) -> JDExtractionProposal:
        _ = request

        return build_proposal()

    def extract_with_telemetry(
        self,
        *,
        request: JDExtractionRequest,
    ) -> JDExtractionProviderResult:
        _ = request

        return JDExtractionProviderResult(
            proposal=build_proposal(),
            telemetry=JDExtractionTelemetry(
                provider_name=(
                    self.provider_name
                ),
                provider_version=(
                    self.provider_version
                ),
                model_name=(
                    "test-model-resolved"
                ),
                response_id=(
                    "resp_test_123"
                ),
                input_tokens=120,
                output_tokens=30,
                total_tokens=150,
                latency_ms=250.0,
            ),
        )


class MismatchedTelemetryProvider(
    TestTelemetryProvider
):
    def extract_with_telemetry(
        self,
        *,
        request: JDExtractionRequest,
    ) -> JDExtractionProviderResult:
        _ = request

        return JDExtractionProviderResult(
            proposal=build_proposal(),
            telemetry=JDExtractionTelemetry(
                provider_name="other_provider",
                provider_version="0.1",
            ),
        )


def test_telemetry_provider_is_recorded_in_extraction_audit() -> None:
    intake_service = JDIntakeService()
    provider = TestTelemetryProvider()
    raw_job = build_raw_job()

    with Session(engine) as session:
        evaluations_before = session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        )

        (
            _,
            opportunity,
            _,
            _,
            _,
            extraction_evaluation,
        ) = intake_service.create_from_provider(
            session=session,
            raw_job=raw_job,
            provider=provider,
            external_id=(
                "telemetry-provider-test"
            ),
        )

        telemetry = (
            extraction_evaluation
            .result_json["provider_telemetry"]
        )

        assert telemetry == {
            "provider_name": "telemetry_test",
            "provider_version": "0.1",
            "model_name": "test-model-resolved",
            "response_id": "resp_test_123",
            "input_tokens": 120,
            "output_tokens": 30,
            "total_tokens": 150,
            "latency_ms": 250.0,
        }

        assert (
            extraction_evaluation.entity_id
            == opportunity.opportunity_id
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


def test_static_provider_gets_safe_local_telemetry() -> None:
    intake_service = JDIntakeService()

    provider = StaticJDExtractionProvider(
        proposal=build_proposal()
    )

    with Session(engine) as session:
        (
            _,
            _,
            _,
            _,
            _,
            extraction_evaluation,
        ) = intake_service.create_from_provider(
            session=session,
            raw_job=build_raw_job(),
            provider=provider,
            external_id=(
                "static-telemetry-test"
            ),
        )

        telemetry = (
            extraction_evaluation
            .result_json["provider_telemetry"]
        )

        assert telemetry == {
            "provider_name": "static_local",
            "provider_version": "0.1",
            "model_name": None,
            "response_id": None,
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "latency_ms": None,
        }

        session.rollback()


def test_mismatched_provider_identity_writes_nothing() -> None:
    intake_service = JDIntakeService()

    provider = (
        MismatchedTelemetryProvider()
    )

    with Session(engine) as session:
        sources_before = session.scalar(
            select(func.count()).select_from(
                Source
            )
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

        with pytest.raises(
            ValueError,
            match=(
                "telemetry provider_name "
                "does not match"
            ),
        ):
            intake_service.create_from_provider(
                session=session,
                raw_job=build_raw_job(),
                provider=provider,
                external_id=(
                    "invalid-telemetry-test"
                ),
            )

        assert session.scalar(
            select(func.count()).select_from(
                Source
            )
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

        session.rollback()