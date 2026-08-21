import pytest
from pydantic import ValidationError

from app.modules.opportunities.extraction import (
    JDExtractionValidator,
)
from app.modules.opportunities.schemas import (
    JDExtractionProposal,
    JobDescriptionInput,
    JobRequirementInput,
    RawJobDescriptionInput,
)


RAW_JD = (
    "We are looking for a Program Manager. "
    "Candidates must have at least 5 years "
    "of project management experience. "
    "Experience with cloud platforms is preferred. "
    "The role is hybrid in Barcelona."
)


def build_requirement(
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
) -> JobRequirementInput:
    return JobRequirementInput(
        requirement_key=requirement_key,
        description=(
            "At least 5 years of project "
            "management experience"
        ),
        priority=priority,
        category="EXPERIENCE",
        blocking=blocking,
        evidence_text=evidence_text,
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
            build_requirement(
                requirement_key=(
                    requirement_key
                ),
                priority=priority,
                blocking=blocking,
                evidence_text=evidence_text,
            )
        ],
    )


def build_raw_job() -> RawJobDescriptionInput:
    return RawJobDescriptionInput(
        company="Example Company",
        role_title="Program Manager",
        location="Barcelona",
        raw_text=RAW_JD,
        source_url=(
            "https://example.com/jobs/program-manager"
        ),
    )


def build_proposal(
    *,
    evidence_text: str | None = (
        "must have at least 5 years "
        "of project management experience"
    ),
) -> JDExtractionProposal:
    return JDExtractionProposal(
        requirements=[
            build_requirement(
                evidence_text=evidence_text
            )
        ]
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


def test_valid_proposal_becomes_validated_job_description() -> None:
    validator = JDExtractionValidator()

    raw_job = build_raw_job()
    proposal = build_proposal()

    result = validator.validate_proposal(
        raw_job=raw_job,
        proposal=proposal,
    )

    assert isinstance(
        result,
        JobDescriptionInput,
    )

    assert result.company == raw_job.company
    assert result.role_title == raw_job.role_title
    assert result.location == raw_job.location
    assert result.raw_text == raw_job.raw_text

    assert len(result.requirements) == 1

    assert (
        result.requirements[0]
        .requirement_key
        == "project_management_experience"
    )


def test_proposal_is_validated_against_trusted_raw_text() -> None:
    validator = JDExtractionValidator()

    raw_job = build_raw_job()

    proposal = build_proposal(
        evidence_text=(
            "Minimum 10 years SAP "
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
        validator.validate_proposal(
            raw_job=raw_job,
            proposal=proposal,
        )


def test_provider_contract_cannot_override_raw_job_fields() -> None:
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        JDExtractionProposal.model_validate(
            {
                "requirements": [],
                "company": "Injected Company",
                "role_title": "Injected Role",
                "raw_text": (
                    "Injected Job Description"
                ),
            }
        )


def test_requirement_contract_rejects_unknown_fields() -> None:
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        JobRequirementInput.model_validate(
            {
                "requirement_key": (
                    "project_management"
                ),
                "description": (
                    "Project management experience"
                ),
                "priority": "MUST_HAVE",
                "category": "EXPERIENCE",
                "blocking": False,
                "evidence_text": (
                    "project management experience"
                ),
                "candidate_fit": "MATCH",
            }
        )


def test_validated_requirements_are_deep_copied() -> None:
    validator = JDExtractionValidator()

    raw_job = build_raw_job()
    proposal = build_proposal()

    result = validator.validate_proposal(
        raw_job=raw_job,
        proposal=proposal,
    )

    original_description = (
        result.requirements[0].description
    )

    proposal.requirements[0].description = (
        "Provider mutated the proposal"
    )

    assert (
        result.requirements[0].description
        == original_description
    )