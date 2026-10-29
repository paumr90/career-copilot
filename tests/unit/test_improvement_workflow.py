import uuid
from types import SimpleNamespace

import pytest

from app.domain.enums import EvidenceTier
from app.modules.fit.pipeline import RequirementAssessmentPipeline
from app.modules.fit.ranking import EvidenceRelevanceRanker
from app.modules.fit.report import build_fit_report
from app.modules.fit.schemas import (
    CareerEvidenceCandidate,
    EvidenceCandidateSet,
    FitResult,
    RequirementAssessment,
    RequirementAssessmentProposal,
)
from app.modules.fit.semantic import SemanticAssessmentRequestBuilder
from app.modules.opportunities.models import JobRequirement
from app.modules.opportunities.review import (
    RequirementReviewRequest,
    RequirementReviewService,
)
from app.modules.opportunities.schemas import JobDescriptionInput


def job():
    return JobDescriptionInput.model_validate(
        {
            "company": "Example",
            "role_title": "Lead",
            "raw_text": "Technical degree required.",
            "requirements": [
                {
                    "requirement_key": "degree",
                    "description": "Technical degree",
                    "priority": "SECONDARY",
                    "category": "OTHER",
                    "blocking": False,
                    "evidence_text": "Technical degree required.",
                }
            ],
        }
    )


def test_review_requires_every_requirement_and_preserves_original():
    service = RequirementReviewService()
    with pytest.raises(ValueError, match="explicitly reviewed"):
        service.review(RequirementReviewRequest(job=job(), reviewer="Reviewer", reviewed_keys=[]))
    approved = service.review(
        RequirementReviewRequest(
            job=job(),
            reviewer="Reviewer",
            reviewed_keys=["degree"],
            amendments=[
                {
                    "requirement_key": "degree",
                    "priority": "MUST_HAVE",
                    "category": "EDUCATION",
                    "blocking": True,
                    "reason": "The original explicitly requires this qualification.",
                }
            ],
        )
    )
    assert approved.original.requirements[0].priority.value == "SECONDARY"
    assert approved.reviewed.requirements[0].priority.value == "MUST_HAVE"
    service.verify(approved)
    altered = approved.model_copy(deep=True)
    altered.reviewed.requirements[0].description = "Invented condition"
    with pytest.raises(ValueError, match="hash"):
        service.verify(altered)


def test_review_rejects_unknown_keys_and_invalid_blocking():
    service = RequirementReviewService()
    with pytest.raises(ValueError, match="existing requirements"):
        service.review(
            RequirementReviewRequest(
                job=job(),
                reviewer="Reviewer",
                reviewed_keys=["degree"],
                amendments=[{"requirement_key": "missing", "reason": "Correction"}],
            )
        )
    with pytest.raises(ValueError, match="MUST_HAVE"):
        service.review(
            RequirementReviewRequest(
                job=job(),
                reviewer="Reviewer",
                reviewed_keys=["degree"],
                amendments=[
                    {"requirement_key": "degree", "blocking": True, "reason": "Correction"}
                ],
            )
        )


def context(primary=True):
    requirement = JobRequirement(
        requirement_key="presales",
        description="Experiencia en preventa",
        category="EXPERIENCE",
        priority="MUST_HAVE",
        blocking=False,
        evidence_text="Preventa",
    )
    candidate = CareerEvidenceCandidate(
        profile_fact_id=uuid.uuid4(),
        fact_type="employment",
        subject="Employer",
        value_json={"responsibilities": ["Client proposals and tenders"]},
        tier="PRIMARY" if primary else "SUPPORTING",
    )
    pool = EvidenceCandidateSet(
        requirement_key="presales",
        requirement_category="EXPERIENCE",
        retrieval_rule_version="0.2",
        primary_candidates=[candidate] if primary else [],
        supporting_candidates=[] if primary else [candidate],
    )
    ranking = EvidenceRelevanceRanker().rank(requirement=requirement, candidate_set=pool)
    return SimpleNamespace(requirement=requirement, ranking_result=ranking), candidate


