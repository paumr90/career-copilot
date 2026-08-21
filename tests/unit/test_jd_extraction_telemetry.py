import pytest
from pydantic import ValidationError

from app.modules.opportunities.schemas import (
    JDExtractionProposal,
    JDExtractionProviderResult,
    JDExtractionTelemetry,
)


def test_openai_telemetry_accepts_usage_metadata() -> None:
    telemetry = JDExtractionTelemetry(
        provider_name="openai",
        provider_version="0.1",
        model_name="test-model",
        response_id="resp_test_123",
        input_tokens=100,
        output_tokens=25,
        total_tokens=125,
        latency_ms=350.5,
    )

    assert telemetry.provider_name == "openai"

    assert (
        telemetry.model_name
        == "test-model"
    )

    assert (
        telemetry.response_id
        == "resp_test_123"
    )

    assert telemetry.input_tokens == 100
    assert telemetry.output_tokens == 25
    assert telemetry.total_tokens == 125
    assert telemetry.latency_ms == 350.5


def test_local_telemetry_can_omit_api_metrics() -> None:
    telemetry = JDExtractionTelemetry(
        provider_name="deterministic_local",
        provider_version="0.1",
    )

    assert telemetry.model_name is None
    assert telemetry.response_id is None
    assert telemetry.input_tokens is None
    assert telemetry.output_tokens is None
    assert telemetry.total_tokens is None
    assert telemetry.latency_ms is None


def test_inconsistent_token_total_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "total_tokens must equal "
            "input_tokens"
        ),
    ):
        JDExtractionTelemetry(
            provider_name="openai",
            provider_version="0.1",
            input_tokens=100,
            output_tokens=25,
            total_tokens=999,
        )


def test_negative_token_count_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
    ):
        JDExtractionTelemetry(
            provider_name="openai",
            provider_version="0.1",
            input_tokens=-1,
        )


def test_telemetry_rejects_unknown_fields() -> None:
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        JDExtractionTelemetry.model_validate(
            {
                "provider_name": "openai",
                "provider_version": "0.1",
                "secret_api_key": "must-not-exist",
            }
        )


def test_provider_result_contains_proposal_and_telemetry() -> None:
    proposal = JDExtractionProposal()

    telemetry = JDExtractionTelemetry(
        provider_name="openai",
        provider_version="0.1",
        model_name="test-model",
    )

    result = JDExtractionProviderResult(
        proposal=proposal,
        telemetry=telemetry,
    )

    assert result.proposal == proposal

    assert (
        result.telemetry.provider_name
        == "openai"
    )

    assert (
        result.telemetry.model_name
        == "test-model"
    )