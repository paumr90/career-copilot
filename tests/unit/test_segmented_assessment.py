import uuid

import pytest

from app.domain.rules.fit_scoring import FitScoringPolicy
from app.modules.fit.report import build_fit_report
from app.modules.fit.schemas import FitScoringRequirement, RequirementAssessment
from app.modules.opportunities.coverage import extraction_coverage
from app.modules.opportunities.extraction import JDExtractionValidator
from app.modules.opportunities.models import JobRequirement
from app.modules.opportunities.review import (
    RequirementReviewRequest,
    RequirementReviewService,
    ReviewedJobDescription,
)
from app.modules.opportunities.schemas import JobDescriptionInput, JobRequirementInput


def criterion(key, kind, text=None):
    return JobRequirement(
        requirement_key=key,
        description=text or key,
        criterion_type=kind,
        classification_reason="Synthetic source classification",
        priority="MUST_HAVE"
        if kind == "ESSENTIAL"
        else "NICE_TO_HAVE"
        if kind == "DESIRABLE"
        else "SECONDARY",
        category="RESPONSIBILITY" if kind in {"ROLE_CAPABILITY", "CONTEXT"} else "SKILL",
        blocking=False,
        evidence_text=text or key,
        source_excerpts=[],
    )


def report_for(rows):
    requirements = [criterion(key, kind) for key, kind, status in rows]
    assessments = [
        RequirementAssessment(
            requirement_key=key,
            match_status=status,
            evidence=[] if status == "UNKNOWN" else [{"profile_fact_id": uuid.uuid4()}],
            rationale="Synthetic evidence judgment",
            gap_basis="EXPLICIT_NON_COMPLIANCE" if status == "GAP" else None,
        )
        for key, kind, status in rows
        if kind != "CONTEXT"
    ]
    mapping = {a.requirement_key: a for a in assessments}
    legacy = FitScoringPolicy().evaluate(
        [
            FitScoringRequirement(
                requirement_key=r.requirement_key,
                priority=r.priority,
                blocking=False,
                assessment=mapping[r.requirement_key],
            )
            for r in requirements
            if r.criterion_type != "CONTEXT"
        ]
    )
    return build_fit_report(result=legacy, requirements=requirements, assessments=assessments)


def test_desirables_and_role_duties_cannot_compensate_an_essential_gap():
    rows = [("essential", "ESSENTIAL", "GAP")]
    rows += [(f"bonus_{i}", "DESIRABLE", "MATCH") for i in range(20)]
    rows += [(f"duty_{i}", "ROLE_CAPABILITY", "MATCH") for i in range(20)]
    report = report_for(rows)
    assert report["recommendation"] == "NO_APPLY"
    assert report["score"] is None
    assert report["selection_requirements"]["essential"]["counts"] == {"GAP": 1}


@pytest.mark.parametrize("duty_count", [0, 1, 40])
def test_offer_length_and_unknown_role_duties_do_not_dilute_selection(duty_count):
    rows = [("essential", "ESSENTIAL", "MATCH")]
    rows += [(f"duty_{i}", "ROLE_CAPABILITY", "UNKNOWN") for i in range(duty_count)]
    report = report_for(rows)
    assert report["recommendation"] == "APPLY"
    assert report["selection_requirements"]["essential"]["coverage_percent"] == 100
    assert report["assessment_summary"]["critical_unknown_count"] == 0
    assert len(report["role_capabilities"]) == duty_count


def test_unknown_essential_is_not_a_gap_and_unclassified_is_not_a_hidden_essential():
    report = report_for(
        [
            ("critical", "ESSENTIAL", "UNKNOWN"),
            ("unclear", "UNCLASSIFIED", "MATCH"),
            ("bonus", "DESIRABLE", "MATCH"),
        ]
    )
    assert report["recommendation"] == "REVIEW"
    assert report["assessment_summary"]["critical_unknown_count"] == 1
    assert report["assessment_summary"]["classification_pending_count"] == 1


def test_no_explicit_essentials_requires_review_even_with_all_bonuses():
    report = report_for([("bonus", "DESIRABLE", "MATCH"), ("mission", "CONTEXT", None)])
    assert report["recommendation"] == "REVIEW"
    assert report["selection_requirements"]["essential"]["coverage_percent"] is None
    assert report["role_context"][0]["status"] is None
    assert len(report["assessments"]) == 1


def grouped_job():
    return JobDescriptionInput(
        company="Synthetic",
        role_title="Lead",
        raw_text="- Define roadmaps.\n- Coordinate delivery.",
        requirements=[
            JobRequirementInput(
                requirement_key="delivery",
                description="Lead roadmap and delivery execution",
                criterion_type="ROLE_CAPABILITY",
                classification_reason="Two duties describe one delivery capability, not an eligibility threshold.",
                priority="SECONDARY",
                category="RESPONSIBILITY",
                evidence_text="Define roadmaps.",
                source_excerpts=["Define roadmaps.", "Coordinate delivery."],
            )
        ],
    )


