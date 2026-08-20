import uuid

import pytest

from app.domain.enums import (
    EvidenceTier,
    GapBasis,
    MatchStatus,
    ProfileFactType,
    RequirementCategory,
)
from app.modules.fit.assessment import (
    RequirementAssessmentValidator,
)
from app.modules.fit.schemas import (
    CareerEvidenceCandidate,
    EvidenceRankingResult,
    ProfileEvidenceReference,
    RankedEvidenceCandidate,
    RequirementAssessmentProposal,
)


def build_ranked_candidate(
    *,
    tier: EvidenceTier,
) -> RankedEvidenceCandidate:
    candidate = CareerEvidenceCandidate(
        profile_fact_id=uuid.uuid4(),
        fact_type=ProfileFactType.EMPLOYMENT,
        subject="Test evidence",
        value_json={
            "responsibilities": [
                "Test responsibility"
            ]
        },
        tier=tier,
    )

    return RankedEvidenceCandidate(
        candidate=candidate,
        relevance_score=10.0,
        matched_terms=["test"],
        exact_phrase_matches=[],
    )


def build_ranking_result(
    ranked_candidates: list[
        RankedEvidenceCandidate
    ],
) -> EvidenceRankingResult:
    return EvidenceRankingResult(
        requirement_key="test_requirement",
        requirement_category=(
            RequirementCategory.EXPERIENCE
        ),
        retrieval_rule_version="0.1",
        ranking_rule_version="0.1",
        ranking_method=(
            "deterministic_lexical_shortlisting"
        ),
        total_candidate_count=len(
            ranked_candidates
        ),
        ranked_candidates=ranked_candidates,
        used_fallback=False,
    )


def reference_for(
    ranked: RankedEvidenceCandidate,
) -> ProfileEvidenceReference:
    return ProfileEvidenceReference(
        profile_fact_id=(
            ranked.candidate.profile_fact_id
        ),
        note="Test evidence.",
    )


def test_valid_match_with_primary_evidence() -> None:
    validator = RequirementAssessmentValidator()

    primary = build_ranked_candidate(
        tier=EvidenceTier.PRIMARY
    )

    ranking = build_ranking_result(
        [primary]
    )

    proposal = RequirementAssessmentProposal(
        requirement_key="test_requirement",
        proposed_status="MATCH",
        evidence=[reference_for(primary)],
        rationale=(
            "Primary evidence directly supports "
            "the requirement."
        ),
    )

    assessment = validator.validate(
        proposal=proposal,
        ranking_result=ranking,
    )

    assert (
        assessment.match_status
        == MatchStatus.MATCH
    )

    assert len(assessment.evidence) == 1


def test_match_without_evidence_is_rejected() -> None:
    validator = RequirementAssessmentValidator()

    ranking = build_ranking_result([])

    proposal = RequirementAssessmentProposal(
        requirement_key="test_requirement",
        proposed_status="MATCH",
        evidence=[],
        rationale="Unsupported match proposal.",
    )

    with pytest.raises(
        ValueError,
        match="MATCH requires at least 1 PRIMARY",
    ):
        validator.validate(
            proposal=proposal,
            ranking_result=ranking,
        )


def test_supporting_only_match_is_rejected() -> None:
    validator = RequirementAssessmentValidator()

    supporting = build_ranked_candidate(
        tier=EvidenceTier.SUPPORTING
    )

    ranking = build_ranking_result(
        [supporting]
    )

    proposal = RequirementAssessmentProposal(
        requirement_key="test_requirement",
        proposed_status="MATCH",
        evidence=[reference_for(supporting)],
        rationale=(
            "Supporting evidence only."
        ),
    )

    with pytest.raises(
        ValueError,
        match="MATCH requires at least 1 PRIMARY",
    ):
        validator.validate(
            proposal=proposal,
            ranking_result=ranking,
        )


def test_unranked_evidence_is_rejected() -> None:
    validator = RequirementAssessmentValidator()

    primary = build_ranked_candidate(
        tier=EvidenceTier.PRIMARY
    )

    ranking = build_ranking_result(
        [primary]
    )

    proposal = RequirementAssessmentProposal(
        requirement_key="test_requirement",
        proposed_status="MATCH",
        evidence=[
            ProfileEvidenceReference(
                profile_fact_id=uuid.uuid4(),
                note="Invented evidence reference.",
            )
        ],
        rationale="Invalid evidence.",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Assessment evidence must come "
            "from the governed ranked shortlist"
        ),
    ):
        validator.validate(
            proposal=proposal,
            ranking_result=ranking,
        )


