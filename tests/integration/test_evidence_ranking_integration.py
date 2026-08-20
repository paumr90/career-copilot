import uuid

from sqlalchemy.orm import Session

from app.domain.enums import (
    EvidenceTier,
    RequirementCategory,
)
from app.infrastructure.db.session import engine
from app.modules.fit.ranking import (
    EvidenceRelevanceRanker,
)
from app.modules.fit.retrieval import (
    CareerEvidenceRetriever,
)
from app.modules.opportunities.models import (
    JobRequirement,
)


def build_requirement(
    *,
    requirement_key: str,
    description: str,
    evidence_text: str | None,
    category: RequirementCategory,
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


def test_real_career_master_candidates_can_be_ranked() -> None:
    retriever = CareerEvidenceRetriever()
    ranker = EvidenceRelevanceRanker()

    requirement = build_requirement(
        requirement_key="digital_transformation",
        description=(
            "Experience leading digital transformation "
            "projects and programs"
        ),
        evidence_text=(
            "Digital transformation experience required"
        ),
        category=RequirementCategory.TECHNOLOGY,
    )

    with Session(engine) as session:
        candidate_set = (
            retriever.retrieve_for_requirement(
                session=session,
                requirement=requirement,
            )
        )

        result = ranker.rank(
            requirement=requirement,
            candidate_set=candidate_set,
        )

        all_candidate_ids = {
            candidate.profile_fact_id
            for candidate in (
                candidate_set.primary_candidates
                + candidate_set.supporting_candidates
            )
        }

        ranked_ids = {
            ranked.candidate.profile_fact_id
            for ranked in result.ranked_candidates
        }

        assert all_candidate_ids
        assert ranked_ids

        assert ranked_ids.issubset(
            all_candidate_ids
        )

        assert result.total_candidate_count == (
            len(candidate_set.primary_candidates)
            + len(candidate_set.supporting_candidates)
        )

        assert len(
            result.ranked_candidates
        ) <= 8

        assert result.used_fallback is False

        assert all(
            ranked.relevance_score > 0
            for ranked in result.ranked_candidates
        )

        assert (
            result.retrieval_rule_version
            == "0.1"
        )

        assert (
            result.ranking_rule_version
            == "0.1"
        )

        assert result.ranking_method == (
            "deterministic_lexical_shortlisting"
        )


def test_real_career_master_ranking_is_deterministic() -> None:
    retriever = CareerEvidenceRetriever()
    ranker = EvidenceRelevanceRanker()

    requirement = build_requirement(
        requirement_key="project_management",
        description=(
            "Experience managing complex projects "
            "and project teams"
        ),
        evidence_text=(
            "Strong project management experience"
        ),
        category=RequirementCategory.EXPERIENCE,
    )

    with Session(engine) as session:
        candidate_set = (
            retriever.retrieve_for_requirement(
                session=session,
                requirement=requirement,
            )
        )

        first_result = ranker.rank(
            requirement=requirement,
            candidate_set=candidate_set,
        )

        second_result = ranker.rank(
            requirement=requirement,
            candidate_set=candidate_set,
        )

        first_ranking = [
            (
                ranked.candidate.profile_fact_id,
                ranked.relevance_score,
                ranked.matched_terms,
            )
            for ranked
            in first_result.ranked_candidates
        ]

        second_ranking = [
            (
                ranked.candidate.profile_fact_id,
                ranked.relevance_score,
                ranked.matched_terms,
            )
            for ranked
            in second_result.ranked_candidates
        ]

        assert first_ranking
        assert first_ranking == second_ranking


def test_real_candidate_pool_uses_fallback_when_no_lexical_overlap() -> None:
    retriever = CareerEvidenceRetriever()
    ranker = EvidenceRelevanceRanker()

    requirement = build_requirement(
        requirement_key="zyxqv_unmatched_requirement",
        description=(
            "Zyxqv plmokn qwertz unusualconcept"
        ),
        evidence_text=(
            "Xyzabc nomatchtoken"
        ),
        category=RequirementCategory.TECHNOLOGY,
    )

    with Session(engine) as session:
        candidate_set = (
            retriever.retrieve_for_requirement(
                session=session,
                requirement=requirement,
            )
        )

        result = ranker.rank(
            requirement=requirement,
            candidate_set=candidate_set,
        )

        assert result.total_candidate_count > 0

        assert result.used_fallback is True

        assert len(result.ranked_candidates) <= 5

        assert all(
            ranked.relevance_score == 0.0
            for ranked in result.ranked_candidates
        )

        if result.ranked_candidates:
            assert (
                result.ranked_candidates[0]
                .candidate.tier
                == EvidenceTier.PRIMARY
            )