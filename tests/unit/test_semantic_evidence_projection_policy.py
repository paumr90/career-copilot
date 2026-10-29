from pathlib import Path

import pytest

from app.domain.enums import (
    ProfileFactType,
    RequirementCategory,
)
from app.domain.rules.semantic_evidence_projection import (
    SemanticEvidenceProjectionPolicy,
)


def write_config(
    tmp_path: Path,
    content: str,
) -> Path:
    config_path = (
        tmp_path
        / "semantic_evidence_projection.yaml"
    )

    config_path.write_text(
        content,
        encoding="utf-8",
    )

    return config_path


def test_default_policy_loads() -> None:
    policy = (
        SemanticEvidenceProjectionPolicy()
    )

    assert policy.version == "0.2"


def test_technology_skill_fields_are_minimized() -> None:
    policy = (
        SemanticEvidenceProjectionPolicy()
    )

    fields = policy.allowed_fields(
        category=(
            RequirementCategory.TECHNOLOGY
        ),
        fact_type=ProfileFactType.SKILL,
    )

    assert fields == (
        "areas",
        "level",
    )


def test_compensation_is_only_projected_for_compensation() -> None:
    policy = (
        SemanticEvidenceProjectionPolicy()
    )

    fields = policy.allowed_fields(
        category=(
            RequirementCategory.COMPENSATION
        ),
        fact_type=(
            ProfileFactType
            .COMPENSATION_PREFERENCE
        ),
    )

    assert fields == (
        "minimum_fixed_salary_eur",
        "variable_compensation_expected",
    )

    with pytest.raises(
        ValueError,
        match="is not eligible",
    ):
        policy.allowed_fields(
            category=(
                RequirementCategory.EXPERIENCE
            ),
            fact_type=(
                ProfileFactType
                .COMPENSATION_PREFERENCE
            ),
        )


def test_positioning_guardrail_is_not_exportable() -> None:
    policy = (
        SemanticEvidenceProjectionPolicy()
    )

    fields = policy.allowed_fields(
        category=RequirementCategory.OTHER,
        fact_type=(
            ProfileFactType.POSITIONING
        ),
    )

    assert "guardrail" not in fields

    assert fields == (
        "statement",
        "differentiators",
    )


def test_internal_ai_initiative_is_not_exportable() -> None:
    policy = (
        SemanticEvidenceProjectionPolicy()
    )

    fields = policy.allowed_fields(
        category=(
            RequirementCategory.TECHNOLOGY
        ),
        fact_type=(
            ProfileFactType.EMPLOYMENT
        ),
    )

    assert (
        "internal_ai_initiative"
        not in fields
    )


def test_clients_are_not_exportable_by_default() -> None:
    policy = (
        SemanticEvidenceProjectionPolicy()
    )

    for category in (
        RequirementCategory.EXPERIENCE,
        RequirementCategory.INDUSTRY,
        RequirementCategory.TECHNOLOGY,
        RequirementCategory.RESPONSIBILITY,
    ):
        fields = policy.allowed_fields(
            category=category,
            fact_type=(
                ProfileFactType.EMPLOYMENT
            ),
        )

        assert "clients" not in fields