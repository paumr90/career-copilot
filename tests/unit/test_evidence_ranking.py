import uuid

import pytest

from app.domain.enums import (
    EvidenceTier,
    ProfileFactType,
    RequirementCategory,
)
from app.modules.fit.ranking import (
    EvidenceRelevanceRanker,
)
from app.modules.fit.schemas import (
    CareerEvidenceCandidate,
    EvidenceCandidateSet,
)
from app.modules.opportunities.models import (
    JobRequirement,
)


def build_requirement(
    *,
    requirement_key: str = "project_management",
    description: str = (
        "Lead complex project management programs"
    ),
    evidence_text: str | None = (
        "Strong project management capability"
    ),
    category: RequirementCategory = (
        RequirementCategory.EXPERIENCE
    ),
) -> JobRequirement:
    return JobRequirement(
        requirement_id=uuid.uuid4(),
        opportunity_id=uuid.uuid4(),
        requirement_key=requirement_key,
        description=description,
        priority="MUST_HAVE",
        category=category.value,
        blocking=False,
        evidence_text=evidence_text,
    )


def build_candidate(
    *,
    subject: str,
    value_json: dict,
    tier: EvidenceTier,
    fact_type: ProfileFactType = (
        ProfileFactType.EMPLOYMENT
    ),
) -> CareerEvidenceCandidate:
    return CareerEvidenceCandidate(
        profile_fact_id=uuid.uuid4(),
        fact_type=fact_type,
        subject=subject,
        value_json=value_json,
        tier=tier,
    )


def build_candidate_set(
    *,
    requirement_key: str,
    category: RequirementCategory,
    primary_candidates: list[
        CareerEvidenceCandidate
    ] | None = None,
    supporting_candidates: list[
        CareerEvidenceCandidate
    ] | None = None,
) -> EvidenceCandidateSet:
    return EvidenceCandidateSet(
        requirement_key=requirement_key,
        requirement_category=category,
        retrieval_rule_version="0.1",
        primary_candidates=(
            primary_candidates or []
        ),
        supporting_candidates=(
            supporting_candidates or []
        ),
    )


def test_related_candidate_ranks_above_unrelated_candidate() -> None:
    ranker = EvidenceRelevanceRanker()

    requirement = build_requirement()

    related = build_candidate(
        subject="Project management",
        value_json={
            "responsibilities": [
                "Lead complex projects"
            ]
        },
        tier=EvidenceTier.PRIMARY,
    )

    unrelated = build_candidate(
        subject="Financial reporting",
        value_json={
            "responsibilities": [
                "Prepare monthly reports"
            ]
        },
        tier=EvidenceTier.PRIMARY,
    )

    candidate_set = build_candidate_set(
        requirement_key=(
            requirement.requirement_key
        ),
        category=RequirementCategory.EXPERIENCE,
        primary_candidates=[
            unrelated,
            related,
        ],
    )

    result = ranker.rank(
        requirement=requirement,
        candidate_set=candidate_set,
    )

    assert result.used_fallback is False

    assert (
        result.ranked_candidates[0]
        .candidate.profile_fact_id
        == related.profile_fact_id
    )

    assert (
        result.ranked_candidates[0]
        .relevance_score
        > 0
    )

    assert (
        "project"
        in result.ranked_candidates[0]
        .matched_terms
    )


def test_primary_candidate_gets_higher_score_than_identical_supporting_candidate() -> None:
    ranker = EvidenceRelevanceRanker()

    requirement = build_requirement()

    primary = build_candidate(
        subject="Project management",
        value_json={
            "focus": "Complex project management"
        },
        tier=EvidenceTier.PRIMARY,
    )

    supporting = build_candidate(
        subject="Project management",
        value_json={
            "focus": "Complex project management"
        },
        tier=EvidenceTier.SUPPORTING,
    )

    candidate_set = build_candidate_set(
        requirement_key=(
            requirement.requirement_key
        ),
        category=RequirementCategory.EXPERIENCE,
        primary_candidates=[primary],
        supporting_candidates=[supporting],
    )

    result = ranker.rank(
        requirement=requirement,
        candidate_set=candidate_set,
    )

    assert (
        result.ranked_candidates[0]
        .candidate.profile_fact_id
        == primary.profile_fact_id
    )

    assert (
        result.ranked_candidates[0]
        .relevance_score
        > result.ranked_candidates[1]
        .relevance_score
    )


