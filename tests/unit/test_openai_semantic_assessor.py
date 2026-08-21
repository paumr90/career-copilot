import uuid
from types import SimpleNamespace

import pytest

from app.domain.enums import (
    EvidenceTier,
    ProfileFactType,
    RequirementCategory,
    RequirementPriority,
)
from app.modules.fit.openai_assessor import (
    OpenAISemanticAssessmentProvider,
)
from app.modules.fit.providers import (
    SemanticAssessmentProvider,
)
from app.modules.fit.schemas import (
    ProfileEvidenceReference,
    RequirementAssessmentProposal,
    SemanticAssessmentEvidence,
    SemanticAssessmentRequest,
    SemanticAssessmentRequirement,
)
from app.modules.fit.telemetry import (
    SemanticAssessmentProviderResult,
)


EVIDENCE_ID = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)


def build_request() -> SemanticAssessmentRequest:
    return SemanticAssessmentRequest(
        semantic_rule_version="0.1",
        retrieval_rule_version="0.1",
        ranking_rule_version="0.1",
        requirement=(
            SemanticAssessmentRequirement(
                requirement_key=(
                    "jira_experience"
                ),
                description=(
                    "Experience using Jira"
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
            SemanticAssessmentEvidence(
                profile_fact_id=EVIDENCE_ID,
                fact_type=(
                    ProfileFactType.SKILL
                ),
                tier=EvidenceTier.PRIMARY,
                subject=(
                    "Project management tools"
                ),
                value_json={
                    "areas": [
                        "Jira",
                    ],
                    "level": "EXPERIENCE",
                },
                relevance_score=10.0,
                matched_terms=[
                    "jira",
                ],
            )
        ],
    )


def build_proposal(
) -> RequirementAssessmentProposal:
    return RequirementAssessmentProposal(
        requirement_key="jira_experience",
        proposed_status="MATCH",
        evidence=[
            ProfileEvidenceReference(
                profile_fact_id=EVIDENCE_ID,
                note=(
                    "Supplied Career Master "
                    "evidence explicitly includes "
                    "Jira."
                ),
            )
        ],
        rationale=(
            "The supplied primary evidence "
            "directly supports Jira experience."
        ),
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
            "resp_semantic_test"
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
                input_tokens=200,
                output_tokens=40,
                total_tokens=240,
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
            "resp_semantic_test"
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
        "resp_semantic_test"
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

    provider = (
        OpenAISemanticAssessmentProvider(
            **kwargs
        )
    )

    return provider, client


def test_provider_implements_protocol() -> None:
    provider, _ = build_provider()

    assert isinstance(
        provider,
        SemanticAssessmentProvider,
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

    result = provider.propose(
        request=build_request()
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
        is RequirementAssessmentProposal
    )


def test_provider_disables_response_storage() -> None:
    provider, client = build_provider()

    provider.propose(
        request=build_request()
    )

    call = client.responses.last_call

    assert call is not None

    assert call["store"] is False


def test_provider_sends_governed_request() -> None:
    provider, client = build_provider()

    request = build_request()

    provider.propose(
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
        "Do not calculate a Fit Score"
        in developer_prompt
    )

    assert (
        str(EVIDENCE_ID)
        in user_prompt
    )

    assert "Jira" in user_prompt


def test_provider_returns_deep_copy() -> None:
    original = build_proposal()

    client = FakeOpenAIClient(
        output_parsed=original
    )

    provider = (
        OpenAISemanticAssessmentProvider(
            model="test-model",
            client=client,
        )
    )

    result = provider.propose(
        request=build_request()
    )

    assert result == original
    assert result is not original

    assert (
        result.evidence[0]
        is not original.evidence[0]
    )


def test_provider_returns_telemetry_envelope() -> None:
    provider, _ = build_provider(
        clock=FakeClock(
            10.0,
            10.25,
        )
    )

    result = (
        provider.propose_with_telemetry(
            request=build_request()
        )
    )

    assert isinstance(
        result,
        SemanticAssessmentProviderResult,
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
        == "resp_semantic_test"
    )

    assert telemetry.input_tokens == 200
    assert telemetry.output_tokens == 40
    assert telemetry.total_tokens == 240

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
        provider.propose_with_telemetry(
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
        provider.propose_with_telemetry(
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
            "semantic_rule_version": (
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
        provider.propose(
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

    provider = (
        OpenAISemanticAssessmentProvider(
            model="test-model",
            client=client,
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "did not contain a parsed "
            "RequirementAssessmentProposal"
        ),
    ):
        provider.propose(
            request=build_request()
        )


def test_real_client_requires_api_key() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "OpenAI API key is required"
        ),
    ):
        OpenAISemanticAssessmentProvider(
            model="test-model",
        )


def test_empty_model_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "model cannot be empty"
        ),
    ):
        OpenAISemanticAssessmentProvider(
            model="   ",
            client=FakeOpenAIClient(
                output_parsed=(
                    build_proposal()
                )
            ),
        )


def test_invalid_token_total_is_rejected() -> None:
    provider, _ = build_provider(
        usage=SimpleNamespace(
            input_tokens=200,
            output_tokens=40,
            total_tokens=999,
        ),
        clock=FakeClock(
            1.0,
            1.1,
        ),
    )

    with pytest.raises(
        ValueError,
        match="total_tokens",
    ):
        provider.propose_with_telemetry(
            request=build_request()
        )