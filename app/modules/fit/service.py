import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import EvidenceState, SourceType
from app.domain.rules.fit_scoring import FitScoringPolicy
from app.modules.audit.models import RuleEvaluation
from app.modules.audit.service import RuleEvaluationService
from app.modules.fit.schemas import (
    FitResult,
    FitScoringRequirement,
)
from app.modules.governance.models import (
    ProfileFact,
    Source,
)


class FitEvaluationService:
    def __init__(
        self,
        policy: FitScoringPolicy | None = None,
        audit_service: RuleEvaluationService | None = None,
    ) -> None:
        self.policy = policy or FitScoringPolicy()
        self.audit_service = (
            audit_service or RuleEvaluationService()
        )

    def _validate_profile_evidence(
        self,
        session: Session,
        requirements: list[FitScoringRequirement],
    ) -> None:
        evidence_ids = {
            evidence.profile_fact_id
            for requirement in requirements
            for evidence in requirement.assessment.evidence
        }

        if not evidence_ids:
            return

        valid_evidence_ids = set(
            session.scalars(
                select(ProfileFact.fact_id)
                .join(
                    Source,
                    ProfileFact.source_id
                    == Source.source_id,
                )
                .where(
                    ProfileFact.fact_id.in_(evidence_ids),
                    ProfileFact.evidence_state
                    == EvidenceState.CONFIRMED.value,
                    ProfileFact.superseded_by.is_(None),
                    Source.source_type
                    == SourceType.PROFILE.value,
                    Source.authority_level
                    == "CANONICAL_PROFILE",
                    Source.immutable.is_(True),
                )
            ).all()
        )

        invalid_evidence_ids = (
            evidence_ids - valid_evidence_ids
        )

        if invalid_evidence_ids:
            invalid_values = sorted(
                str(evidence_id)
                for evidence_id
                in invalid_evidence_ids
            )

            raise ValueError(
                "Fit evidence must reference active, confirmed, "
                "canonical Career Master facts. Invalid "
                f"profile_fact_id values: {invalid_values}"
            )

    def evaluate_and_record(
        self,
        session: Session,
        *,
        opportunity_id: uuid.UUID,
        requirements: list[FitScoringRequirement],
    ) -> tuple[FitResult, RuleEvaluation]:
        self._validate_profile_evidence(
            session=session,
            requirements=requirements,
        )

        input_payload = {
            "requirements": [
                requirement.model_dump(mode="json")
                for requirement in requirements
            ],
            "rules_snapshot": self.policy.config,
        }

        result = self.policy.evaluate(requirements)

        result_json = result.model_dump(mode="json")

        evaluation = self.audit_service.record(
            session,
            rule_set="fit_scoring",
            ruleset_version=self.policy.version,
            input_payload=input_payload,
            result_json=result_json,
            entity_type="opportunity",
            entity_id=opportunity_id,
        )

        return result, evaluation