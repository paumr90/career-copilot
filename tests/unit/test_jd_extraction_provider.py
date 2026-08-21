import pytest

from app.modules.opportunities.extraction import (
    JDExtractionValidator,
)
from app.modules.opportunities.providers import (
    JDExtractionProvider,
    StaticJDExtractionProvider,
)
from app.modules.opportunities.schemas import (
    JDExtractionProposal,
    JobRequirementInput,
    RawJobDescriptionInput,
)


RAW_JD = (
    "We are looking for a Program Manager. "
    "Candidates must have at least 5 years "
    "of project management experience."
)


def build_raw_job() -> RawJobDescriptionInput:
    return RawJobDescriptionInput(
        company="Example Company",
        role_title="Program Manager",
        location="Barcelona",
        raw_text=RAW_JD,
        source_url=(
            "https://example.com/jobs/"
            "program-manager"
        ),
    )


def build_valid_proposal() -> JDExtractionProposal:
    return JDExtractionProposal(
        requirements=[
            JobRequirementInput(
                requirement_key=(
                    "project_management_experience"
                ),
                description=(
                    "At least 5 years of project "
                    "management experience"
                ),
                priority="MUST_HAVE",
                category="EXPERIENCE",
                blocking=False,
                evidence_text=(
                    "must have at least 5 years "
                    "of project management experience"
                ),
            )
        ]
    )


def test_static_provider_implements_protocol() -> None:
    provider = StaticJDExtractionProvider(
        proposal=JDExtractionProposal()
    )

    assert isinstance(
        provider,
        JDExtractionProvider,
    )

    assert provider.provider_name == (
        "static_local"
    )

    assert provider.provider_version == "0.1"


def test_static_provider_returns_deep_copy() -> None:
    proposal = build_valid_proposal()

    provider = StaticJDExtractionProvider(
        proposal=proposal
    )

    result = provider.extract(
        raw_job=build_raw_job()
    )

    assert result == proposal
    assert result is not proposal

    assert (
        result.requirements[0]
        is not proposal.requirements[0]
    )


def test_static_provider_does_not_modify_raw_job() -> None:
    provider = StaticJDExtractionProvider(
        proposal=build_valid_proposal()
    )

    raw_job = build_raw_job()

    before = raw_job.model_dump(
        mode="json"
    )

    provider.extract(
        raw_job=raw_job
    )

    after = raw_job.model_dump(
        mode="json"
    )

    assert after == before


def test_provider_output_remains_untrusted() -> None:
    fabricated_proposal = (
        JDExtractionProposal(
            requirements=[
                JobRequirementInput(
                    requirement_key=(
                        "sap_experience"
                    ),
                    description=(
                        "10 years of SAP "
                        "experience"
                    ),
                    priority="MUST_HAVE",
                    category="TECHNOLOGY",
                    blocking=False,
                    evidence_text=(
                        "10 years of SAP "
                        "experience required"
                    ),
                )
            ]
        )
    )

    provider = StaticJDExtractionProvider(
        proposal=fabricated_proposal
    )

    raw_job = build_raw_job()

    proposal = provider.extract(
        raw_job=raw_job
    )

    assert (
        proposal.requirements[0]
        .requirement_key
        == "sap_experience"
    )

    validator = JDExtractionValidator()

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