def test_zero_overlap_uses_deterministic_fallback() -> None:
    ranker = EvidenceRelevanceRanker()

    requirement = build_requirement(
        requirement_key="quantum_computing",
        description="Quantum computing research",
        evidence_text=None,
        category=RequirementCategory.TECHNOLOGY,
    )

    primary = build_candidate(
        subject="Supply chain",
        value_json={
            "focus": "Industrial operations"
        },
        tier=EvidenceTier.PRIMARY,
        fact_type=ProfileFactType.PROJECT,
    )

    supporting = build_candidate(
        subject="Business education",
        value_json={
            "qualification": "General degree"
        },
        tier=EvidenceTier.SUPPORTING,
        fact_type=ProfileFactType.EDUCATION,
    )

    candidate_set = build_candidate_set(
        requirement_key="quantum_computing",
        category=RequirementCategory.TECHNOLOGY,
        primary_candidates=[primary],
        supporting_candidates=[supporting],
    )

    result = ranker.rank(
        requirement=requirement,
        candidate_set=candidate_set,
    )

    assert result.used_fallback is True

    assert len(result.ranked_candidates) == 2

    assert (
        result.ranked_candidates[0]
        .candidate.profile_fact_id
        == primary.profile_fact_id
    )

    assert all(
        candidate.relevance_score == 0.0
        for candidate in result.ranked_candidates
    )


def test_ranking_is_deterministic() -> None:
    ranker = EvidenceRelevanceRanker()

    requirement = build_requirement()

    candidates = [
        build_candidate(
            subject="Project management alpha",
            value_json={
                "focus": "Project management"
            },
            tier=EvidenceTier.PRIMARY,
        ),
        build_candidate(
            subject="Project management beta",
            value_json={
                "focus": "Project management"
            },
            tier=EvidenceTier.PRIMARY,
        ),
    ]

    candidate_set = build_candidate_set(
        requirement_key=(
            requirement.requirement_key
        ),
        category=RequirementCategory.EXPERIENCE,
        primary_candidates=candidates,
    )

    first_result = ranker.rank(
        requirement=requirement,
        candidate_set=candidate_set,
    )

    second_result = ranker.rank(
        requirement=requirement,
        candidate_set=candidate_set,
    )

    first_ids = [
        candidate.candidate.profile_fact_id
        for candidate
        in first_result.ranked_candidates
    ]

    second_ids = [
        candidate.candidate.profile_fact_id
        for candidate
        in second_result.ranked_candidates
    ]

    assert first_ids == second_ids


def test_requirement_key_mismatch_is_rejected() -> None:
    ranker = EvidenceRelevanceRanker()

    requirement = build_requirement(
        requirement_key="project_management"
    )

    candidate_set = build_candidate_set(
        requirement_key="different_requirement",
        category=RequirementCategory.EXPERIENCE,
    )

    with pytest.raises(
        ValueError,
        match="Requirement key does not match",
    ):
        ranker.rank(
            requirement=requirement,
            candidate_set=candidate_set,
        )


def test_duplicate_candidate_ids_are_rejected() -> None:
    ranker = EvidenceRelevanceRanker()

    requirement = build_requirement()

    candidate = build_candidate(
        subject="Project management",
        value_json={
            "focus": "Project management"
        },
        tier=EvidenceTier.PRIMARY,
    )

    duplicate = CareerEvidenceCandidate(
        profile_fact_id=candidate.profile_fact_id,
        fact_type=ProfileFactType.EDUCATION,
        subject="Duplicate",
        value_json={},
        tier=EvidenceTier.SUPPORTING,
    )

    candidate_set = build_candidate_set(
        requirement_key=(
            requirement.requirement_key
        ),
        category=RequirementCategory.EXPERIENCE,
        primary_candidates=[candidate],
        supporting_candidates=[duplicate],
    )

    with pytest.raises(
        ValueError,
        match=(
            "duplicate profile_fact_id values"
        ),
    ):
        ranker.rank(
            requirement=requirement,
            candidate_set=candidate_set,
        )