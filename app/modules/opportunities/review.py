"""Explicit human review of extracted requirements, without mutating the JD."""

import hashlib
import json
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import RequirementCategory, RequirementPriority
from app.modules.opportunities.extraction import JDExtractionValidator
from app.modules.opportunities.schemas import JobDescriptionInput


class RequirementAmendment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement_key: str
    priority: RequirementPriority | None = None
    category: RequirementCategory | None = None
    blocking: bool | None = None
    description: str | None = None
    evidence_text: str | None = None
    reason: str = Field(min_length=1)


class RequirementReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job: JobDescriptionInput
    reviewer: str = Field(min_length=1)
    reviewed_keys: list[str]
    amendments: list[RequirementAmendment] = Field(default_factory=list)
    note: str = ""


class ReviewedJobDescription(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_hash: str
    reviewer: str
    reviewed_at: datetime
    original: JobDescriptionInput
    reviewed: JobDescriptionInput
    amendments: list[RequirementAmendment]
    note: str


class RequirementReviewService:
    @staticmethod
    def digest(payload: dict) -> str:
        content = dict(payload)
        content.pop("review_hash", None)
        # Optional correction fields preserve hashes of older classification-only reviews.
        content["amendments"] = [
            {
                key: value
                for key, value in amendment.items()
                if key not in {"description", "evidence_text"} or value is not None
            }
            for amendment in content.get("amendments", [])
        ]
        return hashlib.sha256(
            json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()

    def review(self, request: RequirementReviewRequest) -> ReviewedJobDescription:
        if not request.reviewer.strip():
            raise ValueError("Reviewer cannot be blank.")
        original = JDExtractionValidator().validate(request.job.model_copy(deep=True))
        keys = {item.requirement_key for item in original.requirements}
        if not keys:
            raise ValueError("Cannot approve an empty requirement list.")
        if len(request.reviewed_keys) != len(keys) or set(request.reviewed_keys) != keys:
            raise ValueError(
                "Every extracted requirement must be explicitly reviewed exactly once."
            )
        changes = {item.requirement_key: item for item in request.amendments}
        if len(changes) != len(request.amendments) or set(changes) - keys:
            raise ValueError("Amendments must identify unique existing requirements.")
        requirements = []
        for requirement in original.requirements:
            amendment = changes.get(requirement.requirement_key)
            values = requirement.model_dump(mode="json")
            if amendment:
                if not amendment.reason.strip():
                    raise ValueError("Each amendment requires a reason.")
                values.update(
                    amendment.model_dump(
                        mode="json",
                        exclude_none=True,
                        exclude={"requirement_key", "reason"},
                    )
                )
            requirements.append(values)
        values = original.model_dump(mode="json")
        values["requirements"] = requirements
        reviewed = JDExtractionValidator().validate(JobDescriptionInput.model_validate(values))
        payload = {
            "reviewer": request.reviewer.strip(),
            "reviewed_at": datetime.now(UTC).isoformat(),
            "original": original.model_dump(mode="json"),
            "reviewed": reviewed.model_dump(mode="json"),
            "amendments": [item.model_dump(mode="json") for item in request.amendments],
            "note": request.note,
        }
        snapshot = ReviewedJobDescription(review_hash="", **payload)
        return snapshot.model_copy(
            update={
                "review_hash": self.digest(snapshot.model_dump(mode="json")),
            }
        )

    def verify(self, review: ReviewedJobDescription) -> None:
        payload = review.model_dump(mode="json")
        if self.digest(payload) != review.review_hash:
            raise ValueError("Reviewed snapshot hash does not match its contents.")
        # Reconstruct allowed changes to reject altered descriptions or added requirements.
        replay = self.review(
            RequirementReviewRequest(
                job=review.original,
                reviewer=review.reviewer,
                reviewed_keys=[item.requirement_key for item in review.original.requirements],
                amendments=review.amendments,
                note=review.note,
            )
        )
        if replay.reviewed != review.reviewed:
            raise ValueError("Reviewed requirements differ from the approved amendments.")