def test_gap_without_gap_basis_is_rejected() -> None:
    validator = RequirementAssessmentValidator()

    primary = build_ranked_candidate(
        tier=EvidenceTier.PRIMARY
    )

    ranking = build_ranking_result(
        [primary]
    )

    proposal = RequirementAssessmentProposal(
        requirement_key="test_requirement",
        proposed_status="GAP",
        evidence=[reference_for(primary)],
        rationale=(
            "Requirement is not met."
        ),
        gap_basis=None,
    )

    with pytest.raises(
        ValueError,
        match="GAP requires an explicit gap_basis",
    ):
        validator.validate(
            proposal=proposal,
            ranking_result=ranking,
        )


def test_valid_gap_preserves_gap_basis() -> None:
    validator = RequirementAssessmentValidator()

    primary = build_ranked_candidate(
        tier=EvidenceTier.PRIMARY
    )

    ranking = build_ranking_result(
        [primary]
    )

    proposal = RequirementAssessmentProposal(
        requirement_key="test_requirement",
        proposed_status="GAP",
        evidence=[reference_for(primary)],
        rationale=(
            "Confirmed evidence demonstrates "
            "a measurable shortfall."
        ),
        gap_basis="NUMERIC_SHORTFALL",
    )

    assessment = validator.validate(
        proposal=proposal,
        ranking_result=ranking,
    )

    assert assessment.match_status == MatchStatus.GAP
    assert (
        assessment.gap_basis
        == GapBasis.NUMERIC_SHORTFALL
    )


def test_unknown_without_evidence_is_valid() -> None:
    validator = RequirementAssessmentValidator()

    ranking = build_ranking_result([])

    proposal = RequirementAssessmentProposal(
        requirement_key="test_requirement",
        proposed_status="UNKNOWN",
        evidence=[],
        rationale=(
            "Available evidence is insufficient."
        ),
    )

    assessment = validator.validate(
        proposal=proposal,
        ranking_result=ranking,
    )

    assert (
        assessment.match_status
        == MatchStatus.UNKNOWN
    )

    assert assessment.evidence == []


def test_unknown_with_evidence_is_rejected() -> None:
    validator = RequirementAssessmentValidator()

    primary = build_ranked_candidate(
        tier=EvidenceTier.PRIMARY
    )

    ranking = build_ranking_result(
        [primary]
    )

    proposal = RequirementAssessmentProposal(
        requirement_key="test_requirement",
        proposed_status="UNKNOWN",
        evidence=[reference_for(primary)],
        rationale="Invalid unknown proposal.",
    )

    with pytest.raises(
        ValueError,
        match="UNKNOWN does not allow cited evidence",
    ):
        validator.validate(
            proposal=proposal,
            ranking_result=ranking,
        )


def test_non_gap_status_cannot_have_gap_basis() -> None:
    validator = RequirementAssessmentValidator()

    primary = build_ranked_candidate(
        tier=EvidenceTier.PRIMARY
    )

    ranking = build_ranking_result(
        [primary]
    )

    proposal = RequirementAssessmentProposal(
        requirement_key="test_requirement",
        proposed_status="MATCH",
        evidence=[reference_for(primary)],
        rationale="Valid evidence.",
        gap_basis="EXPLICIT_CONTRADICTION",
    )

    with pytest.raises(
        ValueError,
        match=(
            "gap_basis is only valid when "
            "proposed_status is GAP"
        ),
    ):
        validator.validate(
            proposal=proposal,
            ranking_result=ranking,
        )


def test_more_than_five_citations_are_rejected() -> None:
    validator = RequirementAssessmentValidator()

    ranked = [
        build_ranked_candidate(
            tier=EvidenceTier.PRIMARY
        )
        for _ in range(6)
    ]

    ranking = build_ranking_result(
        ranked
    )

    proposal = RequirementAssessmentProposal(
        requirement_key="test_requirement",
        proposed_status="MATCH",
        evidence=[
            reference_for(candidate)
            for candidate in ranked
        ],
        rationale="Too many citations.",
    )

    with pytest.raises(
        ValueError,
        match=(
            "cites more evidence than "
            "maximum_cited_evidence allows"
        ),
    ):
        validator.validate(
            proposal=proposal,
            ranking_result=ranking,
        )