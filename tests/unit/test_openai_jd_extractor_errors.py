import httpx
import pytest

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    RateLimitError,
)

from app.modules.opportunities.errors import (
    JDExtractionAPIError,
    JDExtractionConnectionError,
    JDExtractionRateLimitError,
    JDExtractionTimeoutError,
)
from app.modules.opportunities.extraction_request import (
    JDExtractionRequestBuilder,
)
from app.modules.opportunities.openai_extractor import (
    OpenAIJDExtractionProvider,
)
from app.modules.opportunities.schemas import (
    RawJobDescriptionInput,
)


RAW_JD = (
    "Candidates must have project "
    "management experience."
)


def build_request():
    raw_job = RawJobDescriptionInput(
        company="Example Company",
        role_title="Program Manager",
        location="Barcelona",
        raw_text=RAW_JD,
    )

    return (
        JDExtractionRequestBuilder()
        .build(
            raw_job=raw_job
        )
    )


def build_http_request() -> httpx.Request:
    return httpx.Request(
        "POST",
        "https://api.openai.com/v1/responses",
    )


class FailingResponses:
    def __init__(
        self,
        error: Exception,
    ) -> None:
        self.error = error

    def parse(
        self,
        **kwargs,
    ):
        _ = kwargs
        raise self.error


class FailingClient:
    def __init__(
        self,
        error: Exception,
    ) -> None:
        self.responses = FailingResponses(
            error
        )


def build_provider(
    error: Exception,
) -> OpenAIJDExtractionProvider:
    return OpenAIJDExtractionProvider(
        model="test-model",
        client=FailingClient(
            error
        ),
    )


def test_timeout_is_normalized() -> None:
    provider = build_provider(
        APITimeoutError(
            build_http_request()
        )
    )

    with pytest.raises(
        JDExtractionTimeoutError,
        match="timed out",
    ):
        provider.extract(
            request=build_request()
        )


def test_connection_error_is_normalized() -> None:
    provider = build_provider(
        APIConnectionError(
            request=build_http_request()
        )
    )

    with pytest.raises(
        JDExtractionConnectionError,
        match="could not be reached",
    ):
        provider.extract(
            request=build_request()
        )


def test_rate_limit_is_normalized() -> None:
    request = build_http_request()

    response = httpx.Response(
        status_code=429,
        request=request,
        headers={
            "x-request-id": (
                "req_rate_limit_test"
            )
        },
    )

    provider = build_provider(
        RateLimitError(
            "Rate limited",
            response=response,
            body=None,
        )
    )

    with pytest.raises(
        JDExtractionRateLimitError,
        match="rate limited",
    ):
        provider.extract(
            request=build_request()
        )


def test_other_api_status_is_normalized() -> None:
    request = build_http_request()

    response = httpx.Response(
        status_code=500,
        request=request,
        headers={
            "x-request-id": (
                "req_server_error_test"
            )
        },
    )

    provider = build_provider(
        APIStatusError(
            "Server error",
            response=response,
            body=None,
        )
    )

    with pytest.raises(
        JDExtractionAPIError,
        match="status 500",
    ):
        provider.extract(
            request=build_request()
        )


def test_negative_max_retries_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "max_retries cannot be negative"
        ),
    ):
        OpenAIJDExtractionProvider(
            model="test-model",
            max_retries=-1,
            client=FailingClient(
                RuntimeError("unused")
            ),
        )