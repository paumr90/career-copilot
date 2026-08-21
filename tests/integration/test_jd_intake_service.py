from sqlalchemy import func, select
from sqlalchemy.orm import Session

import pytest

from app.infrastructure.db.session import engine
from app.modules.audit.models import (
    RuleEvaluation,
)
from app.modules.audit.service import (
    RuleEvaluationService,
)
from app.modules.governance.models import Source
from app.modules.opportunities.intake import (
    JDIntakeService,
)
from app.modules.opportunities.models import (
    JobRequirement,
    Opportunity,
)
from app.modules.opportunities.providers import (
    StaticJDExtractionProvider,
)
from app.modules.opportunities.schemas import (
    JDExtractionProposal,
    JobRequirementInput,
    RawJobDescriptionInput,
)


RAW_JD = (
    "We are looking for a Program Manager. "
    "Candidates must have at least 5 years "
    "of project management experience. "
    "Experience with cloud platforms is preferred."
)


def build_raw_job() -> RawJobDescriptionInput:
    return RawJobDescriptionInput(
        company="Example Intake Company",
        role_title="Program Manager",
        location="Barcelona",
        raw_text=RAW_JD,
        source_url=(
            "https://example.com/jobs/"
            "program-manager"
        ),
    )


def build_valid_proposal() -> JDExtractionProposal:
    return JDExtractionProposal(
        requirements=[
            JobRequirementInput(
                requirement_key=(
                    "project_management_experience"
                ),
                description=(
                    "At least 5 years of project "
                    "management experience"
                ),
                priority="MUST_HAVE",
                category="EXPERIENCE",
                blocking=False,
                evidence_text=(
                    "must have at least 5 years "
                    "of project management experience"
                ),
            ),
            JobRequirementInput(
                requirement_key=(
                    "cloud_platform_experience"
                ),
                description=(
                    "Experience with cloud platforms"
                ),
                priority="NICE_TO_HAVE",
                category="TECHNOLOGY",
                blocking=False,
                evidence_text=(
                    "Experience with cloud platforms "
                    "is preferred"
                ),
            ),
        ]
    )


def build_fabricated_proposal() -> JDExtractionProposal:
    return JDExtractionProposal(
        requirements=[
            JobRequirementInput(
                requirement_key=(
                    "sap_experience"
                ),
                description=(
                    "10 years of SAP experience"
                ),
                priority="MUST_HAVE",
                category="TECHNOLOGY",
                blocking=False,
                evidence_text=(
                    "10 years of SAP experience "
                    "required"
                ),
            )
        ]
    )


def test_valid_provider_output_creates_and_audits_canonical_opportunity() -> None:
    intake_service = JDIntakeService()
    audit_service = RuleEvaluationService()

    provider = StaticJDExtractionProvider(
        proposal=build_valid_proposal()
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
                "jd-intake-valid-test"
            ),
        )

        assert source.source_type == "JD"

        assert (
            source.authority_level
            == "CANONICAL_JD"
        )

        assert source.immutable is True

        assert (
            source.external_id
            == "jd-intake-valid-test"
        )

        assert source.uri == raw_job.source_url

        assert (
            source.snapshot_hash
            == intake_service
            .opportunity_service
            .calculate_snapshot_hash(
                raw_job.raw_text
            )
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

        assert len(requirements) == 2

        assert {
            requirement.requirement_key
            for requirement in requirements
        } == {
            "project_management_experience",
            "cloud_platform_experience",
        }

        assert (
            proposal
            == build_valid_proposal()
        )

        assert (
            validated_job.company
            == raw_job.company
        )

        assert (
            validated_job.raw_text
            == raw_job.raw_text
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
            .input_json["source_id"]
            == str(source.source_id)
        )

        assert (
            extraction_evaluation
            .input_json["opportunity_id"]
            == str(
                opportunity.opportunity_id
            )
        )

        assert (
            extraction_evaluation
            .input_json["jd_snapshot_hash"]
            == source.snapshot_hash
        )

        request_audit = (
            extraction_evaluation
            .input_json["extraction_request"]
        )

        assert request_audit == {
            "extraction_rule_version": "0.1",
            "company": raw_job.company,
            "role_title": raw_job.role_title,
            "location": raw_job.location,
        }

        assert (
            "raw_text"
            not in request_audit
        )

        assert (
            "source_url"
            not in request_audit
        )

        assert (
            extraction_evaluation
            .input_json["provider_origin"]
            == {
                "provider_name": "static_local",
                "provider_version": "0.1",
            }
        )

        assert (
            extraction_evaluation
            .input_json["rules_snapshot"]
            ["jd_extraction"]["version"]
            == "0.1"
        )

        assert (
            extraction_evaluation
            .result_json["requirements_count"]
            == 2
        )

        assert len(
            extraction_evaluation
            .result_json["validated_requirements"]
        ) == 2

        assert (
            extraction_evaluation.input_hash
            == audit_service
            .calculate_input_hash(
                extraction_evaluation.input_json
            )
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
        ) == requirements_before + 2

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


def test_fabricated_provider_output_writes_and_audits_nothing() -> None:
    intake_service = JDIntakeService()

    provider = StaticJDExtractionProvider(
        proposal=build_fabricated_proposal()
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

        with pytest.raises(
            ValueError,
            match=(
                "evidence_text must be a verbatim "
                "contiguous substring"
            ),
        ):
            intake_service.create_from_provider(
                session=session,
                raw_job=raw_job,
                provider=provider,
                external_id=(
                    "jd-intake-invalid-test"
                ),
            )

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

        session.rollback()