import uuid

import pytest

from app.domain.enums import (
    EvidenceTier,
    ProfileFactType,
    RequirementCategory,
)
from app.modules.fit.schemas import (
    CareerEvidenceCandidate,
    EvidenceRankingResult,
    RankedEvidenceCandidate,
)
from app.modules.fit.semantic import (
    SemanticAssessmentRequestBuilder,
)
from app.modules.opportunities.models import (
    JobRequirement,
)


def build_requirement(
    *,
    requirement_key: str = "project_management",
    category: str = "EXPERIENCE",
) -> JobRequirement:
    return JobRequirement(
        requirement_id=uuid.uuid4(),
        opportunity_id=uuid.uuid4(),
        requirement_key=requirement_key,
        description=(
            "Experience managing complex projects "
            "and project teams"
        ),
        priority="MUST_HAVE",
        category=category,
        blocking=False,
        evidence_text=(
            "Strong project management "
            "experience required."
        ),
    )


def build_ranked_candidate(
    *,
    index: int,
    tier: EvidenceTier = EvidenceTier.PRIMARY,
) -> RankedEvidenceCandidate:
    return RankedEvidenceCandidate(
        candidate=CareerEvidenceCandidate(
            profile_fact_id=uuid.uuid4(),
            fact_type=(
                ProfileFactType.EMPLOYMENT
            ),
            subject=f"Evidence {index}",
            value_json={
                "responsibilities": [
                    f"Responsibility {index}"
                ]
            },
            tier=tier,
        ),
        relevance_score=float(
            100 - index
        ),
        matched_terms=[
            "project",
            "management",
        ],
        exact_phrase_matches=[],
    )


def build_ranking_result(
    *,
    requirement_key: str = "project_management",
    category: RequirementCategory = (
        RequirementCategory.EXPERIENCE
    ),
    candidate_count: int = 2,
) -> EvidenceRankingResult:
    ranked_candidates = [
        build_ranked_candidate(
            index=index
        )
        for index in range(candidate_count)
    ]

    return EvidenceRankingResult(
        requirement_key=requirement_key,
        requirement_category=category,
        retrieval_rule_version="0.1",
        ranking_rule_version="0.1",
        ranking_method=(
            "deterministic_lexical_shortlisting"
        ),
        total_candidate_count=candidate_count,
        ranked_candidates=ranked_candidates,
        used_fallback=False,
    )


def test_builder_creates_semantic_request() -> None:
    builder = SemanticAssessmentRequestBuilder()

    requirement = build_requirement()
    ranking = build_ranking_result()

    request = builder.build(
        requirement=requirement,
        ranking_result=ranking,
    )

    assert (
        request.semantic_rule_version
        == "0.1"
    )

    assert (
        request.retrieval_rule_version
        == "0.1"
    )

    assert (
        request.ranking_rule_version
        == "0.1"
    )

    assert (
        request.requirement.requirement_key
        == "project_management"
    )

    assert (
        request.requirement.priority.value
        == "MUST_HAVE"
    )

    assert (
        request.requirement.category
        == RequirementCategory.EXPERIENCE
    )

    assert len(request.ranked_evidence) == 2


def test_builder_only_uses_ranked_evidence() -> None:
    builder = SemanticAssessmentRequestBuilder()

    requirement = build_requirement()
    ranking = build_ranking_result(
        candidate_count=3
    )

    request = builder.build(
        requirement=requirement,
        ranking_result=ranking,
    )

    ranked_ids = [
        ranked.candidate.profile_fact_id
        for ranked
        in ranking.ranked_candidates
    ]

    request_ids = [
        evidence.profile_fact_id
        for evidence
        in request.ranked_evidence
    ]

    assert request_ids == ranked_ids


def test_builder_preserves_rank_order() -> None:
    builder = SemanticAssessmentRequestBuilder()

    requirement = build_requirement()
    ranking = build_ranking_result(
        candidate_count=4
    )

    request = builder.build(
        requirement=requirement,
        ranking_result=ranking,
    )

    expected_subjects = [
        ranked.candidate.subject
        for ranked
        in ranking.ranked_candidates
    ]

    actual_subjects = [
        evidence.subject
        for evidence
        in request.ranked_evidence
    ]

    assert actual_subjects == expected_subjects


def test_builder_limits_evidence_to_policy_maximum() -> None:
    builder = SemanticAssessmentRequestBuilder()

    requirement = build_requirement()
    ranking = build_ranking_result(
        candidate_count=10
    )

    request = builder.build(
        requirement=requirement,
        ranking_result=ranking,
    )

    assert len(request.ranked_evidence) == 8

    expected_ids = [
        ranked.candidate.profile_fact_id
        for ranked
        in ranking.ranked_candidates[:8]
    ]

    actual_ids = [
        evidence.profile_fact_id
        for evidence
        in request.ranked_evidence
    ]

    assert actual_ids == expected_ids


def test_requirement_key_mismatch_is_rejected() -> None:
    builder = SemanticAssessmentRequestBuilder()

    requirement = build_requirement(
        requirement_key="project_management"
    )

    ranking = build_ranking_result(
        requirement_key="different_requirement"
    )

    with pytest.raises(
        ValueError,
        match=(
            "Semantic assessment requirement_key "
            "must match"
        ),
    ):
        builder.build(
            requirement=requirement,
            ranking_result=ranking,
        )


def test_requirement_category_mismatch_is_rejected() -> None:
    builder = SemanticAssessmentRequestBuilder()

    requirement = build_requirement(
        category="EXPERIENCE"
    )

    ranking = build_ranking_result(
        category=(
            RequirementCategory.TECHNOLOGY
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "Semantic assessment requirement "
            "category must match"
        ),
    ):
        builder.build(
            requirement=requirement,
            ranking_result=ranking,
        )


def test_semantic_request_does_not_expose_ranking_only_fields() -> None:
    builder = SemanticAssessmentRequestBuilder()

    requirement = build_requirement()
    ranking = build_ranking_result(
        candidate_count=1
    )

    request = builder.build(
        requirement=requirement,
        ranking_result=ranking,
    )

    evidence_payload = (
        request.ranked_evidence[0]
        .model_dump(mode="json")
    )

    assert (
        "exact_phrase_matches"
        not in evidence_payload
    )

    assert (
        set(evidence_payload.keys())
        == {
            "profile_fact_id",
            "fact_type",
            "tier",
            "subject",
            "value_json",
            "relevance_score",
            "matched_terms",
        }
    )