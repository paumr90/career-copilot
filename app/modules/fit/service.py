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
    RequirementAssessment,
)
from app.modules.governance.models import (
    ProfileFact,
    Source,
)
from app.modules.opportunities.models import (
    JobRequirement,
    Opportunity,
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

    def _load_canonical_opportunity(
        self,
        session: Session,
        opportunity_id: uuid.UUID,
    ) -> tuple[
        Opportunity,
        Source,
        list[JobRequirement],
    ]:
        row = session.execute(
            select(
                Opportunity,
                Source,
            )
            .join(
                Source,
                Opportunity.jd_source_id
                == Source.source_id,
            )
            .where(
                Opportunity.opportunity_id
                == opportunity_id,
                Source.source_type
                == SourceType.JD.value,
                Source.authority_level
                == "CANONICAL_JD",
                Source.immutable.is_(True),
            )
        ).one_or_none()

        if row is None:
            raise ValueError(
                "Fit evaluation requires an existing "
                "Opportunity backed by an immutable "
                "canonical JD Source."
            )

        opportunity, source = row

        job_requirements = list(
            session.scalars(
                select(JobRequirement)
                .where(
                    JobRequirement.opportunity_id
                    == opportunity_id
                )
                .order_by(
                    JobRequirement.requirement_key
                )
            ).all()
        )

        return (
            opportunity,
            source,
            job_requirements,
        )

    def _build_scoring_requirements(
        self,
        job_requirements: list[JobRequirement],
        assessments: list[RequirementAssessment],
    ) -> list[FitScoringRequirement]:
        assessment_keys = [
            assessment.requirement_key
            for assessment in assessments
        ]

        if len(assessment_keys) != len(
            set(assessment_keys)
        ):
            raise ValueError(
                "Duplicate requirement assessments "
                "are not allowed."
            )

        canonical_keys = {
            requirement.requirement_key
            for requirement in job_requirements
        }

        provided_keys = set(assessment_keys)

        if canonical_keys != provided_keys:
            missing_keys = sorted(
                canonical_keys - provided_keys
            )

            extra_keys = sorted(
                provided_keys - canonical_keys
            )

            raise ValueError(
                "Assessment keys must exactly match "
                "the canonical JobRequirements. "
                f"Missing: {missing_keys}. "
                f"Extra: {extra_keys}."
            )

        assessment_by_key = {
            assessment.requirement_key: assessment
            for assessment in assessments
        }

        return [
            FitScoringRequirement(
                requirement_key=(
                    requirement.requirement_key
                ),
                priority=requirement.priority,
                blocking=requirement.blocking,
                assessment=assessment_by_key[
                    requirement.requirement_key
                ],
            )
            for requirement in job_requirements
        ]

    def _validate_profile_evidence(
        self,
        session: Session,
        requirements: list[FitScoringRequirement],
    ) -> None:
        evidence_ids = {
            evidence.profile_fact_id
            for requirement in requirements
            for evidence
            in requirement.assessment.evidence
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
                    ProfileFact.fact_id.in_(
                        evidence_ids
                    ),
                    ProfileFact.evidence_state
                    == EvidenceState.CONFIRMED.value,
                    ProfileFact.superseded_by.is_(
                        None
                    ),
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
                "Fit evidence must reference active, "
                "confirmed, canonical Career Master "
                "facts. Invalid profile_fact_id "
                f"values: {invalid_values}"
            )

    def evaluate_opportunity_and_record(
        self,
        session: Session,
        *,
        opportunity_id: uuid.UUID,
        assessments: list[RequirementAssessment],
    ) -> tuple[FitResult, RuleEvaluation]:
        (
            opportunity,
            source,
            job_requirements,
        ) = self._load_canonical_opportunity(
            session=session,
            opportunity_id=opportunity_id,
        )

        scoring_requirements = (
            self._build_scoring_requirements(
                job_requirements=job_requirements,
                assessments=assessments,
            )
        )

        self._validate_profile_evidence(
            session=session,
            requirements=scoring_requirements,
        )

        input_payload = {
            "opportunity": {
                "opportunity_id": str(
                    opportunity.opportunity_id
                ),
                "jd_source_id": str(
                    source.source_id
                ),
                "jd_snapshot_hash": (
                    source.snapshot_hash
                ),
            },
            "requirements": [
                requirement.model_dump(
                    mode="json"
                )
                for requirement
                in scoring_requirements
            ],
            "rules_snapshot": self.policy.config,
        }

        result = self.policy.evaluate(
            scoring_requirements
        )

        result_json = result.model_dump(
            mode="json"
        )

        evaluation = self.audit_service.record(
            session,
            rule_set="fit_scoring",
            ruleset_version=self.policy.version,
            input_payload=input_payload,
            result_json=result_json,
            entity_type="opportunity",
            entity_id=opportunity.opportunity_id,
        )

        return result, evaluation