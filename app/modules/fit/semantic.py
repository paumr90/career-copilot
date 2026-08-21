from app.domain.enums import (
    RequirementCategory,
    RequirementPriority,
)
from app.domain.rules.semantic_assessment import (
    SemanticAssessmentPolicy,
)
from app.modules.fit.projection import (
    SemanticEvidenceProjector,
)
from app.modules.fit.schemas import (
    EvidenceRankingResult,
    SemanticAssessmentEvidence,
    SemanticAssessmentRequest,
    SemanticAssessmentRequirement,
)
from app.modules.opportunities.models import (
    JobRequirement,
)


class SemanticAssessmentRequestBuilder:
    def __init__(
        self,
        policy: SemanticAssessmentPolicy | None = None,
        projector: SemanticEvidenceProjector | None = None,
    ) -> None:
        self.policy = (
            policy or SemanticAssessmentPolicy()
        )

        self.projector = (
            projector
            or SemanticEvidenceProjector()
        )

    def build(
        self,
        *,
        requirement: JobRequirement,
        ranking_result: EvidenceRankingResult,
    ) -> SemanticAssessmentRequest:
        if (
            requirement.requirement_key
            != ranking_result.requirement_key
        ):
            raise ValueError(
                "Semantic assessment requirement_key "
                "must match the ranking result."
            )

        requirement_category = (
            RequirementCategory(
                requirement.category
            )
        )

        if (
            requirement_category
            != ranking_result.requirement_category
        ):
            raise ValueError(
                "Semantic assessment requirement "
                "category must match the ranking "
                "result category."
            )

        semantic_requirement = (
            SemanticAssessmentRequirement(
                requirement_key=(
                    requirement.requirement_key
                ),
                description=requirement.description,
                priority=RequirementPriority(
                    requirement.priority
                ),
                category=requirement_category,
                blocking=requirement.blocking,
                evidence_text=(
                    requirement.evidence_text
                ),
            )
        )

        ranked_evidence = [
            SemanticAssessmentEvidence(
                profile_fact_id=(
                    ranked.candidate.profile_fact_id
                ),
                fact_type=(
                    ranked.candidate.fact_type
                ),
                tier=ranked.candidate.tier,
                subject=(
                    ranked.candidate.subject
                ),
                value_json=(
                    ranked.candidate.value_json
                ),
                relevance_score=(
                    ranked.relevance_score
                ),
                matched_terms=(
                    ranked.matched_terms
                ),
            )
            for ranked
            in ranking_result.ranked_candidates[
                : self.policy.maximum_ranked_evidence
            ]
        ]

        unprojected_request = (
            SemanticAssessmentRequest(
                semantic_rule_version=(
                    self.policy.version
                ),
                retrieval_rule_version=(
                    ranking_result
                    .retrieval_rule_version
                ),
                ranking_rule_version=(
                    ranking_result
                    .ranking_rule_version
                ),
                requirement=semantic_requirement,
                ranked_evidence=ranked_evidence,
            )
        )

        return self.projector.project_request(
            request=unprojected_request
        )