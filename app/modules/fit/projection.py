from copy import deepcopy

from app.domain.enums import (
    ProfileFactType,
    RequirementCategory,
)
from app.domain.rules.semantic_evidence_projection import (
    SemanticEvidenceProjectionPolicy,
)
from app.modules.fit.schemas import (
    SemanticAssessmentEvidence,
    SemanticAssessmentRequest,
)


class SemanticEvidenceProjector:
    """
    Applies governed data minimization to Career
    Master evidence before it may leave the local
    application boundary.

    The projector never decides relevance, evidence
    tier or requirement fit. It only removes
    value_json fields that are not explicitly
    allowlisted for the current requirement
    category and ProfileFactType.
    """

    def __init__(
        self,
        policy: (
            SemanticEvidenceProjectionPolicy | None
        ) = None,
    ) -> None:
        self.policy = (
            policy
            or SemanticEvidenceProjectionPolicy()
        )

    @property
    def version(self) -> str:
        return self.policy.version

    def project_evidence(
        self,
        *,
        category: RequirementCategory,
        evidence: SemanticAssessmentEvidence,
    ) -> SemanticAssessmentEvidence:
        allowed_fields = set(
            self.policy.allowed_fields(
                category=category,
                fact_type=evidence.fact_type,
            )
        )

        projected_value_json = {
            key: deepcopy(value)
            for key, value
            in evidence.value_json.items()
            if key in allowed_fields
        }

        return SemanticAssessmentEvidence(
            profile_fact_id=(
                evidence.profile_fact_id
            ),
            fact_type=evidence.fact_type,
            tier=evidence.tier,
            subject=evidence.subject,
            value_json=projected_value_json,
            relevance_score=(
                evidence.relevance_score
            ),
            matched_terms=deepcopy(
                evidence.matched_terms
            ),
        )

    def project_request(
        self,
        *,
        request: SemanticAssessmentRequest,
    ) -> SemanticAssessmentRequest:
        category = (
            request.requirement.category
        )

        projected_evidence = [
            self.project_evidence(
                category=category,
                evidence=evidence,
            )
            for evidence
            in request.ranked_evidence
        ]

        return SemanticAssessmentRequest(
            semantic_rule_version=(
                request.semantic_rule_version
            ),
            retrieval_rule_version=(
                request.retrieval_rule_version
            ),
            ranking_rule_version=(
                request.ranking_rule_version
            ),
            requirement=(
                request.requirement.model_copy(
                    deep=True
                )
            ),
            ranked_evidence=(
                projected_evidence
            ),
        )