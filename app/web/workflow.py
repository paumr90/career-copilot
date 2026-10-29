"""Transient local previews. Persistence is explicit and never re-runs the model."""

from copy import deepcopy

from sqlalchemy.orm import Session

import app.infrastructure.db.model_registry  # noqa: F401
from app.config import settings
from app.infrastructure.db.session import engine
from app.modules.audit.service import RuleEvaluationService
from app.modules.fit.openai_assessor import OpenAISemanticAssessmentProvider
from app.modules.fit.pipeline import RequirementAssessmentPipeline
from app.modules.fit.report import build_fit_report
from app.modules.opportunities.coverage import extraction_coverage
from app.modules.opportunities.extraction_request import JDExtractionRequestBuilder
from app.modules.opportunities.extraction_workflow import extract_validated
from app.modules.opportunities.openai_extractor import OpenAIJDExtractionProvider
from app.modules.opportunities.service import OpportunityService


def provider_options():

    if not settings.llm_model or not settings.llm_api_key:
        raise ValueError("Configura LLM_MODEL i LLM_API_KEY al fitxer .env abans de continuar.")

    return {
        "model": settings.llm_model,
        "api_key": settings.llm_api_key,
        "timeout_seconds": settings.llm_timeout_seconds,
        "max_retries": settings.llm_max_retries,
    }


def make_extractor():

    return OpenAIJDExtractionProvider(**provider_options())


def make_assessor():

    return OpenAISemanticAssessmentProvider(**provider_options())


def extract(raw, checkpoint):

    job, _, _ = extract_validated(
        raw_job=raw,
        request=JDExtractionRequestBuilder().build(raw_job=raw),
        provider=make_extractor(),
        write_audit=checkpoint,
    )

    return job


def evaluate(review):

    with Session(engine) as session:
        try:
            _, opportunity, requirements = OpportunityService().create_from_review(
                session=session, review=review
            )

            pipeline = RequirementAssessmentPipeline()

            result, fit_audit, assessment_audit, assessments, _ = (
                pipeline.evaluate_with_provider_and_record(
                    session, opportunity_id=opportunity.opportunity_id, provider=make_assessor()
                )
            )

            report = build_fit_report(
                result=result, requirements=requirements, assessments=assessments
            )

            report["extraction_coverage"] = extraction_coverage(review.reviewed)

            if report["extraction_coverage"]["requires_source_review"]:
                report["provisional"] = True

                if report["recommendation"] == "APPLY":
                    report["recommendation"] = "REVIEW"

                if report["assessment_summary"]["status"] in {"ASSESSED", "ESSENTIALS_SUPPORTED"}:
                    report["assessment_summary"].update(
                        status="REQUIRES_REVIEW",
                        message="Cal revisar fragments de la font sense representació literal.",
                    )

            report.update(review_hash=review.review_hash, persisted=False)

            evidence = {}

            for context in pipeline.prepare_context(
                session=session, opportunity_id=opportunity.opportunity_id
            ):
                request = pipeline.semantic_request_builder.build(
                    requirement=context.requirement, ranking_result=context.ranking_result
                )

                evidence[context.requirement.requirement_key] = {
                    str(item.profile_fact_id): item.model_dump(mode="json")
                    for item in request.ranked_evidence
                }

            for item in report["assessments"]:
                item["evidence_items"] = [
                    evidence[item["requirement_key"]][cite["profile_fact_id"]]
                    for cite in item["evidence"]
                ]

            snapshots = [
                {
                    "rule_set": a.rule_set,
                    "ruleset_version": a.ruleset_version,
                    "input_payload": deepcopy(a.input_json),
                    "result_json": deepcopy(a.result_json),
                }
                for a in (assessment_audit, fit_audit)
            ]

            return report, snapshots

        finally:
            session.rollback()


def save(review, report, snapshots):

    with Session(engine) as session, session.begin():
        _, opportunity, _ = OpportunityService().create_from_review(session=session, review=review)

        for snapshot in snapshots:
            values = deepcopy(snapshot)

            values["input_payload"]["preview_opportunity_id"] = values["input_payload"].get(
                "opportunity_id"
            )

            values["input_payload"]["opportunity_id"] = str(opportunity.opportunity_id)

            RuleEvaluationService().record(
                session, **values, entity_type="opportunity", entity_id=opportunity.opportunity_id
            )

        RuleEvaluationService().record(
            session,
            rule_set="reviewed_web_report",
            ruleset_version="0.1",
            entity_type="opportunity",
            entity_id=opportunity.opportunity_id,
            input_payload={"review_hash": review.review_hash, "origin": "local_web_preview"},
            result_json={**deepcopy(report), "persisted": True},
        )

        return str(opportunity.opportunity_id)
