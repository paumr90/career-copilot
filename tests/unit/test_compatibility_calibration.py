import uuid

import pytest

from app.modules.fit.compatibility import CompatibilityAssessmentRules
from app.modules.fit.report import build_fit_report
from app.modules.fit.schemas import (
    FitResult,
    RequirementAssessment,
    RequirementAssessmentProposal,
    SemanticAssessmentRequest,
)
from app.modules.opportunities.coverage import extraction_coverage
from app.modules.opportunities.models import JobRequirement
from app.modules.opportunities.review import RequirementReviewRequest, RequirementReviewService
from app.modules.opportunities.schemas import JobDescriptionInput


def request(category, description, values):
    fact_id = uuid.uuid4()
    return SemanticAssessmentRequest.model_validate(
        {
            "semantic_rule_version": "0.1",
            "retrieval_rule_version": "0.3",
            "ranking_rule_version": "0.2",
            "requirement": {
                "requirement_key": "condition",
                "description": description,
                "category": category,
                "priority": "MUST_HAVE",
                "blocking": False,
                "evidence_text": description,
            },
            "ranked_evidence": [
                {
                    "profile_fact_id": str(fact_id),
                    "fact_type": (
                        "compensation_preference"
                        if category == "COMPENSATION"
                        else "work_preference"
                    ),
                    "tier": "PRIMARY",
                    "subject": "Synthetic user confirmation",
                    "value_json": values,
                    "relevance_score": 1,
                }
            ],
        }
    )


def proposal(req, status="MATCH"):
    return RequirementAssessmentProposal.model_validate(
        {
            "requirement_key": "condition",
            "proposed_status": status,
            "evidence": []
            if status == "UNKNOWN"
            else [
                {
                    "profile_fact_id": str(req.ranked_evidence[0].profile_fact_id),
                }
            ],
            "rationale": "Assessment supported by the explicit facts.",
        }
    )


@pytest.mark.parametrize(
    "values",
    [
        {"preferred_location": "Example City"},
        {"current_city": "Neighbouring Municipality", "preferred_location": "Example City"},
    ],
)
def test_residency_is_unknown_without_actual_matching_city_or_explicit_scope(values):
    req = request("LOCATION", "Reside in Example City Region.", values)
    with pytest.raises(ValueError):
        CompatibilityAssessmentRules().validate(request=req, proposal=proposal(req))
    CompatibilityAssessmentRules().validate(request=req, proposal=proposal(req, "UNKNOWN"))


def test_ambiguous_city_province_scope_requires_unknown_even_with_actual_residence():
    req = request("LOCATION", "Residir en Barcelona.", {"current_city": "Mataró"})
    for status in ["MATCH", "PARTIAL_MATCH", "GAP"]:
        with pytest.raises(ValueError, match="scope"):
            CompatibilityAssessmentRules().validate(request=req, proposal=proposal(req, status))


def test_explicit_province_requires_province_evidence():
    req = request("LOCATION", "Reside in Barcelona province.", {"current_city": "Mataró"})
    with pytest.raises(ValueError, match="province fact"):
        CompatibilityAssessmentRules().validate(request=req, proposal=proposal(req))
    req.ranked_evidence[0].value_json["current_province"] = "Barcelona"
    CompatibilityAssessmentRules().validate(request=req, proposal=proposal(req))


def test_salary_touching_only_upper_bound_cannot_be_a_full_match():
    req = request(
        "COMPENSATION", "Entre 50k y 60k + variable.", {"minimum_fixed_salary_eur": 60000}
    )
    with pytest.raises(ValueError, match="PARTIAL_MATCH"):
        CompatibilityAssessmentRules().validate(request=req, proposal=proposal(req))
    CompatibilityAssessmentRules().validate(request=req, proposal=proposal(req, "PARTIAL_MATCH"))


def test_fully_compatible_salary_range_is_allowed():
    req = request(
        "COMPENSATION", "Between 65k and 70k EUR annually.", {"minimum_fixed_salary_eur": 60000}
    )
    CompatibilityAssessmentRules().validate(request=req, proposal=proposal(req))


def test_monthly_salary_is_not_compared_to_an_unconverted_minimum():
    req = request("COMPENSATION", "5000 EUR monthly.", {"minimum_fixed_salary_eur": 60000})
    with pytest.raises(ValueError, match="conversion"):
        CompatibilityAssessmentRules().validate(request=req, proposal=proposal(req))


def test_conditional_onsite_willingness_remains_partial():
    req = request(
        "WORK_MODE",
        "3 onsite days per week.",
        {
            "onsite_days_acceptance": {"days_per_week": 3, "status": "CONDITIONAL"},
        },
    )
    with pytest.raises(ValueError, match="Conditional"):
        CompatibilityAssessmentRules().validate(request=req, proposal=proposal(req))
    CompatibilityAssessmentRules().validate(request=req, proposal=proposal(req, "PARTIAL_MATCH"))


def test_vehicle_requires_explicit_ownership_not_travel_willingness():
    req = request("OTHER", "Have own vehicle.", {"travel_acceptable": True})
    with pytest.raises(ValueError, match="owns_vehicle"):
        CompatibilityAssessmentRules().validate(request=req, proposal=proposal(req))
    req.ranked_evidence[0].value_json["owns_vehicle"] = True
    CompatibilityAssessmentRules().validate(request=req, proposal=proposal(req))


