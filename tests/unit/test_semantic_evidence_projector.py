import uuid

import pytest

from app.domain.enums import (
    EvidenceTier,
    ProfileFactType,
    RequirementCategory,
    RequirementPriority,
)
from app.modules.fit.projection import (
    SemanticEvidenceProjector,
)
from app.modules.fit.schemas import (
    SemanticAssessmentEvidence,
    SemanticAssessmentRequest,
    SemanticAssessmentRequirement,
)


def build_employment_evidence():
    return SemanticAssessmentEvidence(
        profile_fact_id=uuid.uuid4(),
        fact_type=(
            ProfileFactType.EMPLOYMENT
        ),
        tier=EvidenceTier.PRIMARY,
        subject="Example Employment",
        value_json={
            "role": "Program Manager",
            "focus": "Digital transformation",
            "responsibilities": [
                "Manage transformation projects"
            ],
            "knowledge": [
                "Jira",
                "SQL",
            ],
            "clients": [
                "Private Client"
            ],
            "internal_level": (
                "Confidential Internal Level"
            ),
            "internal_ai_initiative": {
                "members": 3,
                "detail": "Private initiative",
            },
            "context": (
                "Additional private context"
            ),
        },
        relevance_score=5.0,
        matched_terms=[
            "jira",
            "transformation",
        ],
    )


def test_technology_employment_is_minimized() -> None:
    projector = SemanticEvidenceProjector()

    evidence = build_employment_evidence()

    projected = projector.project_evidence(
        category=(
            RequirementCategory.TECHNOLOGY
        ),
        evidence=evidence,
    )

    assert projected.value_json == {
        "role": "Program Manager",
        "focus": "Digital transformation",
        "responsibilities": [
            "Manage transformation projects"
        ],
        "knowledge": [
            "Jira",
            "SQL",
        ],
    }


def test_non_allowlisted_fields_are_removed() -> None:
    projector = SemanticEvidenceProjector()

    projected = projector.project_evidence(
        category=(
            RequirementCategory.TECHNOLOGY
        ),
        evidence=build_employment_evidence(),
    )

    assert (
        "clients"
        not in projected.value_json
    )

    assert (
        "internal_level"
        not in projected.value_json
    )

    assert (
        "internal_ai_initiative"
        not in projected.value_json
    )

    assert (
        "context"
        not in projected.value_json
    )


def test_projection_preserves_evidence_identity() -> None:
    projector = SemanticEvidenceProjector()

    evidence = build_employment_evidence()

    projected = projector.project_evidence(
        category=(
            RequirementCategory.TECHNOLOGY
        ),
        evidence=evidence,
    )

    assert (
        projected.profile_fact_id
        == evidence.profile_fact_id
    )

    assert (
        projected.fact_type
        == evidence.fact_type
    )

    assert (
        projected.tier
        == evidence.tier
    )

    assert (
        projected.subject
        == evidence.subject
    )

    assert (
        projected.relevance_score
        == evidence.relevance_score
    )

    assert (
        projected.matched_terms
        == evidence.matched_terms
    )


def test_projection_does_not_modify_original_evidence() -> None:
    projector = SemanticEvidenceProjector()

    evidence = build_employment_evidence()

    projected = projector.project_evidence(
        category=(
            RequirementCategory.TECHNOLOGY
        ),
        evidence=evidence,
    )

    projected.value_json[
        "knowledge"
    ].append(
        "Modified after projection"
    )

    projected.matched_terms.append(
        "modified"
    )

    assert evidence.value_json[
        "knowledge"
    ] == [
        "Jira",
        "SQL",
    ]

    assert evidence.matched_terms == [
        "jira",
        "transformation",
    ]

    assert (
        "clients"
        in evidence.value_json
    )


def test_project_request_minimizes_all_evidence() -> None:
    projector = SemanticEvidenceProjector()

    employment = (
        build_employment_evidence()
    )

    skill = SemanticAssessmentEvidence(
        profile_fact_id=uuid.uuid4(),
        fact_type=ProfileFactType.SKILL,
        tier=EvidenceTier.PRIMARY,
        subject="Technology skills",
        value_json={
            "areas": [
                "Jira",
                "SQL",
            ],
            "level": "EXPERIENCE",
            "private_field": (
                "must not leave local boundary"
            ),
        },
        relevance_score=8.0,
        matched_terms=[
            "jira",
        ],
    )

    request = SemanticAssessmentRequest(
        semantic_rule_version="0.1",
        retrieval_rule_version="0.1",
        ranking_rule_version="0.1",
        requirement=(
            SemanticAssessmentRequirement(
                requirement_key=(
                    "jira_experience"
                ),
                description=(
                    "Experience with Jira"
                ),
                priority=(
                    RequirementPriority
                    .NICE_TO_HAVE
                ),
                category=(
                    RequirementCategory
                    .TECHNOLOGY
                ),
                blocking=False,
                evidence_text=(
                    "Experience with Jira "
                    "is preferred."
                ),
            )
        ),
        ranked_evidence=[
            employment,
            skill,
        ],
    )

    projected = (
        projector.project_request(
            request=request
        )
    )

    assert len(
        projected.ranked_evidence
    ) == 2

    projected_employment = (
        projected.ranked_evidence[0]
    )

    projected_skill = (
        projected.ranked_evidence[1]
    )

    assert (
        "clients"
        not in projected_employment
        .value_json
    )

    assert (
        projected_skill.value_json
        == {
            "areas": [
                "Jira",
                "SQL",
            ],
            "level": "EXPERIENCE",
        }
    )

    assert (
        "private_field"
        not in projected_skill
        .value_json
    )


def test_empty_projection_is_allowed() -> None:
    projector = SemanticEvidenceProjector()

    evidence = SemanticAssessmentEvidence(
        profile_fact_id=uuid.uuid4(),
        fact_type=ProfileFactType.SKILL,
        tier=EvidenceTier.PRIMARY,
        subject="Example skill",
        value_json={
            "unexpected_field": (
                "not exportable"
            )
        },
        relevance_score=1.0,
        matched_terms=[],
    )

    projected = projector.project_evidence(
        category=(
            RequirementCategory.TECHNOLOGY
        ),
        evidence=evidence,
    )

    assert projected.value_json == {}


def test_ineligible_fact_type_is_rejected() -> None:
    projector = SemanticEvidenceProjector()

    evidence = SemanticAssessmentEvidence(
        profile_fact_id=uuid.uuid4(),
        fact_type=(
            ProfileFactType
            .COMPENSATION_PREFERENCE
        ),
        tier=EvidenceTier.PRIMARY,
        subject="Compensation preference",
        value_json={
            "minimum_fixed_salary_eur": 1,
        },
        relevance_score=1.0,
        matched_terms=[],
    )

    with pytest.raises(
        ValueError,
        match="is not eligible",
    ):
        projector.project_evidence(
            category=(
                RequirementCategory
                .TECHNOLOGY
            ),
            evidence=evidence,
        )