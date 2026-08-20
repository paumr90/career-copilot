import uuid

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import MatchStatus


class ProfileEvidenceReference(BaseModel):
    profile_fact_id: uuid.UUID

    note: str | None = Field(
        default=None,
        max_length=1000,
    )


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

    @model_validator(mode="after")
    def validate_evidence_consistency(
        self,
    ) -> "RequirementAssessment":
        if self.match_status in {
            MatchStatus.MATCH,
            MatchStatus.PARTIAL_MATCH,
            MatchStatus.GAP,
        } and not self.evidence:
            raise ValueError(
                f"{self.match_status.value} requires at least "
                "one Career Master evidence reference."
            )

        if (
            self.match_status == MatchStatus.UNKNOWN
            and self.evidence
        ):
            raise ValueError(
                "UNKNOWN cannot contain Career Master evidence. "
                "If relevant evidence exists, classify the requirement "
                "as MATCH, PARTIAL_MATCH or GAP."
            )

        return self