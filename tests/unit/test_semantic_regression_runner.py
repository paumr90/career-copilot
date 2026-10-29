import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.fit.regression import build_case_request, evaluate_case
from app.modules.fit.schemas import RequirementAssessmentProposal

CASES = json.loads(
    (Path(__file__).parents[1] / "fixtures/semantic_cases.json").read_text(encoding="utf-8")
)


class FakeProvider:
    def __init__(self, status="MATCH", key=None, invented_id=None):
        self.status, self.key, self.invented_id = status, key, invented_id

    def propose_with_telemetry(self, *, request):
        assert "expected_status" not in request.model_dump_json()
        proposal = RequirementAssessmentProposal(
            requirement_key=self.key or request.requirement.requirement_key,
            proposed_status=self.status,
            evidence=[]
            if self.status == "UNKNOWN"
            else [
                {"profile_fact_id": self.invented_id or request.ranked_evidence[0].profile_fact_id}
            ],
            rationale="Synthetic response for harness validation",
        )
        return SimpleNamespace(
            proposal=proposal,
            model_dump=lambda **kwargs: {"proposal": proposal.model_dump(mode="json")},
        )


def test_live_runner_detects_overstatement_without_relabeling():
    case = next(c for c in CASES if c["case_id"] == "model_use_only")
    result = evaluate_case(case, FakeProvider("PARTIAL_MATCH"))
    assert not result["passed"]
    assert result["actual_status"] == "PARTIAL_MATCH"


def test_live_runner_detects_excessive_caution():
    assert not evaluate_case(CASES[0], FakeProvider("UNKNOWN"))["passed"]


def test_live_runner_accepts_correct_grounded_label():
    assert evaluate_case(CASES[0], FakeProvider())["passed"]


def test_live_runner_rejects_wrong_key_and_unprovided_evidence():
    with pytest.raises(ValueError, match="requirement_key"):
        evaluate_case(CASES[0], FakeProvider(key="invented"))
    with pytest.raises(ValueError, match="ranked shortlist"):
        evaluate_case(CASES[0], FakeProvider(invented_id="11111111-1111-1111-1111-111111111111"))


def test_reference_cases_are_unique_and_cover_all_three_labels():
    assert len({c["case_id"] for c in CASES}) == len(CASES)
    assert {c["expected_status"] for c in CASES} == {"MATCH", "PARTIAL_MATCH", "UNKNOWN"}
    for case in CASES:
        assert build_case_request(case).requirement.description == case["requirement"]