def test_grouping_preserves_separate_literal_sources_and_bullet_inventory():
    job = JDExtractionValidator().validate(grouped_job())
    assert not extraction_coverage(job)["unrepresented_bullets"]
    job.requirements[0].source_excerpts.append("Invented experience")
    with pytest.raises(ValueError, match="verbatim"):
        JDExtractionValidator().validate(job)


def test_classifier_cannot_use_essential_weight_for_role_duties():
    job = grouped_job()
    job.requirements[0].priority = "MUST_HAVE"
    with pytest.raises(ValueError, match="requires priority SECONDARY"):
        JDExtractionValidator().validate(job)


def test_review_records_changed_classification_and_preserves_original():
    job = grouped_job()
    reviewed = RequirementReviewService().review(
        RequirementReviewRequest(
            job=job,
            reviewer="Synthetic reviewer",
            reviewed_keys=["delivery"],
            amendments=[
                {
                    "requirement_key": "delivery",
                    "criterion_type": "UNCLASSIFIED",
                    "classification_reason": "This qualification has unclear priority",
                    "reason": "Corrected grouping after source review",
                }
            ],
        )
    )
    assert reviewed.original.requirements[0].criterion_type == "ROLE_CAPABILITY"
    assert reviewed.reviewed.requirements[0].criterion_type == "UNCLASSIFIED"
    RequirementReviewService().verify(reviewed)


def test_old_review_hashes_survive_default_classification_fields():
    job = grouped_job()
    job.requirements[0].criterion_type = None
    job.requirements[0].classification_reason = ""
    job.requirements[0].source_excerpts = []
    review = RequirementReviewService().review(
        RequirementReviewRequest(job=job, reviewer="Synthetic", reviewed_keys=["delivery"])
    )
    old = review.model_dump(mode="json")
    for snapshot in ["original", "reviewed"]:
        for item in old[snapshot]["requirements"]:
            for key in ["criterion_type", "classification_reason", "source_excerpts"]:
                item.pop(key)
    assert RequirementReviewService.digest(old) == review.review_hash
    RequirementReviewService().verify(ReviewedJobDescription.model_validate(old))


def test_shared_source_sentence_does_not_turn_education_into_vehicle_condition():
    from app.modules.fit.compatibility import is_vehicle_requirement

    requirement = criterion("technical_education", "UNCLASSIFIED", "Engineering education")
    requirement.category = "EDUCATION"
    requirement.evidence_text = "Technical education and own vehicle."
    assert not is_vehicle_requirement(requirement)
    vehicle = criterion("own_vehicle", "PRACTICAL_CONDITION", "Own a vehicle")
    vehicle.category = "OTHER"
    vehicle.evidence_text = requirement.evidence_text
    assert is_vehicle_requirement(vehicle)


def test_group_excerpt_spacing_recovery_preserves_original_model_output():
    from app.modules.opportunities.extraction_workflow import restore_literal_whitespace
    from app.modules.opportunities.schemas import JDExtractionProposal

    job = grouped_job()
    proposal = JDExtractionProposal(requirements=job.requirements)
    source = "Define\n  roadmaps. Coordinate delivery."
    repaired, audit = restore_literal_whitespace(proposal, source)
    assert repaired.requirements[0].source_excerpts[0] == "Define\n  roadmaps."
    assert proposal.requirements[0].source_excerpts[0] == "Define roadmaps."
    assert any(r["field"] == "source_excerpts" for r in audit)


def test_classification_change_needs_no_written_reason_and_preserves_original_explanation():
    original = grouped_job()
    review = RequirementReviewService().review(
        RequirementReviewRequest(
            job=original,
            reviewer="Synthetic reviewer",
            reviewed_keys=["delivery"],
            amendments=[{"requirement_key": "delivery", "criterion_type": "ESSENTIAL"}],
        )
    )
    changed = review.reviewed.requirements[0]
    assert changed.priority == "MUST_HAVE"
    assert changed.criterion_type == "ESSENTIAL"
    assert "Motiu no indicat" in changed.classification_reason
    assert (
        review.original.requirements[0].classification_reason
        == original.requirements[0].classification_reason
    )
    assert review.amendments[0].reason == ""
    RequirementReviewService().verify(review)


def test_optional_note_is_preserved_without_becoming_a_mandatory_field():
    review = RequirementReviewService().review(
        RequirementReviewRequest(
            job=grouped_job(),
            reviewer="Synthetic reviewer",
            reviewed_keys=["delivery"],
            amendments=[
                {
                    "requirement_key": "delivery",
                    "criterion_type": "UNCLASSIFIED",
                    "reason": "Cal confirmar-ho amb l'empresa",
                }
            ],
        )
    )
    assert review.reviewed.requirements[0].classification_reason == "Cal confirmar-ho amb l'empresa"
    assert review.amendments[0].reason == "Cal confirmar-ho amb l'empresa"
    RequirementReviewService().verify(review)


def test_optional_notes_do_not_allow_ungrounded_source_edits():
    with pytest.raises(ValueError, match="verbatim"):
        RequirementReviewService().review(
            RequirementReviewRequest(
                job=grouped_job(),
                reviewer="Synthetic",
                reviewed_keys=["delivery"],
                amendments=[{"requirement_key": "delivery", "evidence_text": "Invented source"}],
            )
        )
