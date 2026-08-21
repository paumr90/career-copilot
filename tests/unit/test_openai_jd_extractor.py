from types import SimpleNamespace

import pytest

from app.modules.opportunities.extraction_request import (
    JDExtractionRequestBuilder,
)
from app.modules.opportunities.openai_extractor import (
    OpenAIJDExtractionProvider,
)
from app.modules.opportunities.providers import (
    JDExtractionProvider,
)
from app.modules.opportunities.schemas import (
    JDExtractionProposal,
    JDExtractionProviderResult,
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


def build_request():
    return (
        JDExtractionRequestBuilder()
        .build(
            raw_job=build_raw_job()
        )
    )


def build_proposal() -> JDExtractionProposal:
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


class FakeClock:
    def __init__(
        self,
        *values: float,
    ) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(
            self._values
        )


class FakeResponses:
    def __init__(
        self,
        *,
        output_parsed,
        response_id: str | None = (
            "resp_test_123"
        ),
        model: str | None = (
            "test-model-resolved"
        ),
        usage=None,
    ) -> None:
        self.output_parsed = output_parsed
        self.response_id = response_id
        self.model = model

        self.usage = (
            usage
            if usage is not None
            else SimpleNamespace(
                input_tokens=120,
                output_tokens=30,
                total_tokens=150,
            )
        )

        self.last_call = None

    def parse(
        self,
        **kwargs,
    ):
        self.last_call = kwargs

        return SimpleNamespace(
            output_parsed=(
                self.output_parsed
            ),
            id=self.response_id,
            model=self.model,
            usage=self.usage,
        )


class FakeOpenAIClient:
    def __init__(
        self,
        *,
        output_parsed,
        response_id: str | None = (
            "resp_test_123"
        ),
        model: str | None = (
            "test-model-resolved"
        ),
        usage=None,
    ) -> None:
        self.responses = FakeResponses(
            output_parsed=output_parsed,
            response_id=response_id,
            model=model,
            usage=usage,
        )


def build_provider(
    *,
    output_parsed=None,
    response_id: str | None = (
        "resp_test_123"
    ),
    response_model: str | None = (
        "test-model-resolved"
    ),
    usage=None,
    clock=None,
):
    if output_parsed is None:
        output_parsed = build_proposal()

    client = FakeOpenAIClient(
        output_parsed=output_parsed,
        response_id=response_id,
        model=response_model,
        usage=usage,
    )

    kwargs = {
        "model": "test-model",
        "client": client,
    }

    if clock is not None:
        kwargs["clock"] = clock

    provider = OpenAIJDExtractionProvider(
        **kwargs
    )

    return provider, client


def test_provider_implements_protocol() -> None:
    provider, _ = build_provider()

    assert isinstance(
        provider,
        JDExtractionProvider,
    )

    assert (
        provider.provider_name
        == "openai"
    )

    assert (
        provider.provider_version
        == "0.1"
    )

    assert (
        provider.model_name
        == "test-model"
    )


def test_provider_uses_structured_output_contract() -> None:
    provider, client = build_provider()

    request = build_request()

    result = provider.extract(
        request=request
    )

    assert result == build_proposal()

    call = client.responses.last_call

    assert call is not None

    assert (
        call["model"]
        == "test-model"
    )

    assert (
        call["text_format"]
        is JDExtractionProposal
    )


def test_provider_disables_response_storage() -> None:
    provider, client = build_provider()

    provider.extract(
        request=build_request()
    )

    call = client.responses.last_call

    assert call is not None

    assert call["store"] is False


def test_provider_sends_governed_request() -> None:
    provider, client = build_provider()

    request = build_request()

    provider.extract(
        request=request
    )

    call = client.responses.last_call

    messages = call["input"]

    assert len(messages) == 2

    assert (
        messages[0]["role"]
        == "developer"
    )

    assert (
        messages[1]["role"]
        == "user"
    )

    developer_prompt = (
        messages[0]["content"]
    )

    user_prompt = (
        messages[1]["content"]
    )

    assert (
        "UNTRUSTED DATA"
        in developer_prompt
    )

    assert (
        '"version": "0.1"'
        in developer_prompt
    )

    assert (
        request.raw_text
        in user_prompt
    )


def test_provider_never_receives_source_url() -> None:
    provider, client = build_provider()

    request = build_request()

    provider.extract(
        request=request
    )

    call = client.responses.last_call

    complete_prompt = str(
        call["input"]
    )

    assert (
        "https://example.com"
        not in complete_prompt
    )


def test_provider_returns_deep_copy() -> None:
    original = build_proposal()

    client = FakeOpenAIClient(
        output_parsed=original
    )

    provider = OpenAIJDExtractionProvider(
        model="test-model",
        client=client,
    )

    result = provider.extract(
        request=build_request()
    )

    assert result == original
    assert result is not original

    assert (
        result.requirements[0]
        is not original.requirements[0]
    )


def test_provider_returns_telemetry_envelope() -> None:
    provider, _ = build_provider(
        clock=FakeClock(
            10.0,
            10.25,
        )
    )

    result = (
        provider.extract_with_telemetry(
            request=build_request()
        )
    )

    assert isinstance(
        result,
        JDExtractionProviderResult,
    )

    assert (
        result.proposal
        == build_proposal()
    )

    telemetry = result.telemetry

    assert (
        telemetry.provider_name
        == "openai"
    )

    assert (
        telemetry.provider_version
        == "0.1"
    )

    assert (
        telemetry.model_name
        == "test-model-resolved"
    )

    assert (
        telemetry.response_id
        == "resp_test_123"
    )

    assert telemetry.input_tokens == 120
    assert telemetry.output_tokens == 30
    assert telemetry.total_tokens == 150

    assert telemetry.latency_ms == 250.0


def test_missing_usage_is_allowed() -> None:
    provider, _ = build_provider(
        usage=SimpleNamespace(
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
        ),
        clock=FakeClock(
            5.0,
            5.1,
        ),
    )

    result = (
        provider.extract_with_telemetry(
            request=build_request()
        )
    )

    telemetry = result.telemetry

    assert telemetry.input_tokens is None
    assert telemetry.output_tokens is None
    assert telemetry.total_tokens is None


def test_response_model_falls_back_to_requested_model() -> None:
    provider, _ = build_provider(
        response_model=None,
        clock=FakeClock(
            1.0,
            1.0,
        ),
    )

    result = (
        provider.extract_with_telemetry(
            request=build_request()
        )
    )

    assert (
        result.telemetry.model_name
        == "test-model"
    )


def test_rule_version_mismatch_is_rejected_before_api_call() -> None:
    provider, client = build_provider()

    request = build_request().model_copy(
        update={
            "extraction_rule_version": (
                "999.0"
            )
        }
    )

    with pytest.raises(
        ValueError,
        match=(
            "request rule version does not "
            "match the provider policy version"
        ),
    ):
        provider.extract(
            request=request
        )

    assert (
        client.responses.last_call
        is None
    )


def test_missing_parsed_output_is_rejected() -> None:
    client = FakeOpenAIClient(
        output_parsed=None
    )

    provider = OpenAIJDExtractionProvider(
        model="test-model",
        client=client,
    )

    with pytest.raises(
        ValueError,
        match=(
            "did not contain a parsed "
            "JDExtractionProposal"
        ),
    ):
        provider.extract(
            request=build_request()
        )


def test_real_client_requires_api_key() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "OpenAI API key is required"
        ),
    ):
        OpenAIJDExtractionProvider(
            model="test-model",
        )


def test_empty_model_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "model cannot be empty"
        ),
    ):
        OpenAIJDExtractionProvider(
            model="   ",
            client=FakeOpenAIClient(
                output_parsed=(
                    build_proposal()
                )
            ),
        )