def test_spanish_presales_retrieves_english_proposals():
    ctx, candidate = context()
    assert (
        ctx.ranking_result.ranked_candidates[0].candidate.profile_fact_id
        == candidate.profile_fact_id
    )
    assert ctx.ranking_result.ranked_candidates[0].relevance_score > 0


def test_primary_reservation_survives_positive_supporting_matches():
    ctx, primary = context()
    primary.value_json = {"focus": "Untranslated evidence"}
    primary.subject = "Employer"
    supporters = [
        primary.model_copy(
            update={
                "profile_fact_id": uuid.uuid4(),
                "subject": "Preventa",
                "tier": EvidenceTier.SUPPORTING,
                "value_json": {"areas": ["Preventa"]},
            }
        )
        for _ in range(8)
    ]
    pool = EvidenceCandidateSet(
        requirement_key="presales",
        requirement_category="EXPERIENCE",
        retrieval_rule_version="0.2",
        primary_candidates=[primary],
        supporting_candidates=supporters,
    )
    result = EvidenceRelevanceRanker().rank(requirement=ctx.requirement, candidate_set=pool)
    assert len(result.ranked_candidates) <= 8
    assert primary.profile_fact_id in {
        item.candidate.profile_fact_id for item in result.ranked_candidates
    }
    assert result.used_fallback


def test_invalid_proposal_is_repaired_once_and_both_attempts_are_retained():
    ctx, candidate = context()
    request = SemanticAssessmentRequestBuilder().build(
        requirement=ctx.requirement,
        ranking_result=ctx.ranking_result,
    )
    invalid = RequirementAssessmentProposal(
        requirement_key="presales",
        proposed_status="MATCH",
        evidence=[],
        rationale="Rejected unsupported match.",
    )
    valid = RequirementAssessmentProposal.model_validate(
        {
            **invalid.model_dump(),
            "evidence": [{"profile_fact_id": candidate.profile_fact_id}],
        }
    )

    class Provider:
        provider_name = "test"
        provider_version = "1"
        repairs = 0

        def propose(self, *, request):
            return invalid

        def repair_with_telemetry(self, *, request, proposal, validation_error):
            self.repairs += 1
            assert "PRIMARY" in validation_error
            return SimpleNamespace(proposal=valid, telemetry=None)

    provider = Provider()
    proposal, audit = RequirementAssessmentPipeline()._propose_validated(
        provider=provider,
        request=request,
        context=ctx,
    )
    assert provider.repairs == 1
    assert proposal.evidence
    assert len(audit["validation_attempts"]) == 2
    assert audit["validation_attempts"][0]["proposal"]["evidence"] == []
    assert audit["validation_attempts"][1]["validation_error"] is None


def test_invalid_repair_fails_closed_with_attempt_history():
    ctx, _ = context()
    request = SemanticAssessmentRequestBuilder().build(
        requirement=ctx.requirement,
        ranking_result=ctx.ranking_result,
    )
    invalid = RequirementAssessmentProposal(
        requirement_key="presales",
        proposed_status="MATCH",
        evidence=[],
        rationale="Unsupported claim.",
    )

    class Provider:
        def propose(self, *, request):
            return invalid

        def repair_with_telemetry(self, **kwargs):
            return SimpleNamespace(proposal=invalid, telemetry=None)

    with pytest.raises(ValueError) as caught:
        RequirementAssessmentPipeline()._propose_validated(
            provider=Provider(),
            request=request,
            context=ctx,
        )
    assert len(caught.value.assessment_attempts) == 2


