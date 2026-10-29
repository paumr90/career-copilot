import uuid

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)

from app.domain.enums import (
    EvidenceTier,
    FitRecommendation,
    GapBasis,
    MatchStatus,
    ProfileFactType,
    RequirementCategory,
    RequirementPriority,
)


class ProfileEvidenceReference(BaseModel):
    profile_fact_id: uuid.UUID

    note: str | None = Field(
        default=None,
        max_length=1000,
    )


class RequirementAssessmentProposal(BaseModel):
    requirement_key: str = Field(
        min_length=1,
        max_length=150,
    )

    proposed_status: MatchStatus

    evidence: list[ProfileEvidenceReference] = Field(
        default_factory=list,
    )

    rationale: str = Field(
        min_length=1,
        max_length=4000,
    )

    gap_basis: GapBasis | None = None

    @model_validator(mode="after")
    def validate_unique_evidence(
        self,
    ) -> RequirementAssessmentProposal:
        evidence_ids = [evidence.profile_fact_id for evidence in self.evidence]

        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError(
                "RequirementAssessmentProposal cannot cite duplicate profile_fact_id values."
            )

        return self


class RequirementAssessment(BaseModel):
    requirement_key: str = Field(
        min_length=1,
        max_length=150,
    )

    match_status: MatchStatus

    evidence: list[ProfileEvidenceReference] = Field(
        default_factory=list,
    )

    rationale: str = Field(
        min_length=1,
        max_length=4000,
    )

    gap_basis: GapBasis | None = None

    @model_validator(mode="after")
    def validate_evidence_consistency(
        self,
    ) -> RequirementAssessment:
        if (
            self.match_status
            in {
                MatchStatus.MATCH,
                MatchStatus.PARTIAL_MATCH,
                MatchStatus.GAP,
            }
            and not self.evidence
        ):
            raise ValueError(
                f"{self.match_status.value} requires at least one Career Master evidence reference."
            )

        if self.match_status == MatchStatus.UNKNOWN and self.evidence:
            raise ValueError(
                "UNKNOWN cannot contain Career Master evidence. "
                "If relevant evidence exists, classify the requirement "
                "as MATCH, PARTIAL_MATCH or GAP."
            )

        return self


class FitScoringRequirement(BaseModel):
    requirement_key: str = Field(
        min_length=1,
        max_length=150,
    )

    priority: RequirementPriority

    blocking: bool = False

    assessment: RequirementAssessment

    @model_validator(mode="after")
    def validate_requirement_consistency(
        self,
    ) -> FitScoringRequirement:
        if self.requirement_key != self.assessment.requirement_key:
            raise ValueError(
                "FitScoringRequirement requirement_key must match "
                "RequirementAssessment requirement_key."
            )

        if self.blocking and self.priority != RequirementPriority.MUST_HAVE:
            raise ValueError("blocking=True is only valid for MUST_HAVE requirements.")

        return self


class FitResult(BaseModel):
    score: float = Field(
        ge=0.0,
        le=100.0,
    )

    recommendation: FitRecommendation

    rule_version: str

    known_weight: float = Field(
        ge=0.0,
    )

    total_weight: float = Field(
        ge=0.0,
    )

    coverage_percent: float = Field(
        ge=0.0,
        le=100.0,
    )

    blocking_gap_keys: list[str] = Field(
        default_factory=list,
    )

    review_required_keys: list[str] = Field(
        default_factory=list,
    )


class CareerEvidenceCandidate(BaseModel):
    profile_fact_id: uuid.UUID

    fact_type: ProfileFactType

    subject: str = Field(
        min_length=1,
        max_length=255,
    )

    value_json: dict

    tier: EvidenceTier


class EvidenceCandidateSet(BaseModel):
    requirement_key: str = Field(
        min_length=1,
        max_length=150,
    )

    requirement_category: RequirementCategory

    retrieval_rule_version: str

    primary_candidates: list[CareerEvidenceCandidate] = Field(
        default_factory=list,
    )

    supporting_candidates: list[CareerEvidenceCandidate] = Field(
        default_factory=list,
    )


class RankedEvidenceCandidate(BaseModel):
    candidate: CareerEvidenceCandidate

    relevance_score: float = Field(
        ge=0.0,
    )

    matched_terms: list[str] = Field(
        default_factory=list,
    )

    exact_phrase_matches: list[str] = Field(
        default_factory=list,
    )


class EvidenceRankingResult(BaseModel):
    requirement_key: str = Field(
        min_length=1,
        max_length=150,
    )

    requirement_category: RequirementCategory

    retrieval_rule_version: str

    ranking_rule_version: str

    ranking_method: str

    total_candidate_count: int = Field(
        ge=0,
    )

    ranked_candidates: list[RankedEvidenceCandidate] = Field(
        default_factory=list,
    )

    used_fallback: bool = False


class SemanticAssessmentRequirement(BaseModel):
    requirement_key: str = Field(
        min_length=1,
        max_length=150,
    )

    description: str = Field(
        min_length=1,
        max_length=2000,
    )

    priority: RequirementPriority

    category: RequirementCategory

    blocking: bool = False

    source_excerpts: list[str] = Field(default_factory=list)

    evidence_text: str | None = Field(
        default=None,
        max_length=4000,
    )


class SemanticAssessmentEvidence(BaseModel):
    profile_fact_id: uuid.UUID

    fact_type: ProfileFactType

    tier: EvidenceTier

    subject: str = Field(
        min_length=1,
        max_length=255,
    )

    value_json: dict

    relevance_score: float = Field(
        ge=0.0,
    )

    matched_terms: list[str] = Field(
        default_factory=list,
    )


class SemanticAssessmentRequest(BaseModel):
    semantic_rule_version: str

    retrieval_rule_version: str

    ranking_rule_version: str

    requirement: SemanticAssessmentRequirement

    ranked_evidence: list[SemanticAssessmentEvidence] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def validate_unique_evidence(
        self,
    ) -> SemanticAssessmentRequest:
        evidence_ids = [evidence.profile_fact_id for evidence in self.ranked_evidence]

        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError(
                "SemanticAssessmentRequest cannot contain duplicate profile_fact_id values."
            )

        return self
