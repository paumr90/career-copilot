"""Local review and evaluation workflow. Private inputs stay outside version control."""

import argparse
import json
from pathlib import Path


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract", help="Extract all assessable JD sections")
    extract.add_argument("--input", required=True, help="RawJobDescriptionInput JSON")
    extract.add_argument("--output", required=True, help="Validated JobDescriptionInput JSON")
    extract.add_argument("--audit-output")
    template = commands.add_parser(
        "review-template", help="Export every requirement for human review"
    )
    template.add_argument("--input", required=True, help="JobDescriptionInput JSON")
    template.add_argument("--output", required=True)
    review = commands.add_parser("review", help="Validate and freeze an explicit review")
    review.add_argument("--input", required=True)
    review.add_argument("--output", required=True)
    evaluate = commands.add_parser(
        "evaluate", help="Evaluate a reviewed snapshot with configured OpenAI"
    )
    evaluate.add_argument("--review", required=True)
    evaluate.add_argument("--output", required=True)
    evaluate.add_argument(
        "--save", action="store_true", help="Commit opportunity and audit to PostgreSQL"
    )
    args = parser.parse_args()
    from app.modules.opportunities.review import (
        RequirementReviewRequest,
        RequirementReviewService,
        ReviewedJobDescription,
    )

    if args.command == "extract":
        from app.config import settings
        from app.modules.opportunities.coverage import extraction_coverage
        from app.modules.opportunities.extraction_request import JDExtractionRequestBuilder
        from app.modules.opportunities.openai_extractor import OpenAIJDExtractionProvider
        from app.modules.opportunities.schemas import RawJobDescriptionInput

        raw = RawJobDescriptionInput.model_validate(read_json(args.input))
        from app.modules.opportunities.extraction_workflow import extract_validated

        audit_path = args.audit_output or str(
            Path(args.output).with_name(Path(args.output).stem + ".audit.local.json")
        )
        job, result, attempts = extract_validated(
            raw_job=raw,
            request=JDExtractionRequestBuilder().build(raw_job=raw),
            provider=OpenAIJDExtractionProvider(
                model=settings.llm_model,
                api_key=settings.llm_api_key,
                timeout_seconds=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
            ),
            write_audit=lambda audit: write_json(audit_path, audit),
        )
        write_json(args.output, job.model_dump(mode="json"))
        inventory = extraction_coverage(job)
        write_json(
            audit_path,
            {
                **result.model_dump(mode="json"),
                "status": "validated",
                "attempts": attempts,
                "coverage": inventory,
                "extraction_rule_version": JDExtractionRequestBuilder().policy.version,
            },
        )
        print(
            "Extracted requirements:",
            len(job.requirements),
            "Unrepresented source bullets:",
            len(inventory["unrepresented_bullets"]),
        )
        return
    if args.command == "review-template":
        from app.modules.opportunities.schemas import JobDescriptionInput

        job = JobDescriptionInput.model_validate(read_json(args.input))
        write_json(
            args.output,
            {
                "job": job.model_dump(mode="json"),
                "reviewer": "",
                "reviewed_keys": [],
                "amendments": [],
                "note": "",
            },
        )
        print(
            "Fill reviewer and reviewed_keys after checking all priorities, categories and blockers."
        )
        return
    if args.command == "review":
        approved = RequirementReviewService().review(
            RequirementReviewRequest.model_validate(read_json(args.input))
        )
        write_json(args.output, approved.model_dump(mode="json"))
        print("Review saved:", approved.review_hash)
        return

    approved = ReviewedJobDescription.model_validate(read_json(args.review))
    RequirementReviewService().verify(approved)
    from sqlalchemy.orm import Session

    import app.infrastructure.db.model_registry  # noqa: F401
    from app.config import settings
    from app.infrastructure.db.session import engine
    from app.modules.fit.openai_assessor import OpenAISemanticAssessmentProvider
    from app.modules.fit.pipeline import RequirementAssessmentPipeline
    from app.modules.fit.report import build_fit_report
    from app.modules.opportunities.service import OpportunityService

    provider = OpenAISemanticAssessmentProvider(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
    with Session(engine) as session:
        try:
            _, opportunity, requirements = OpportunityService().create_from_review(
                session=session,
                review=approved,
            )
            result, fit_audit, assessment_audit, assessments, _ = (
                RequirementAssessmentPipeline().evaluate_with_provider_and_record(
                    session,
                    opportunity_id=opportunity.opportunity_id,
                    provider=provider,
                )
            )
            report = build_fit_report(
                result=result, requirements=requirements, assessments=assessments
            )
            from app.modules.opportunities.coverage import extraction_coverage

            report["extraction_coverage"] = extraction_coverage(approved.reviewed)
            if report["extraction_coverage"]["requires_source_review"]:
                report["provisional"] = True
                if report["recommendation"] == "APPLY":
                    report["recommendation"] = "REVIEW"
            report["review_hash"] = approved.review_hash
            report["persisted"] = args.save
            report["assessment_audit"] = assessment_audit.input_json
            report["fit_audit"] = fit_audit.result_json
            if args.save:
                session.commit()
            else:
                session.rollback()
            write_json(args.output, report)
            print(
                json.dumps(
                    {
                        key: report[key]
                        for key in (
                            "assessment_summary",
                            "recommendation",
                            "provisional",
                        )
                    }
                )
            )
        except Exception as error:
            session.rollback()
            attempts = getattr(error, "assessment_attempts", None)
            if attempts:
                write_json(
                    args.output,
                    {
                        "status": "validation_failed",
                        "error": str(error),
                        "validation_attempts": attempts,
                        "review_hash": approved.review_hash,
                    },
                )
            raise


if __name__ == "__main__":
    main()
