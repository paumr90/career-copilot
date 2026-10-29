from pydantic import ValidationError
import pytest

from app.modules.opportunities.extraction_request import (
    JDExtractionRequestBuilder,
)
from app.modules.opportunities.schemas import (
    JDExtractionRequest,
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


def test_builder_creates_extraction_request() -> None:
    builder = JDExtractionRequestBuilder()

    raw_job = build_raw_job()

    request = builder.build(
        raw_job=raw_job
    )

    assert isinstance(
        request,
        JDExtractionRequest,
    )

    assert (
        request.extraction_rule_version
        == "0.2"
    )

    assert request.company == raw_job.company

    assert (
        request.role_title
        == raw_job.role_title
    )

    assert (
        request.location
        == raw_job.location
    )

    assert (
        request.raw_text
        == raw_job.raw_text
    )


def test_request_does_not_expose_source_url() -> None:
    builder = JDExtractionRequestBuilder()

    request = builder.build(
        raw_job=build_raw_job()
    )

    payload = request.model_dump(
        mode="json"
    )

    assert "source_url" not in payload

    assert set(payload) == {
        "extraction_rule_version",
        "company",
        "role_title",
        "location",
        "raw_text",
    }


def test_builder_does_not_modify_raw_job() -> None:
    builder = JDExtractionRequestBuilder()

    raw_job = build_raw_job()

    before = raw_job.model_dump(
        mode="json"
    )

    builder.build(
        raw_job=raw_job
    )

    after = raw_job.model_dump(
        mode="json"
    )

    assert after == before


def test_extraction_request_rejects_extra_fields() -> None:
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        JDExtractionRequest.model_validate(
            {
                "extraction_rule_version": "0.1",
                "company": "Example Company",
                "role_title": "Program Manager",
                "location": "Barcelona",
                "raw_text": RAW_JD,
                "source_url": (
                    "https://example.com/private"
                ),
            }
        )