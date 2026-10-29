"""Opt-in semantic regression runner. Uses synthetic evidence; live mode costs API tokens."""

import argparse
import json
import uuid
from pathlib import Path

from app.domain.rules.semantic_assessment import SemanticAssessmentPolicy
from app.modules.fit.assessment import RequirementAssessmentValidator
from app.modules.fit.schemas import (
    CareerEvidenceCandidate,
    EvidenceRankingResult,
    RankedEvidenceCandidate,
    SemanticAssessmentEvidence,
    SemanticAssessmentRequest,
    SemanticAssessmentRequirement,
)


def build_case_request(case):
    evidence = SemanticAssessmentEvidence(
        profile_fact_id=uuid.uuid5(
            uuid.NAMESPACE_URL, "career-copilot/synthetic/" + case["case_id"]
        ),
        fact_type="employment",
        tier="PRIMARY",
        subject="Synthetic work evidence",
        value_json={"responsibilities": [case["evidence"]]},
        relevance_score=1,
        matched_terms=[],
    )
    return SemanticAssessmentRequest(
        semantic_rule_version=SemanticAssessmentPolicy().version,
        retrieval_rule_version="synthetic",
        ranking_rule_version="synthetic",
        requirement=SemanticAssessmentRequirement(
            requirement_key=case["case_id"],
            description=case["requirement"],
            category="EXPERIENCE",
            priority="SECONDARY",
            blocking=False,
            evidence_text=case["requirement"],
        ),
        ranked_evidence=[evidence],
    )


def evaluate_case(case, provider):
    # Expected labels are kept outside the provider request.
    request = build_case_request(case)
    result = provider.propose_with_telemetry(request=request)
    ranking = EvidenceRankingResult(
        requirement_key=request.requirement.requirement_key,
        requirement_category=request.requirement.category,
        retrieval_rule_version="synthetic",
        ranking_rule_version="synthetic",
        ranking_method="synthetic_fixed_evidence",
        total_candidate_count=1,
        ranked_candidates=[
            RankedEvidenceCandidate(
                candidate=CareerEvidenceCandidate(
                    **item.model_dump(exclude={"relevance_score", "matched_terms"})
                ),
                relevance_score=1,
            )
            for item in request.ranked_evidence
        ],
    )
    assessment = RequirementAssessmentValidator().validate(
        proposal=result.proposal, ranking_result=ranking
    )
    return {
        "case_id": case["case_id"],
        "expected_status": case["expected_status"],
        "actual_status": assessment.match_status.value,
        "passed": assessment.match_status.value == case["expected_status"],
        "result": result.model_dump(mode="json"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="tests/fixtures/semantic_cases.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--live", action="store_true", help="Authorize real model calls")
    args = parser.parse_args()
    if not args.live:
        parser.error("--live is required to make API calls")
    from app.config import settings
    from app.modules.fit.openai_assessor import OpenAISemanticAssessmentProvider

    provider = OpenAISemanticAssessmentProvider(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    rows = []
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        try:
            row = evaluate_case(case, provider)
        except Exception as error:  # noqa: BLE001 - persist per-case failures and continue the diagnostic run
            row = {"case_id": case["case_id"], "passed": False, "error": str(error)}
        rows.append(row)
        output.write_text(
            json.dumps(
                {
                    "model": settings.llm_model,
                    "semantic_rule_version": SemanticAssessmentPolicy().version,
                    "cases": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(row["case_id"], "PASS" if row["passed"] else "FAIL", flush=True)
    raise SystemExit(0 if all(row["passed"] for row in rows) else 1)


if __name__ == "__main__":
    main()