def test_high_score_with_low_coverage_is_presented_as_provisional_review():
    requirement = JobRequirement(
        requirement_key="degree",
        description="Degree",
        category="EDUCATION",
        priority="NICE_TO_HAVE",
        blocking=False,
    )
    assessment = RequirementAssessment(
        requirement_key="degree",
        match_status="UNKNOWN",
        evidence=[],
        rationale="No education evidence was supplied.",
    )
    known = RequirementAssessment(
        requirement_key="experience",
        match_status="MATCH",
        evidence=[{"profile_fact_id": uuid.uuid4()}],
        rationale="Relevant employment.",
    )
    known_requirement = JobRequirement(
        requirement_key="experience",
        description="Experience",
        category="EXPERIENCE",
        priority="MUST_HAVE",
        blocking=False,
    )
    result = FitResult(
        score=100,
        recommendation="APPLY",
        rule_version="0.1",
        known_weight=5,
        total_weight=7,
        coverage_percent=71.43,
    )
    report = build_fit_report(
        result=result,
        requirements=[requirement, known_requirement],
        assessments=[assessment, known],
    )
    assert report["assessment_summary"]["status"] == "INSUFFICIENT_EVIDENCE"
    assert report["provisional"]
    assert report["recommendation"] == "REVIEW"
    assert report["scoring_recommendation"] == "APPLY"
    assert report["unresolved_requirements"][0]["reason"] == assessment.rationale


def test_source_provenance_cannot_create_relevance():
    ctx, primary = context()
    primary.value_json = {"_source": {"title": "Preventa client proposals tenders"}}
    primary.subject = "Unrelated"
    pool = EvidenceCandidateSet(
        requirement_key="presales",
        requirement_category="EXPERIENCE",
        retrieval_rule_version="0.2",
        primary_candidates=[primary],
    )
    result = EvidenceRelevanceRanker().rank(requirement=ctx.requirement, candidate_set=pool)
    assert result.ranked_candidates[0].relevance_score == 0
    assert result.used_fallback


def test_short_ai_terms_participate_in_multilingual_retrieval():
    ctx, primary = context()
    ctx.requirement.description = "IA"
    ctx.requirement.requirement_key = "specialty"
    ctx.requirement.evidence_text = "IA"
    primary.value_json = {"areas": ["LLM"]}
    pool = EvidenceCandidateSet(
        requirement_key="specialty",
        requirement_category="EXPERIENCE",
        retrieval_rule_version="0.2",
        primary_candidates=[primary],
    )
    result = EvidenceRelevanceRanker().rank(requirement=ctx.requirement, candidate_set=pool)
    assert result.ranked_candidates[0].relevance_score > 0


@pytest.mark.parametrize("priority,blocking", [("MUST_HAVE", False), ("MUST_HAVE", True)])
def test_critical_unknown_is_prominent_even_when_coverage_is_high(priority, blocking):
    from app.domain.rules.fit_scoring import FitScoringPolicy
    from app.modules.fit.schemas import FitScoringRequirement

    requirements = [
        JobRequirement(
            requirement_key=f"known_{i}",
            description="Demonstrated work",
            category="EXPERIENCE",
            priority="MUST_HAVE",
            blocking=False,
        )
        for i in range(12)
    ]
    requirements.append(
        JobRequirement(
            requirement_key="critical",
            description="Essential evidence pending",
            category="EXPERIENCE",
            priority=priority,
            blocking=blocking,
        )
    )
    assessments = [
        RequirementAssessment(
            requirement_key=r.requirement_key,
            match_status="MATCH",
            evidence=[{"profile_fact_id": uuid.uuid4()}],
            rationale="Direct work evidence",
        )
        for r in requirements[:-1]
    ]
    assessments.append(
        RequirementAssessment(
            requirement_key="critical",
            match_status="UNKNOWN",
            evidence=[],
            rationale="No evidence supplied",
        )
    )
    result = FitScoringPolicy().evaluate(
        [
            FitScoringRequirement(
                requirement_key=r.requirement_key,
                priority=r.priority,
                blocking=r.blocking,
                assessment=a,
            )
            for r, a in zip(requirements, assessments, strict=True)
        ]
    )
    report = build_fit_report(result=result, requirements=requirements, assessments=assessments)
    assert report["coverage_percent"] > 80
    assert report["score"] == 100
    assert report["recommendation"] == "REVIEW"
    summary = report["assessment_summary"]
    assert summary["status"] == "INSUFFICIENT_EVIDENCE"
    assert summary["critical_unknown_count"] == 1
    assert summary["critical_unknowns"][0]["requirement_key"] == "critical"
