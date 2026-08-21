from app.domain.enums import (
    RequirementCategory,
    RequirementPriority,
)
from app.modules.opportunities.deterministic_extractor import (
    DeterministicJDExtractionProvider,
)
from app.modules.opportunities.extraction import (
    JDExtractionValidator,
)
from app.modules.opportunities.extraction_request import (
    JDExtractionRequestBuilder,
)
from app.modules.opportunities.schemas import (
    RawJobDescriptionInput,
)


RAW_JD = (
    "We are hiring a Program Manager. "
    "Candidates must have at least 5 years "
    "of project management experience. "
    "Experience with cloud platforms is preferred. "
    "Knowledge of SQL. "
    "We offer private health insurance."
)


def build_raw_job(
    raw_text: str = RAW_JD,
) -> RawJobDescriptionInput:
    return RawJobDescriptionInput(
        company="Example Company",
        role_title="Program Manager",
        location="Barcelona",
        raw_text=raw_text,
        source_url=(
            "https://example.com/jobs/"
            "program-manager"
        ),
    )


def extract(
    raw_text: str = RAW_JD,
):
    raw_job = build_raw_job(
        raw_text=raw_text
    )

    request = (
        JDExtractionRequestBuilder()
        .build(
            raw_job=raw_job
        )
    )

    provider = (
        DeterministicJDExtractionProvider()
    )

    proposal = provider.extract(
        request=request
    )

    return raw_job, proposal


def test_provider_identifies_explicit_requirements() -> None:
    _, proposal = extract()

    assert len(
        proposal.requirements
    ) == 3

    priorities = [
        requirement.priority
        for requirement
        in proposal.requirements
    ]

    assert priorities == [
        RequirementPriority.MUST_HAVE,
        RequirementPriority.NICE_TO_HAVE,
        RequirementPriority.SECONDARY,
    ]


def test_provider_classifies_categories_conservatively() -> None:
    _, proposal = extract()

    categories = [
        requirement.category
        for requirement
        in proposal.requirements
    ]

    assert categories == [
        RequirementCategory.EXPERIENCE,
        RequirementCategory.TECHNOLOGY,
        RequirementCategory.TECHNOLOGY,
    ]


def test_provider_preserves_verbatim_evidence() -> None:
    raw_job, proposal = extract()

    for requirement in proposal.requirements:
        assert (
            requirement.evidence_text
            in raw_job.raw_text
        )


def test_provider_output_passes_grounding_validator() -> None:
    raw_job, proposal = extract()

    validator = JDExtractionValidator()

    validated = (
        validator.validate_proposal(
            raw_job=raw_job,
            proposal=proposal,
        )
    )

    assert len(
        validated.requirements
    ) == 3


def test_provider_does_not_extract_neutral_benefit_text() -> None:
    _, proposal = extract()

    descriptions = [
        requirement.description.lower()
        for requirement
        in proposal.requirements
    ]

    assert not any(
        "health insurance"
        in description
        for description in descriptions
    )


def test_provider_does_not_extract_negated_requirement() -> None:
    raw_text = (
        "We are hiring a Program Manager. "
        "SAP experience is not required."
    )

    _, proposal = extract(
        raw_text=raw_text
    )

    assert proposal.requirements == []


def test_provider_does_not_treat_plain_responsibility_as_requirement() -> None:
    raw_text = (
        "You will lead cross-functional "
        "transformation projects."
    )

    _, proposal = extract(
        raw_text=raw_text
    )

    assert proposal.requirements == []


def test_provider_never_sets_blocking_true() -> None:
    _, proposal = extract()

    assert all(
        requirement.blocking is False
        for requirement
        in proposal.requirements
    )


def test_provider_is_deterministic() -> None:
    _, first = extract()
    _, second = extract()

    assert first == second


def test_requirement_keys_are_unique_and_snake_case() -> None:
    _, proposal = extract()

    keys = [
        requirement.requirement_key
        for requirement
        in proposal.requirements
    ]

    assert len(keys) == len(
        set(keys)
    )

    assert all(
        key == key.lower()
        and " " not in key
        for key in keys
    )