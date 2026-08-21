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
from app.modules.opportunities.models import (
    JobRequirement,
    Opportunity,
)
from app.modules.opportunities.providers import (
    JDExtractionProvider,
)
from app.modules.opportunities.schemas import (
    JDExtractionProposal,
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
        opportunity_service: OpportunityService | None = None,
        audit_service: RuleEvaluationService | None = None,
    ) -> None:
        self.validator = (
            validator
            or JDExtractionValidator()
        )

        self.opportunity_service = (
            opportunity_service
            or OpportunityService()
        )

        self.audit_service = (
            audit_service
            or RuleEvaluationService()
        )

    def _build_audit_input(
        self,
        *,
        source: Source,
        opportunity: Opportunity,
        raw_job: RawJobDescriptionInput,
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
        proposal = provider.extract(
            raw_job=raw_job
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