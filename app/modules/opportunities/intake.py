from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.audit.models import (
    RuleEvaluation,
)
from app.modules.audit.service import (
    RuleEvaluationService,
)
from app.modules.governance.models import Source
from app.modules.opportunities.extraction import (
    JDExtractionValidator,
)
from app.modules.opportunities.extraction_request import (
    JDExtractionRequestBuilder,
)
from app.modules.opportunities.models import (
    JobRequirement,
    Opportunity,
)
from app.modules.opportunities.providers import (
    JDExtractionProvider,
    TelemetryJDExtractionProvider,
)
from app.modules.opportunities.schemas import (
    JDExtractionProposal,
    JDExtractionProviderResult,
    JDExtractionRequest,
    JDExtractionTelemetry,
    JobDescriptionInput,
    RawJobDescriptionInput,
)
from app.modules.opportunities.service import (
    OpportunityService,
)


class JDIntakeService:
    def __init__(
        self,
        *,
        validator: JDExtractionValidator | None = None,
        request_builder: (
            JDExtractionRequestBuilder | None
        ) = None,
        opportunity_service: OpportunityService | None = None,
        audit_service: RuleEvaluationService | None = None,
    ) -> None:
        self.validator = (
            validator
            or JDExtractionValidator()
        )

        self.request_builder = (
            request_builder
            or JDExtractionRequestBuilder(
                policy=self.validator.policy
            )
        )

        self.opportunity_service = (
            opportunity_service
            or OpportunityService()
        )

        self.audit_service = (
            audit_service
            or RuleEvaluationService()
        )

    def _extract_with_telemetry(
        self,
        *,
        provider: JDExtractionProvider,
        request: JDExtractionRequest,
    ) -> JDExtractionProviderResult:
        if isinstance(
            provider,
            TelemetryJDExtractionProvider,
        ):
            result = (
                provider.extract_with_telemetry(
                    request=request
                )
            )

            if (
                result.telemetry.provider_name
                != provider.provider_name
            ):
                raise ValueError(
                    "JD extraction telemetry "
                    "provider_name does not match "
                    "the provider identity."
                )

            if (
                result.telemetry.provider_version
                != provider.provider_version
            ):
                raise ValueError(
                    "JD extraction telemetry "
                    "provider_version does not match "
                    "the provider identity."
                )

            return result.model_copy(
                deep=True
            )

        proposal = provider.extract(
            request=request
        )

        return JDExtractionProviderResult(
            proposal=proposal.model_copy(
                deep=True
            ),
            telemetry=JDExtractionTelemetry(
                provider_name=(
                    provider.provider_name
                ),
                provider_version=(
                    provider.provider_version
                ),
            ),
        )

    def _build_audit_input(
        self,
        *,
        source: Source,
        opportunity: Opportunity,
        raw_job: RawJobDescriptionInput,
        request: JDExtractionRequest,
        provider: JDExtractionProvider,
        proposal: JDExtractionProposal,
    ) -> dict:
        return {
            "source_id": str(
                source.source_id
            ),
            "opportunity_id": str(
                opportunity.opportunity_id
            ),
            "jd_snapshot_hash": (
                source.snapshot_hash
            ),
            "source_uri": (
                raw_job.source_url
            ),
            "extraction_request": {
                "extraction_rule_version": (
                    request.extraction_rule_version
                ),
                "company": request.company,
                "role_title": request.role_title,
                "location": request.location,
            },
            "provider_origin": {
                "provider_name": (
                    provider.provider_name
                ),
                "provider_version": (
                    provider.provider_version
                ),
            },
            "proposal": proposal.model_dump(
                mode="json"
            ),
            "rules_snapshot": {
                "jd_extraction": (
                    self.validator.policy.config
                ),
            },
        }

    def create_from_provider(
        self,
        session: Session,
        *,
        raw_job: RawJobDescriptionInput,
        provider: JDExtractionProvider,
        external_id: str | None = None,
        captured_at: datetime | None = None,
    ) -> tuple[
        Source,
        Opportunity,
        list[JobRequirement],
        JDExtractionProposal,
        JobDescriptionInput,
        RuleEvaluation,
    ]:
        request = self.request_builder.build(
            raw_job=raw_job
        )

        provider_result = (
            self._extract_with_telemetry(
                provider=provider,
                request=request,
            )
        )

        proposal = (
            provider_result.proposal
        )

        validated_job_description = (
            self.validator.validate_proposal(
                raw_job=raw_job,
                proposal=proposal,
            )
        )

        (
            source,
            opportunity,
            requirements,
        ) = (
            self.opportunity_service
            .create_from_job_description(
                session=session,
                job_description=(
                    validated_job_description
                ),
                external_id=external_id,
                uri=raw_job.source_url,
                captured_at=captured_at,
            )
        )

        audit_input = self._build_audit_input(
            source=source,
            opportunity=opportunity,
            raw_job=raw_job,
            request=request,
            provider=provider,
            proposal=proposal,
        )

        extraction_evaluation = (
            self.audit_service.record(
                session,
                rule_set="jd_extraction",
                ruleset_version=(
                    self.validator.policy.version
                ),
                input_payload=audit_input,
                result_json={
                    "validated_requirements": [
                        requirement.model_dump(
                            mode="json"
                        )
                        for requirement
                        in validated_job_description
                        .requirements
                    ],
                    "requirements_count": len(
                        validated_job_description
                        .requirements
                    ),
                    "provider_telemetry": (
                        provider_result.telemetry
                        .model_dump(
                            mode="json"
                        )
                    ),
                },
                entity_type="opportunity",
                entity_id=(
                    opportunity.opportunity_id
                ),
            )
        )

        return (
            source,
            opportunity,
            requirements,
            proposal,
            validated_job_description,
            extraction_evaluation,
        )