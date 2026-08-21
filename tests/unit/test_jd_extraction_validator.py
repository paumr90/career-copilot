import pytest

from app.modules.opportunities.extraction import (
    JDExtractionValidator,
)
from app.modules.opportunities.schemas import (
    JobDescriptionInput,
    JobRequirementInput,
)


RAW_JD = (
    "We are looking for a Program Manager. "
    "Candidates must have at least 5 years "
    "of project management experience. "
    "Experience with cloud platforms is preferred. "
    "The role is hybrid in Barcelona."
)


def build_extraction(
    *,
    requirement_key: str = (
        "project_management_experience"
    ),
    priority: str = "MUST_HAVE",
    blocking: bool = False,
    evidence_text: str | None = (
        "must have at least 5 years "
        "of project management experience"
    ),
) -> JobDescriptionInput:
    return JobDescriptionInput(
        company="Example Company",
        role_title="Program Manager",
        location="Barcelona",
        raw_text=RAW_JD,
        requirements=[
            JobRequirementInput(
                requirement_key=requirement_key,
                description=(
                    "At least 5 years of project "
                    "management experience"
                ),
                priority=priority,
                category="EXPERIENCE",
                blocking=blocking,
                evidence_text=evidence_text,
            ),
        ],
    )


def test_valid_grounded_extraction_is_accepted() -> None:
    validator = JDExtractionValidator()

    extraction = build_extraction()

    result = validator.validate(
        extraction
    )

    assert result is extraction

    assert (
        result.requirements[0]
        .requirement_key
        == "project_management_experience"
    )


def test_fabricated_evidence_is_rejected() -> None:
    validator = JDExtractionValidator()

    extraction = build_extraction(
        evidence_text=(
            "Minimum 10 years of SAP "
            "experience required"
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "evidence_text must be a verbatim "
            "contiguous substring"
        ),
    ):
        validator.validate(
            extraction
        )


def test_semantically_similar_but_non_verbatim_evidence_is_rejected() -> None:
    validator = JDExtractionValidator()

    extraction = build_extraction(
        evidence_text=(
            "Minimum 5 years project "
            "management experience"
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "evidence_text must be a verbatim "
            "contiguous substring"
        ),
    ):
        validator.validate(
            extraction
        )


def test_non_contiguous_evidence_is_rejected() -> None:
    validator = JDExtractionValidator()

    extraction = build_extraction(
        evidence_text=(
            "Candidates at least 5 years "
            "project management experience"
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "evidence_text must be a verbatim "
            "contiguous substring"
        ),
    ):
        validator.validate(
            extraction
        )


def test_missing_evidence_is_rejected() -> None:
    validator = JDExtractionValidator()

    extraction = build_extraction(
        evidence_text=None
    )

    with pytest.raises(
        ValueError,
        match=(
            "requires non-empty evidence_text"
        ),
    ):
        validator.validate(
            extraction
        )


def test_empty_evidence_is_rejected() -> None:
    validator = JDExtractionValidator()

    extraction = build_extraction(
        evidence_text=""
    )

    with pytest.raises(
        ValueError,
        match=(
            "requires non-empty evidence_text"
        ),
    ):
        validator.validate(
            extraction
        )


def test_requirement_key_must_be_snake_case() -> None:
    validator = JDExtractionValidator()

    extraction = build_extraction(
        requirement_key=(
            "Project Management"
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "requirement_key must use "
            "lowercase snake_case"
        ),
    ):
        validator.validate(
            extraction
        )


def test_blocking_nice_to_have_is_rejected() -> None:
    validator = JDExtractionValidator()

    extraction = build_extraction(
        priority="NICE_TO_HAVE",
        blocking=True,
    )

    with pytest.raises(
        ValueError,
        match=(
            "blocking=True is only valid "
            "for MUST_HAVE"
        ),
    ):
        validator.validate(
            extraction
        )


def test_blocking_must_have_is_allowed() -> None:
    validator = JDExtractionValidator()

    extraction = build_extraction(
        priority="MUST_HAVE",
        blocking=True,
    )

    result = validator.validate(
        extraction
    )

    assert result.requirements[0].blocking is True