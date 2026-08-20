from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import (
    EvidenceState,
    EvidenceTier,
    ProfileFactType,
    RequirementCategory,
    SourceType,
)
from app.domain.rules.evidence_retrieval import (
    EvidenceRetrievalPolicy,
)
from app.modules.fit.schemas import (
    CareerEvidenceCandidate,
    EvidenceCandidateSet,
)
from app.modules.governance.models import (
    ProfileFact,
    Source,
)
from app.modules.opportunities.models import (
    JobRequirement,
)


class CareerEvidenceRetriever:
    def __init__(
        self,
        policy: EvidenceRetrievalPolicy | None = None,
    ) -> None:
        self.policy = (
            policy or EvidenceRetrievalPolicy()
        )

    def _load_candidates(
        self,
        session: Session,
        *,
        fact_types: list[ProfileFactType],
        tier: EvidenceTier,
    ) -> list[CareerEvidenceCandidate]:
        if not fact_types:
            return []

        fact_type_values = [
            fact_type.value
            for fact_type in fact_types
        ]

        facts = session.scalars(
            select(ProfileFact)
            .join(
                Source,
                ProfileFact.source_id
                == Source.source_id,
            )
            .where(
                ProfileFact.fact_type.in_(
                    fact_type_values
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
            .order_by(
                ProfileFact.fact_type,
                ProfileFact.subject,
                ProfileFact.fact_id,
            )
        ).all()

        return [
            CareerEvidenceCandidate(
                profile_fact_id=fact.fact_id,
                fact_type=ProfileFactType(
                    fact.fact_type
                ),
                subject=fact.subject,
                value_json=fact.value_json,
                tier=tier,
            )
            for fact in facts
        ]

    def retrieve_for_requirement(
        self,
        session: Session,
        requirement: JobRequirement,
    ) -> EvidenceCandidateSet:
        category = RequirementCategory(
            requirement.category
        )

        primary_fact_types = (
            self.policy.get_primary_fact_types(
                category
            )
        )

        supporting_fact_types = (
            self.policy.get_supporting_fact_types(
                category
            )
        )

        primary_candidates = (
            self._load_candidates(
                session,
                fact_types=primary_fact_types,
                tier=EvidenceTier.PRIMARY,
            )
        )

        supporting_candidates = (
            self._load_candidates(
                session,
                fact_types=supporting_fact_types,
                tier=EvidenceTier.SUPPORTING,
            )
        )

        return EvidenceCandidateSet(
            requirement_key=(
                requirement.requirement_key
            ),
            requirement_category=category,
            retrieval_rule_version=(
                self.policy.version
            ),
            primary_candidates=(
                primary_candidates
            ),
            supporting_candidates=(
                supporting_candidates
            ),
        )