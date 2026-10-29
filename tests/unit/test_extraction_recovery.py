from copy import deepcopy

import pytest

from app.modules.opportunities.extraction_request import JDExtractionRequestBuilder
from app.modules.opportunities.extraction_workflow import extract_validated
from app.modules.opportunities.schemas import (
    JDExtractionProposal,
    JDExtractionProviderResult,
    RawJobDescriptionInput,
)


def exercise(quotes, checkpoints):
    raw = RawJobDescriptionInput(
        company="Synthetic", role_title="Engineer", raw_text="Must write Java services."
    )

    class Provider:
        def __init__(self):
            self.calls = []

        def extract_with_telemetry(self, **kwargs):
            self.calls.append(kwargs)
            quote = quotes[len(self.calls) - 1]
            return JDExtractionProviderResult(
                proposal=JDExtractionProposal(
                    requirements=[
                        {
                            "requirement_key": "java",
                            "description": "Write Java services",
                            "category": "TECHNOLOGY",
                            "criterion_type": "ESSENTIAL",
                            "classification_reason": "The source explicitly says Must.",
                            "priority": "MUST_HAVE",
                            "blocking": False,
                            "evidence_text": quote,
                        }
                    ]
                ),
                telemetry={
                    "provider_name": "fake",
                    "provider_version": "1",
                    "model_name": "fake",
                    "total_tokens": 10,
                    "input_tokens": 8,
                    "output_tokens": 2,
                    "latency_ms": 1,
                },
            )

    provider = Provider()

    def save(audit):
        checkpoints.append(deepcopy(audit))

    return extract_validated(
        raw_job=raw,
        request=JDExtractionRequestBuilder().build(raw_job=raw),
        provider=provider,
        write_audit=save,
    ), provider


def test_repair_preserves_failed_proposal_and_usage_before_second_call():
    checkpoints = []
    (job, _, attempts), provider = exercise(
        ["Must write Python", "Must write Java services."], checkpoints
    )
    assert len(provider.calls) == 2
    assert checkpoints[0]["status"] == "retry_pending"
    assert (
        checkpoints[0]["attempts"][0]["proposal"]["requirements"][0]["evidence_text"]
        == "Must write Python"
    )
    assert checkpoints[0]["attempts"][0]["telemetry"]["total_tokens"] == 10
    assert "verbatim" in provider.calls[1]["correction"]
    assert job.requirements[0].evidence_text == "Must write Java services."
    assert len(attempts) == 2


def test_two_invalid_proposals_stop_and_preserve_both():
    checkpoints = []
    with pytest.raises(ValueError, match="verbatim"):
        exercise(["invented", "also invented"], checkpoints)
    assert checkpoints[-1]["status"] == "failed"
    assert len(checkpoints[-1]["attempts"]) == 2


def test_valid_first_proposal_is_not_retried():
    checkpoints = []
    (_, _, attempts), provider = exercise(["Must write Java services."], checkpoints)
    assert len(provider.calls) == len(attempts) == 1


def test_provider_failure_is_audited_without_blind_retry():
    raw = RawJobDescriptionInput(
        company="Synthetic", role_title="Engineer", raw_text="Must write Java services."
    )
    checkpoints = []

    class BrokenProvider:
        def extract_with_telemetry(self, **kwargs):
            raise RuntimeError("connection unavailable")

    with pytest.raises(RuntimeError, match="connection unavailable"):
        extract_validated(
            raw_job=raw,
            request=JDExtractionRequestBuilder().build(raw_job=raw),
            provider=BrokenProvider(),
            write_audit=checkpoints.append,
        )
    assert checkpoints[-1]["status"] == "failed"
    assert len(checkpoints[-1]["attempts"]) == 1
    assert checkpoints[-1]["attempts"][0]["status"] == "provider_failed"


def test_unique_whitespace_difference_uses_literal_source_and_keeps_provider_quote():
    checkpoints = []
    (job, result, attempts), provider = exercise(["Must\nwrite Java services."], checkpoints)
    assert len(provider.calls) == 1
    assert result.proposal.requirements[0].evidence_text == "Must\nwrite Java services."
    assert job.requirements[0].evidence_text == "Must write Java services."
    assert attempts[0]["quote_repairs"][0]["provider_quote"] == "Must\nwrite Java services."
    assert (
        attempts[0]["validated_proposal"]["requirements"][0]["evidence_text"]
        == "Must write Java services."
    )


@pytest.mark.parametrize(
    "source,quote",
    [
        ("Barcelona. Hybrid work.", "Barcelona (Hybrid)"),
        ("Java services", "Java, services"),
        ("Java  services; Java\nservices", "Java services"),
    ],
)
def test_spacing_recovery_never_invents_words_punctuation_or_chooses_ambiguous_span(source, quote):
    from app.modules.opportunities.extraction_workflow import restore_literal_whitespace

    proposal = JDExtractionProposal(
        requirements=[
            {
                "requirement_key": "test",
                "description": "Test",
                "category": "OTHER",
                "priority": "SECONDARY",
                "evidence_text": quote,
            }
        ]
    )
    restored, repairs = restore_literal_whitespace(proposal, source)
    assert not repairs
    assert restored.requirements[0].evidence_text == quote


def test_repair_feedback_can_omit_metadata_only_requirement_without_rewriting_source():
    checkpoints = []
    (_, _, _), provider = exercise(["Barcelona (Hybrid)", "Must write Java services."], checkpoints)
    assert "supported ONLY by metadata" in provider.calls[1]["correction"]
    assert "omit that unsupported criterion" in provider.calls[1]["correction"]
