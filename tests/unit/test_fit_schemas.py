import uuid

import pytest
from pydantic import ValidationError

from app.modules.fit.schemas import (
    ProfileEvidenceReference,
    RequirementAssessment,
)


def build_evidence() -> ProfileEvidenceReference:
    return ProfileEvidenceReference(
        profile_fact_id=uuid.uuid4(),
        note="Confirmed Career Master evidence.",
    )


def test_match_requires_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match="MATCH requires at least one Career Master evidence reference",
    ):
        RequirementAssessment(
            requirement_key="project_management",
            match_status="MATCH",
            evidence=[],
            rationale="Profile matches requirement.",
        )


def test_partial_match_requires_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "PARTIAL_MATCH requires at least one "
            "Career Master evidence reference"
        ),
    ):
        RequirementAssessment(
            requirement_key="ai_transformation",
            match_status="PARTIAL_MATCH",
            evidence=[],
            rationale="Profile partially matches requirement.",
        )


def test_gap_requires_evidence() -> None:
    with pytest.raises(
        ValidationError,
        match="GAP requires at least one Career Master evidence reference",
    ):
        RequirementAssessment(
            requirement_key="required_certification",
            match_status="GAP",
            evidence=[],
            rationale=(
                "Career Master evidence confirms that the "
                "required qualification is not met."
            ),
        )


def test_unknown_without_evidence_is_valid() -> None:
    assessment = RequirementAssessment(
        requirement_key="aws",
        match_status="UNKNOWN",
        evidence=[],
        rationale="Career Master contains insufficient evidence.",
    )

    assert assessment.match_status.value == "UNKNOWN"
    assert assessment.evidence == []


def test_unknown_with_evidence_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="UNKNOWN cannot contain Career Master evidence",
    ):
        RequirementAssessment(
            requirement_key="aws",
            match_status="UNKNOWN",
            evidence=[build_evidence()],
            rationale="Evidence exists but status was marked unknown.",
        )


def test_match_with_evidence_is_valid() -> None:
    evidence = build_evidence()

    assessment = RequirementAssessment(
        requirement_key="project_management",
        match_status="MATCH",
        evidence=[evidence],
        rationale=(
            "Confirmed project-management evidence supports "
            "the requirement."
        ),
    )

    assert assessment.match_status.value == "MATCH"
    assert len(assessment.evidence) == 1
    assert (
        assessment.evidence[0].profile_fact_id
        == evidence.profile_fact_id
    )