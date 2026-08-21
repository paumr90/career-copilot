from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.db.session import engine
from app.modules.audit.models import (
    RuleEvaluation,
)
from app.modules.governance.models import Source
from app.modules.opportunities.deterministic_extractor import (
    DeterministicJDExtractionProvider,
)
from app.modules.opportunities.intake import (
    JDIntakeService,
)
from app.modules.opportunities.models import (
    JobRequirement,
    Opportunity,
)
from app.modules.opportunities.schemas import (
    RawJobDescriptionInput,
)


RAW_JD = (
    "We are hiring a Senior Program Manager. "
    "Candidates must have at least 5 years "
    "of project management experience. "
    "Experience with cloud platforms is preferred. "
    "Knowledge of SQL. "
    "You will lead cross-functional transformation "
    "projects. "
    "We offer private health insurance."
)


def build_raw_job() -> RawJobDescriptionInput:
    return RawJobDescriptionInput(
        company="Automated Intake Example",
        role_title="Senior Program Manager",
        location="Barcelona",
        raw_text=RAW_JD,
        source_url=(
            "https://example.com/jobs/"
            "senior-program-manager"
        ),
    )


def test_raw_jd_is_automatically_extracted_created_and_audited() -> None:
    intake_service = JDIntakeService()

    provider = (
        DeterministicJDExtractionProvider()
    )

    raw_job = build_raw_job()

    with Session(engine) as session:
        sources_before = session.scalar(
            select(func.count()).select_from(
                Source
            )
        )

        opportunities_before = session.scalar(
            select(func.count()).select_from(
                Opportunity
            )
        )

        requirements_before = session.scalar(
            select(func.count()).select_from(
                JobRequirement
            )
        )

        evaluations_before = session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        )

        (
            source,
            opportunity,
            requirements,
            proposal,
            validated_job,
            extraction_evaluation,
        ) = intake_service.create_from_provider(
            session=session,
            raw_job=raw_job,
            provider=provider,
            external_id=(
                "automated-jd-intake-test"
            ),
        )

        assert (
            provider.provider_name
            == "deterministic_local"
        )

        assert (
            provider.provider_version
            == "0.1"
        )

        assert source.source_type == "JD"

        assert (
            source.authority_level
            == "CANONICAL_JD"
        )

        assert source.immutable is True

        assert (
            source.external_id
            == "automated-jd-intake-test"
        )

        assert (
            source.uri
            == raw_job.source_url
        )

        assert (
            opportunity.jd_source_id
            == source.source_id
        )

        assert (
            opportunity.company
            == raw_job.company
        )

        assert (
            opportunity.role_title
            == raw_job.role_title
        )

        assert (
            opportunity.location
            == raw_job.location
        )

        assert (
            opportunity.raw_text
            == raw_job.raw_text
        )

        assert len(
            proposal.requirements
        ) == 3

        assert len(
            validated_job.requirements
        ) == 3

        assert len(requirements) == 3

        priorities = [
            requirement.priority
            for requirement
            in requirements
        ]

        assert priorities == [
            "MUST_HAVE",
            "NICE_TO_HAVE",
            "SECONDARY",
        ]

        categories = [
            requirement.category
            for requirement
            in requirements
        ]

        assert categories == [
            "EXPERIENCE",
            "TECHNOLOGY",
            "TECHNOLOGY",
        ]

        assert all(
            requirement.blocking is False
            for requirement in requirements
        )

        assert all(
            requirement.evidence_text
            in raw_job.raw_text
            for requirement in requirements
        )

        descriptions = [
            requirement.description.lower()
            for requirement in requirements
        ]

        assert not any(
            "health insurance"
            in description
            for description in descriptions
        )

        assert not any(
            "lead cross-functional"
            in description
            for description in descriptions
        )

        assert (
            extraction_evaluation.rule_set
            == "jd_extraction"
        )

        assert (
            extraction_evaluation.ruleset_version
            == "0.1"
        )

        assert (
            extraction_evaluation.entity_type
            == "opportunity"
        )

        assert (
            extraction_evaluation.entity_id
            == opportunity.opportunity_id
        )

        assert (
            extraction_evaluation
            .input_json["provider_origin"]
            == {
                "provider_name": (
                    "deterministic_local"
                ),
                "provider_version": "0.1",
            }
        )

        assert (
            extraction_evaluation
            .result_json["requirements_count"]
            == 3
        )

        assert session.scalar(
            select(func.count()).select_from(
                Source
            )
        ) == sources_before + 1

        assert session.scalar(
            select(func.count()).select_from(
                Opportunity
            )
        ) == opportunities_before + 1

        assert session.scalar(
            select(func.count()).select_from(
                JobRequirement
            )
        ) == requirements_before + 3

        assert session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        ) == evaluations_before + 1

        session.rollback()

    with Session(engine) as session:
        assert session.scalar(
            select(func.count()).select_from(
                Source
            )
        ) == sources_before

        assert session.scalar(
            select(func.count()).select_from(
                Opportunity
            )
        ) == opportunities_before

        assert session.scalar(
            select(func.count()).select_from(
                JobRequirement
            )
        ) == requirements_before

        assert session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        ) == evaluations_before