def test_bullet_inventory_exposes_omitted_talent_development():
    job = JobDescriptionInput.model_validate(
        {
            "company": "Synthetic",
            "role_title": "AI Lead",
            "raw_text": "• Evaluate AI specialists.\n• Develop internal AI talent.",
            "requirements": [
                {
                    "requirement_key": "assess_specialists",
                    "description": "Evaluate specialists",
                    "priority": "SECONDARY",
                    "category": "RESPONSIBILITY",
                    "blocking": False,
                    "evidence_text": "Evaluate AI specialists.",
                }
            ],
        }
    )
    inventory = extraction_coverage(job)
    assert inventory["unrepresented_bullets"] == ["Develop internal AI talent."]
    assert inventory["requires_source_review"]


def test_review_can_correct_excerpt_but_cannot_invent_source_text():
    job = JobDescriptionInput.model_validate(
        {
            "company": "Synthetic",
            "role_title": "AI Lead",
            "raw_text": "Identify internal talent.\nDevelop training plans.",
            "requirements": [
                {
                    "requirement_key": "develop_talent",
                    "description": "Develop talent and training",
                    "priority": "SECONDARY",
                    "category": "RESPONSIBILITY",
                    "evidence_text": "Develop training plans.",
                }
            ],
        }
    )
    approved = RequirementReviewService().review(
        RequirementReviewRequest(
            job=job,
            reviewer="Technical reviewer",
            reviewed_keys=["develop_talent"],
            amendments=[
                {
                    "requirement_key": "develop_talent",
                    "evidence_text": job.raw_text,
                    "reason": "Include both adjacent source sentences.",
                }
            ],
        )
    )
    RequirementReviewService().verify(approved)
    assert approved.original.requirements[0].evidence_text == "Develop training plans."
    with pytest.raises(ValueError, match="verbatim"):
        RequirementReviewService().review(
            RequirementReviewRequest(
                job=job,
                reviewer="Technical reviewer",
                reviewed_keys=["develop_talent"],
                amendments=[
                    {
                        "requirement_key": "develop_talent",
                        "evidence_text": "Invented experience.",
                        "reason": "Invalid correction.",
                    }
                ],
            )
        )


def test_conditions_do_not_contribute_to_the_professional_score():
    professional = JobRequirement(
        requirement_key="skill",
        description="Relevant skill",
        priority="MUST_HAVE",
        category="SKILL",
        blocking=False,
    )
    salary = JobRequirement(
        requirement_key="salary",
        description="Salary range",
        priority="SECONDARY",
        category="COMPENSATION",
        blocking=False,
    )
    assessments = [
        RequirementAssessment(
            requirement_key="skill",
            match_status="MATCH",
            evidence=[{"profile_fact_id": uuid.uuid4()}],
            rationale="Professional experience.",
        ),
        RequirementAssessment(
            requirement_key="salary",
            match_status="PARTIAL_MATCH",
            evidence=[{"profile_fact_id": uuid.uuid4()}],
            rationale="Negotiation required.",
        ),
    ]
    report = build_fit_report(
        result=FitResult(
            score=91.67,
            recommendation="APPLY",
            rule_version="0.1",
            known_weight=6,
            total_weight=6,
            coverage_percent=100,
        ),
        requirements=[professional, salary],
        assessments=assessments,
    )
    assert report["score"] == 100
    assert report["coverage_percent"] == 100
    assert report["combined_fit"]["score"] == 91.67
    assert report["score_scope"] == "professional_requirements_only"
    assert report["recommendation"] == "REVIEW"
    assert report["conditions"][0]["status"] == "PARTIAL_MATCH"


def test_pipeline_repairs_unsupported_residency_and_retains_the_rejection():
    from types import SimpleNamespace

    from app.modules.fit.pipeline import RequirementAssessmentPipeline
    from app.modules.fit.schemas import EvidenceRankingResult

    req = request("LOCATION", "Residir en Barcelona.", {"current_city": "Mataró"})
    evidence = req.ranked_evidence[0]
    ranking = EvidenceRankingResult.model_validate(
        {
            "requirement_key": "condition",
            "requirement_category": "LOCATION",
            "retrieval_rule_version": "0.3",
            "ranking_rule_version": "0.2",
            "ranking_method": "test",
            "total_candidate_count": 1,
            "ranked_candidates": [
                {
                    "candidate": {
                        key: value
                        for key, value in evidence.model_dump(mode="json").items()
                        if key in {"profile_fact_id", "fact_type", "tier", "subject", "value_json"}
                    },
                    "relevance_score": 1,
                }
            ],
        }
    )

    class Provider:
        repairs = 0

        def propose(self, *, request):
            return proposal(request, "PARTIAL_MATCH")

        def repair_with_telemetry(self, *, request, proposal, validation_error):
            self.repairs += 1
            assert "scope" in validation_error
            return SimpleNamespace(
                proposal=RequirementAssessmentProposal(
                    requirement_key="condition",
                    proposed_status="UNKNOWN",
                    evidence=[],
                    rationale="The geographic scope must be clarified by the employer.",
                ),
                telemetry=None,
            )

    provider = Provider()
    final, audit = RequirementAssessmentPipeline()._propose_validated(
        provider=provider,
        request=req,
        context=SimpleNamespace(ranking_result=ranking),
    )
    assert final.proposed_status.value == "UNKNOWN"
    assert provider.repairs == 1
    assert audit["validation_attempts"][0]["proposal"]["proposed_status"] == "PARTIAL_MATCH"
    assert audit["validation_attempts"][1]["validation_error"] is None
