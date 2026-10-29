"""User-facing fit report: coverage and unresolved requirements accompany every score."""

from app.domain.enums import MatchStatus
from app.domain.rules.fit_scoring import FitScoringPolicy
from app.modules.fit.compatibility import is_compatibility_requirement
from app.modules.fit.schemas import FitResult, FitScoringRequirement, RequirementAssessment
from app.modules.opportunities.models import JobRequirement


def _legacy_fit_report(
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


def build_fit_report(*, result, requirements, assessments, minimum_coverage=80.0):
    from collections import Counter

    from app.modules.opportunities.classification import criterion_kind

    assessable = [r for r in requirements if criterion_kind(r) != "CONTEXT"]
    report = _legacy_fit_report(
        result=result,
        requirements=assessable,
        assessments=assessments,
        minimum_coverage=minimum_coverage,
    )
    by_key = {a.requirement_key: a for a in assessments}
    groups = {
        kind: []
        for kind in (
            "CONTEXT",
            "ROLE_CAPABILITY",
            "ESSENTIAL",
            "DESIRABLE",
            "UNCLASSIFIED",
            "PRACTICAL_CONDITION",
        )
    }
    for requirement in requirements:
        kind = criterion_kind(requirement)
        assessment = by_key.get(requirement.requirement_key)
        groups[kind].append(
            {
                "requirement_key": requirement.requirement_key,
                "description": requirement.description,
                "status": assessment.match_status.value if assessment else None,
                "reason": assessment.rationale
                if assessment
                else "Context: not assessed against the candidate.",
                "classification_reason": getattr(requirement, "classification_reason", None)
                or "Historical classification inferred from category/priority; verify before reuse.",
                "classification_inferred": not bool(getattr(requirement, "criterion_type", None)),
                "criterion_type": kind,
                "blocking": requirement.blocking,
                "priority": requirement.priority,
                "source_excerpts": list(
                    dict.fromkeys(
                        [
                            requirement.evidence_text,
                            *(getattr(requirement, "source_excerpts", None) or []),
                        ]
                    )
                ),
            }
        )

    def section(items):
        counts = dict(Counter(item["status"] for item in items))
        return {
            "items": items,
            "total": len(items),
            "counts": counts,
            "coverage_percent": round(
                100 * sum(item["status"] != "UNKNOWN" for item in items) / len(items), 2
            )
            if items
            else None,
        }

    essential = groups["ESSENTIAL"]
    unclear = groups["UNCLASSIFIED"]
    conditions = groups["PRACTICAL_CONDITION"]
    critical_unknowns = [item for item in essential if item["status"] == "UNKNOWN"]
    pending = [item for item in essential if item["status"] != "MATCH"]
    condition_pending = [item for item in conditions if item["status"] != "MATCH"]
    if any(item["status"] == "GAP" for item in essential):
        decision = "NO_APPLY"
    elif not essential or unclear or pending or condition_pending:
        decision = "REVIEW"
    else:
        decision = "APPLY"
    # Numerical legacy calculations remain audit-only; never a product-level fit rating.
    report["legacy_fit_audit"] = {
        "professional": report.pop("fit"),
        "combined": report.pop("combined_fit"),
    }
    report.update(
        assessment_model="segmented_v1",
        score=None,
        score_scope="no_aggregate_score",
        coverage_percent=section(essential)["coverage_percent"],
        recommendation=decision,
        scoring_recommendation=None,
        provisional=decision == "REVIEW",
        minimum_coverage_percent=None,
        score_explanation="No aggregate fit score. Essential, desirable, role capabilities and practical conditions are assessed separately.",
        selection_requirements={
            "essential": section(essential),
            "desirable": section(groups["DESIRABLE"]),
            "unclassified": section(unclear),
        },
        role_capabilities=groups["ROLE_CAPABILITY"],
        role_context=groups["CONTEXT"],
        practical_conditions=conditions,
        assessment_summary={
            "status": "INSUFFICIENT_EVIDENCE"
            if critical_unknowns or unclear or not essential
            else "REQUIRES_REVIEW"
            if decision == "REVIEW"
            else "ESSENTIAL_GAP"
            if decision == "NO_APPLY"
            else "ESSENTIALS_SUPPORTED",
            "critical_unknown_count": len(critical_unknowns),
            "critical_unknowns": critical_unknowns,
            "coverage_percent": section(essential)["coverage_percent"],
            "essential_total": len(essential),
            "essential_matched": sum(item["status"] == "MATCH" for item in essential),
            "classification_pending_count": len(unclear),
            "message": "Review essential qualifications, unresolved classification and practical conditions independently. Role duties and desirable qualifications cannot compensate for an essential gap.",
        },
    )
    for row in report["requirements"]:
        requirement = next(r for r in requirements if r.requirement_key == row["requirement_key"])
        row["criterion_type"] = criterion_kind(requirement)
        row["source_excerpts"] = getattr(requirement, "source_excerpts", None) or []
    return report
