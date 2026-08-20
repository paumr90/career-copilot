import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import (
    EvidenceTier,
    ProfileFactType,
    RequirementCategory,
)
from app.domain.rules.evidence_retrieval import (
    EvidenceRetrievalPolicy,
)
from app.infrastructure.db.session import engine
from app.modules.fit.retrieval import (
    CareerEvidenceRetriever,
)
from app.modules.governance.models import (
    ProfileFact,
    Source,
)
from app.modules.opportunities.models import (
    JobRequirement,
)


def build_requirement(
    category: RequirementCategory,
    requirement_key: str = "test_requirement",
) -> JobRequirement:
    return JobRequirement(
        requirement_id=uuid.uuid4(),
        opportunity_id=uuid.uuid4(),
        requirement_key=requirement_key,
        description="Test requirement",
        priority="MUST_HAVE",
        category=category.value,
        blocking=False,
        evidence_text="Test evidence text.",
    )


def test_evidence_retrieval_policy_maps_categories() -> None:
    policy = EvidenceRetrievalPolicy()

    technology_primary = (
        policy.get_primary_fact_types(
            RequirementCategory.TECHNOLOGY
        )
    )

    technology_supporting = (
        policy.get_supporting_fact_types(
            RequirementCategory.TECHNOLOGY
        )
    )

    assert technology_primary == [
        ProfileFactType.SKILL,
        ProfileFactType.EMPLOYMENT,
        ProfileFactType.PROJECT,
    ]

    assert technology_supporting == [
        ProfileFactType.EDUCATION,
        ProfileFactType.CERTIFICATION,
    ]

    assert (
        policy.get_primary_fact_types(
            RequirementCategory.OTHER
        )
        == []
    )


def test_technology_retrieval_returns_expected_candidate_pool() -> None:
    retriever = CareerEvidenceRetriever()

    requirement = build_requirement(
        RequirementCategory.TECHNOLOGY,
        "technology_requirement",
    )

    with Session(engine) as session:
        result = retriever.retrieve_for_requirement(
            session=session,
            requirement=requirement,
        )

        assert result.requirement_key == (
            "technology_requirement"
        )

        assert (
            result.requirement_category
            == RequirementCategory.TECHNOLOGY
        )

        assert result.retrieval_rule_version == "0.1"

        assert len(result.primary_candidates) == 20
        assert len(result.supporting_candidates) == 4

        assert {
            candidate.fact_type
            for candidate
            in result.primary_candidates
        } == {
            ProfileFactType.SKILL,
            ProfileFactType.EMPLOYMENT,
            ProfileFactType.PROJECT,
        }

        assert {
            candidate.fact_type
            for candidate
            in result.supporting_candidates
        } == {
            ProfileFactType.EDUCATION,
            ProfileFactType.CERTIFICATION,
        }

        assert all(
            candidate.tier == EvidenceTier.PRIMARY
            for candidate
            in result.primary_candidates
        )

        assert all(
            candidate.tier == EvidenceTier.SUPPORTING
            for candidate
            in result.supporting_candidates
        )


def test_retrieved_candidates_are_canonical_and_active() -> None:
    retriever = CareerEvidenceRetriever()

    requirement = build_requirement(
        RequirementCategory.EXPERIENCE,
        "experience_requirement",
    )

    with Session(engine) as session:
        result = retriever.retrieve_for_requirement(
            session=session,
            requirement=requirement,
        )

        candidate_ids = {
            candidate.profile_fact_id
            for candidate
            in (
                result.primary_candidates
                + result.supporting_candidates
            )
        }

        assert candidate_ids

        rows = session.execute(
            select(
                ProfileFact.fact_id,
                ProfileFact.evidence_state,
                ProfileFact.superseded_by,
                Source.source_type,
                Source.authority_level,
                Source.immutable,
            )
            .join(
                Source,
                ProfileFact.source_id
                == Source.source_id,
            )
            .where(
                ProfileFact.fact_id.in_(
                    candidate_ids
                )
            )
        ).all()

        assert len(rows) == len(candidate_ids)

        for row in rows:
            assert row.evidence_state == "CONFIRMED"
            assert row.superseded_by is None
            assert row.source_type == "PROFILE"
            assert (
                row.authority_level
                == "CANONICAL_PROFILE"
            )
            assert row.immutable is True


def test_other_category_has_supporting_context_only() -> None:
    retriever = CareerEvidenceRetriever()

    requirement = build_requirement(
        RequirementCategory.OTHER,
        "other_requirement",
    )

    with Session(engine) as session:
        result = retriever.retrieve_for_requirement(
            session=session,
            requirement=requirement,
        )

        assert result.primary_candidates == []

        assert len(
            result.supporting_candidates
        ) == 3

        assert {
            candidate.fact_type
            for candidate
            in result.supporting_candidates
        } == {
            ProfileFactType.PROFESSIONAL_SUMMARY,
            ProfileFactType.POSITIONING,
            ProfileFactType.CAREER_OBJECTIVE,
        }


def test_ineligible_profile_facts_are_excluded() -> None:
    retriever = CareerEvidenceRetriever()

    requirement = build_requirement(
        RequirementCategory.TECHNOLOGY,
        "technology_filter_test",
    )

    with Session(engine) as session:
        canonical_source = session.scalar(
            select(Source)
            .where(
                Source.source_type == "PROFILE",
                Source.authority_level
                == "CANONICAL_PROFILE",
                Source.immutable.is_(True),
            )
            .limit(1)
        )

        assert canonical_source is not None

        existing_fact_id = session.scalar(
            select(ProfileFact.fact_id)
            .where(
                ProfileFact.source_id
                == canonical_source.source_id
            )
            .limit(1)
        )

        assert existing_fact_id is not None

        noncanonical_source = Source(
            source_type="PROFILE",
            external_id=None,
            uri=None,
            captured_at=datetime.now(
                timezone.utc
            ),
            snapshot_hash=None,
            metadata_json={},
            authority_level=(
                "NON_CANONICAL_PROFILE"
            ),
            immutable=True,
        )

        session.add(noncanonical_source)
        session.flush()

        noncanonical_fact = ProfileFact(
            fact_type="skill",
            subject="Noncanonical test skill",
            value_json={
                "areas": ["test"],
                "level": "STRONG",
            },
            evidence_state="CONFIRMED",
            source_id=(
                noncanonical_source.source_id
            ),
        )

        inferred_fact = ProfileFact(
            fact_type="skill",
            subject="Inferred test skill",
            value_json={
                "areas": ["test"],
                "level": "STRONG",
            },
            evidence_state="INFERRED",
            source_id=(
                canonical_source.source_id
            ),
        )

        superseded_fact = ProfileFact(
            fact_type="skill",
            subject="Superseded test skill",
            value_json={
                "areas": ["test"],
                "level": "STRONG",
            },
            evidence_state="CONFIRMED",
            source_id=(
                canonical_source.source_id
            ),
            superseded_by=existing_fact_id,
        )

        session.add_all(
            [
                noncanonical_fact,
                inferred_fact,
                superseded_fact,
            ]
        )

        session.flush()

        result = retriever.retrieve_for_requirement(
            session=session,
            requirement=requirement,
        )

        returned_ids = {
            candidate.profile_fact_id
            for candidate
            in (
                result.primary_candidates
                + result.supporting_candidates
            )
        }

        assert (
            noncanonical_fact.fact_id
            not in returned_ids
        )

        assert inferred_fact.fact_id not in returned_ids

        assert (
            superseded_fact.fact_id
            not in returned_ids
        )

        assert len(result.primary_candidates) == 20
        assert len(result.supporting_candidates) == 4

        session.rollback()