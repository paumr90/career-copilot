from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infrastructure.db.session import engine
from app.modules.opportunities.review import RequirementReviewRequest, RequirementReviewService
from app.modules.opportunities.service import OpportunityService


def test_review_snapshot_is_stored_without_changing_original_source():
    request = RequirementReviewRequest.model_validate(
        {
            "job": {
                "company": "Synthetic",
                "role_title": "Engineer",
                "raw_text": "A degree is required.",
                "requirements": [
                    {
                        "requirement_key": "degree",
                        "description": "A degree",
                        "priority": "SECONDARY",
                        "category": "EDUCATION",
                        "blocking": False,
                        "evidence_text": "A degree is required.",
                    }
                ],
            },
            "reviewer": "Test reviewer",
            "reviewed_keys": ["degree"],
            "amendments": [
                {
                    "requirement_key": "degree",
                    "priority": "MUST_HAVE",
                    "reason": "The source explicitly requires it.",
                }
            ],
        }
    )
    approved = RequirementReviewService().review(request)
    with Session(engine) as session:
        assert session.scalar(text("SELECT current_schema()")).startswith("copilot_test_")
        source, opportunity, requirements = OpportunityService().create_from_review(
            session,
            review=approved,
        )
        stored = source.metadata_json["requirement_review"]
        assert stored["original"]["requirements"][0]["priority"] == "SECONDARY"
        assert stored["reviewed"]["requirements"][0]["priority"] == "MUST_HAVE"
        assert stored["review_hash"] == approved.review_hash
        assert requirements[0].priority == "MUST_HAVE"
        assert opportunity.raw_text == request.job.raw_text
        session.rollback()
