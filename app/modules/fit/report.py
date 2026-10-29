"""User-facing fit report: coverage and unresolved requirements accompany every score."""

from app.domain.enums import MatchStatus
from app.domain.rules.fit_scoring import FitScoringPolicy
from app.modules.fit.compatibility import is_compatibility_requirement
from app.modules.fit.schemas import FitResult, FitScoringRequirement, RequirementAssessment
from app.modules.opportunities.models import JobRequirement


def build_fit_report(
    *,
    result: FitResult,
    requirements: list[JobRequirement],
    assessments: list[RequirementAssessment],
    minimum_coverage: float = 80.0,
) -> dict:
    if not 0 <= minimum_coverage <= 100:
        raise ValueError("minimum_coverage must be between 0 and 100.")
    by_key = {item.requirement_key: item for item in requirements}
    if (
        len(by_key) != len(requirements)
        or len({item.requirement_key for item in assessments}) != len(assessments)
        or {item.requirement_key for item in assessments} != set(by_key)
    ):
        raise ValueError("Report assessments must exactly match the requirements.")
    condition_keys = {
        item.requirement_key for item in requirements if is_compatibility_requirement(item)
    }
    professional_assessments = [
        item for item in assessments if item.requirement_key not in condition_keys
    ]
    professional_result = FitScoringPolicy().evaluate(
        [
            FitScoringRequirement(
                requirement_key=item.requirement_key,
                priority=by_key[item.requirement_key].priority,
                blocking=by_key[item.requirement_key].blocking,
                assessment=item,
            )
            for item in professional_assessments
        ]
    )
    conditions = [
        {
            "requirement_key": item.requirement_key,
            "status": item.match_status.value,
            "priority": by_key[item.requirement_key].priority,
            "blocking": by_key[item.requirement_key].blocking,
            "reason": item.rationale,
        }
        for item in assessments
        if item.requirement_key in condition_keys
    ]
    unknowns = [
        {
            "requirement_key": item.requirement_key,
            "description": by_key[item.requirement_key].description,
            "priority": by_key[item.requirement_key].priority,
            "reason": item.rationale,
            "next_action": "Verify the source facts and selected evidence; ask for missing information.",
        }
        for item in assessments
        if item.match_status == MatchStatus.UNKNOWN
    ]
    pending_conditions = any(item["status"] != "MATCH" for item in conditions)
    provisional = (
        professional_result.coverage_percent < minimum_coverage
        or bool(unknowns)
        or pending_conditions
    )
    decision = professional_result.recommendation.value
    if result.blocking_gap_keys:
        decision = "NO_APPLY"
    elif pending_conditions and decision == "APPLY":
        decision = "REVIEW"
    if provisional and decision == "APPLY":
        decision = "REVIEW"
    critical_unknowns = [
        item
        for item in unknowns
        if by_key[item["requirement_key"]].blocking
        or by_key[item["requirement_key"]].priority == "MUST_HAVE"
    ]
    evidence_insufficient = (
        bool(critical_unknowns) or professional_result.coverage_percent < minimum_coverage
    )
    return {
        "assessment_summary": {
            "status": "INSUFFICIENT_EVIDENCE"
            if evidence_insufficient
            else ("REQUIRES_REVIEW" if provisional else "ASSESSED"),
            "critical_unknown_count": len(critical_unknowns),
            "critical_unknowns": critical_unknowns,
            "coverage_percent": professional_result.coverage_percent,
            "message": "Insufficient evidence to establish fit."
            if evidence_insufficient
            else "Review unresolved conditions and partial matches before deciding."
            if provisional
            else "Assessment supported by available evidence.",
        },
        "score": professional_result.score,
        "coverage_percent": professional_result.coverage_percent,
        "score_scope": "professional_requirements_only",
        "conditions": conditions,
        "combined_fit": result.model_dump(mode="json"),
        "recommendation": decision,
        "scoring_recommendation": professional_result.recommendation.value,
        "provisional": provisional,
        "minimum_coverage_percent": minimum_coverage,
        "score_explanation": (
            "Professional score excludes location, vehicle, work mode and compensation. "
            "UNKNOWN professional requirements are excluded from the score denominator. "
            "Coverage measures the share of requirement weight supported by an assessment."
        ),
        "unresolved_requirements": unknowns,
        "review_items": [
            {
                "requirement_key": item.requirement_key,
                "status": item.match_status.value,
                "priority": by_key[item.requirement_key].priority,
                "reason": item.rationale,
            }
            for item in assessments
            if item.match_status in {MatchStatus.UNKNOWN, MatchStatus.PARTIAL_MATCH}
        ],
        "fit": professional_result.model_dump(mode="json"),
        "requirements": [
            {
                "requirement_key": item.requirement_key,
                "description": item.description,
                "priority": item.priority,
                "category": item.category,
                "blocking": item.blocking,
                "evidence_text": item.evidence_text,
            }
            for item in requirements
        ],
        "assessments": [item.model_dump(mode="json") for item in assessments],
    }
