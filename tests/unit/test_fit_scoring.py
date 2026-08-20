import uuid

import pytest
from pydantic import ValidationError

from app.domain.enums import FitRecommendation
from app.domain.rules.fit_scoring import FitScoringPolicy
from app.modules.fit.schemas import (
    FitScoringRequirement,
    ProfileEvidenceReference,
    RequirementAssessment,
)


def build_evidence() -> ProfileEvidenceReference:
    return ProfileEvidenceReference(
        profile_fact_id=uuid.uuid4(),
        note="Confirmed Career Master evidence.",
    )


def build_requirement(
    requirement_key: str,
    priority: str,
    match_status: str,
    *,
    blocking: bool = False,
) -> FitScoringRequirement:
    evidence = []

    if match_status != "UNKNOWN":
        evidence = [build_evidence()]

    assessment = RequirementAssessment(
        requirement_key=requirement_key,
        match_status=match_status,
        evidence=evidence,
        rationale="Test assessment rationale.",
    )

    return FitScoringRequirement(
        requirement_key=requirement_key,
        priority=priority,
        blocking=blocking,
        assessment=assessment,
    )


def test_full_match_recommends_apply() -> None:
    policy = FitScoringPolicy()

    requirements = [
        build_requirement(
            "project_management",
            "MUST_HAVE",
            "MATCH",
        ),
        build_requirement(
            "digital_transformation",
            "NICE_TO_HAVE",
            "MATCH",
        ),
    ]

    result = policy.evaluate(requirements)

    assert result.score == 100.0
    assert result.coverage_percent == 100.0
    assert result.recommendation == FitRecommendation.APPLY
    assert result.rule_version == "0.1"


def test_score_below_threshold_recommends_no_apply() -> None:
    policy = FitScoringPolicy()

    requirements = [
        build_requirement(
            "core_experience",
            "MUST_HAVE",
            "PARTIAL_MATCH",
        ),
        build_requirement(
            "secondary_skill",
            "NICE_TO_HAVE",
            "GAP",
        ),
    ]

    result = policy.evaluate(requirements)

    assert result.score == 35.71
    assert result.recommendation == FitRecommendation.NO_APPLY


def test_blocking_gap_overrides_high_score() -> None:
    policy = FitScoringPolicy()

    requirements = [
        build_requirement(
            "blocking_requirement",
            "MUST_HAVE",
            "GAP",
            blocking=True,
        ),
        build_requirement(
            "must_match_1",
            "MUST_HAVE",
            "MATCH",
        ),
        build_requirement(
            "must_match_2",
            "MUST_HAVE",
            "MATCH",
        ),
        build_requirement(
            "must_match_3",
            "MUST_HAVE",
            "MATCH",
        ),
        build_requirement(
            "must_match_4",
            "MUST_HAVE",
            "MATCH",
        ),
        build_requirement(
            "must_match_5",
            "MUST_HAVE",
            "MATCH",
        ),
    ]

    result = policy.evaluate(requirements)

    assert result.score == 83.33
    assert result.recommendation == FitRecommendation.NO_APPLY
    assert result.blocking_gap_keys == [
        "blocking_requirement"
    ]


def test_blocking_partial_match_requires_review() -> None:
    policy = FitScoringPolicy()

    requirements = [
        build_requirement(
            "required_experience",
            "MUST_HAVE",
            "PARTIAL_MATCH",
            blocking=True,
        ),
        build_requirement(
            "additional_skill",
            "NICE_TO_HAVE",
            "MATCH",
        ),
    ]

    result = policy.evaluate(requirements)

    assert result.recommendation == FitRecommendation.REVIEW
    assert result.review_required_keys == [
        "required_experience"
    ]


def test_unknown_must_have_requires_review() -> None:
    policy = FitScoringPolicy()

    requirements = [
        build_requirement(
            "unknown_must_have",
            "MUST_HAVE",
            "UNKNOWN",
        ),
        build_requirement(
            "known_nice_to_have",
            "NICE_TO_HAVE",
            "MATCH",
        ),
    ]

    result = policy.evaluate(requirements)

    assert result.score == 100.0
    assert result.coverage_percent == 28.57
    assert result.recommendation == FitRecommendation.REVIEW
    assert result.review_required_keys == [
        "unknown_must_have"
    ]


def test_unknown_nice_to_have_does_not_reduce_score() -> None:
    policy = FitScoringPolicy()

    requirements = [
        build_requirement(
            "known_must_have",
            "MUST_HAVE",
            "MATCH",
        ),
        build_requirement(
            "unknown_nice_to_have",
            "NICE_TO_HAVE",
            "UNKNOWN",
        ),
    ]

    result = policy.evaluate(requirements)

    assert result.score == 100.0
    assert result.coverage_percent == 71.43
    assert result.recommendation == FitRecommendation.APPLY


def test_all_unknown_requirements_require_review() -> None:
    policy = FitScoringPolicy()

    requirements = [
        build_requirement(
            "unknown_secondary",
            "SECONDARY",
            "UNKNOWN",
        )
    ]

    result = policy.evaluate(requirements)

    assert result.score == 0.0
    assert result.coverage_percent == 0.0
    assert result.recommendation == FitRecommendation.REVIEW


def test_empty_requirement_list_requires_review() -> None:
    policy = FitScoringPolicy()

    result = policy.evaluate([])

    assert result.score == 0.0
    assert result.total_weight == 0.0
    assert result.known_weight == 0.0
    assert result.recommendation == FitRecommendation.REVIEW


def test_blocking_non_must_have_is_rejected() -> None:
    assessment = RequirementAssessment(
        requirement_key="optional_skill",
        match_status="MATCH",
        evidence=[build_evidence()],
        rationale="Evidence supports the optional skill.",
    )

    with pytest.raises(
        ValidationError,
        match=(
            "blocking=True is only valid for "
            "MUST_HAVE requirements"
        ),
    ):
        FitScoringRequirement(
            requirement_key="optional_skill",
            priority="NICE_TO_HAVE",
            blocking=True,
            assessment=assessment,
        )