from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import (
    EvidenceTier,
    FitRecommendation,
    GapBasis,
    MatchStatus,
    ProfileFactType,
)
from app.infrastructure.db.session import engine
from app.modules.audit.models import RuleEvaluation
from app.modules.fit.pipeline import (
    RequirementAssessmentPipeline,
)
from app.modules.fit.providers import (
    StaticSemanticAssessmentProvider,
)
from app.modules.fit.schemas import (
    ProfileEvidenceReference,
    RequirementAssessmentProposal,
)
from app.modules.governance.models import (
    ProfileFact,
    Source,
)
from app.modules.opportunities.models import (
    JobRequirement,
    Opportunity,
)
from app.modules.opportunities.schemas import (
    JobDescriptionInput,
    JobRequirementInput,
)
from app.modules.opportunities.service import (
    OpportunityService,
)


MATCH_KEY = "program_leadership"
PARTIAL_KEY = "cloud_governance"
GAP_KEY = "compensation_requirement"
UNKNOWN_KEY = "zyxqv_plmokn_qwertz"


def build_job_description() -> JobDescriptionInput:
    return JobDescriptionInput(
        company="M3 Acceptance Company",
        role_title="Transformation Program Manager",
        location="Barcelona",
        raw_text=(
            "alphamatchmarker transformation leadership. "
            "betapartialmarker cloud governance. "
            "gammagapmarker fixed compensation requirement. "
            "zyxqv plmokn qwertz unusualconcept."
        ),
        requirements=[
            JobRequirementInput(
                requirement_key=MATCH_KEY,
                description=(
                    "alphamatchmarker leadership of "
                    "complex transformation programs"
                ),
                priority="MUST_HAVE",
                category="EXPERIENCE",
                blocking=False,
                evidence_text=(
                    "alphamatchmarker program "
                    "leadership required"
                ),
            ),
            JobRequirementInput(
                requirement_key=PARTIAL_KEY,
                description=(
                    "betapartialmarker enterprise "
                    "cloud governance expertise"
                ),
                priority="NICE_TO_HAVE",
                category="SKILL",
                blocking=False,
                evidence_text=(
                    "betapartialmarker cloud "
                    "governance preferred"
                ),
            ),
            JobRequirementInput(
                requirement_key=GAP_KEY,
                description=(
                    "gammagapmarker minimum fixed "
                    "salary of 90000 EUR"
                ),
                priority="MUST_HAVE",
                category="COMPENSATION",
                blocking=True,
                evidence_text=(
                    "gammagapmarker 90000 EUR "
                    "fixed compensation required"
                ),
            ),
            JobRequirementInput(
                requirement_key=UNKNOWN_KEY,
                description=(
                    "zyxqv plmokn qwertz "
                    "unusualconcept"
                ),
                priority="NICE_TO_HAVE",
                category="TECHNOLOGY",
                blocking=False,
                evidence_text=(
                    "xyzabc nomatchtoken "
                    "qazwsx"
                ),
            ),
        ],
    )


def create_test_profile_evidence(
    session: Session,
) -> tuple[
    ProfileFact,
    ProfileFact,
    ProfileFact,
]:
    test_source = Source(
        source_type="PROFILE",
        external_id=None,
        uri=None,
        captured_at=datetime.now(
            timezone.utc
        ),
        snapshot_hash=None,
        metadata_json={
            "test_only": True,
            "scenario": "m3_acceptance",
        },
        authority_level="CANONICAL_PROFILE",
        immutable=True,
    )

    session.add(test_source)
    session.flush()

    match_fact = ProfileFact(
        fact_type=(
            ProfileFactType.EMPLOYMENT.value
        ),
        subject=(
            "alphamatchmarker transformation "
            "program leadership"
        ),
        value_json={
            "role": "Test Program Lead",
            "responsibilities": [
                "alphamatchmarker led complex "
                "transformation programs"
            ],
        },
        evidence_state="CONFIRMED",
        source_id=test_source.source_id,
    )

    partial_fact = ProfileFact(
        fact_type=(
            ProfileFactType.SKILL.value
        ),
        subject=(
            "betapartialmarker cloud governance"
        ),
        value_json={
            "areas": [
                "betapartialmarker adjacent "
                "cloud governance experience"
            ],
            "level": "EXPERIENCE",
        },
        evidence_state="CONFIRMED",
        source_id=test_source.source_id,
    )

    gap_fact = ProfileFact(
        fact_type=(
            ProfileFactType
            .COMPENSATION_PREFERENCE
            .value
        ),
        subject=(
            "gammagapmarker compensation "
            "evidence"
        ),
        value_json={
            "minimum_fixed_salary_eur": 60000,
            "variable_compensation_expected": True,
            "test_marker": "gammagapmarker",
        },
        evidence_state="CONFIRMED",
        source_id=test_source.source_id,
    )

    session.add_all(
        [
            match_fact,
            partial_fact,
            gap_fact,
        ]
    )

    session.flush()

    return (
        match_fact,
        partial_fact,
        gap_fact,
    )


def ranked_ids_for_context(
    context,
) -> set:
    return {
        ranked.candidate.profile_fact_id
        for ranked
        in context
        .ranking_result
        .ranked_candidates
    }


def test_m3_end_to_end_acceptance_scenario() -> None:
    opportunity_service = OpportunityService()
    pipeline = RequirementAssessmentPipeline()

    with Session(engine) as session:
        sources_before = session.scalar(
            select(func.count()).select_from(
                Source
            )
        )

        facts_before = session.scalar(
            select(func.count()).select_from(
                ProfileFact
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
            match_fact,
            partial_fact,
            gap_fact,
        ) = create_test_profile_evidence(
            session
        )

        _, opportunity, _ = (
            opportunity_service
            .create_from_job_description(
                session=session,
                job_description=(
                    build_job_description()
                ),
                external_id=(
                    "m3-acceptance-scenario"
                ),
            )
        )

        contexts = pipeline.prepare_context(
            session=session,
            opportunity_id=(
                opportunity.opportunity_id
            ),
        )

        context_by_key = {
            context.requirement.requirement_key:
                context
            for context in contexts
        }

        assert set(context_by_key) == {
            MATCH_KEY,
            PARTIAL_KEY,
            GAP_KEY,
            UNKNOWN_KEY,
        }

        assert (
            match_fact.fact_id
            in ranked_ids_for_context(
                context_by_key[MATCH_KEY]
            )
        )

        assert (
            partial_fact.fact_id
            in ranked_ids_for_context(
                context_by_key[PARTIAL_KEY]
            )
        )

        assert (
            gap_fact.fact_id
            in ranked_ids_for_context(
                context_by_key[GAP_KEY]
            )
        )

        assert (
            context_by_key[UNKNOWN_KEY]
            .ranking_result.used_fallback
            is True
        )

        assert (
            context_by_key[MATCH_KEY]
            .ranking_result
            .ranked_candidates[0]
            .candidate.tier
            == EvidenceTier.PRIMARY
        )

        assert (
            context_by_key[PARTIAL_KEY]
            .ranking_result
            .ranked_candidates[0]
            .candidate.tier
            == EvidenceTier.PRIMARY
        )

        assert (
            context_by_key[GAP_KEY]
            .ranking_result
            .ranked_candidates[0]
            .candidate.tier
            == EvidenceTier.PRIMARY
        )

        provider = (
            StaticSemanticAssessmentProvider(
                proposals={
                    MATCH_KEY:
                        RequirementAssessmentProposal(
                            requirement_key=(
                                MATCH_KEY
                            ),
                            proposed_status=(
                                MatchStatus.MATCH
                            ),
                            evidence=[
                                ProfileEvidenceReference(
                                    profile_fact_id=(
                                        match_fact.fact_id
                                    ),
                                    note=(
                                        "Direct primary "
                                        "experience evidence."
                                    ),
                                )
                            ],
                            rationale=(
                                "Primary evidence directly "
                                "supports the program "
                                "leadership requirement."
                            ),
                        ),
                    PARTIAL_KEY:
                        RequirementAssessmentProposal(
                            requirement_key=(
                                PARTIAL_KEY
                            ),
                            proposed_status=(
                                MatchStatus
                                .PARTIAL_MATCH
                            ),
                            evidence=[
                                ProfileEvidenceReference(
                                    profile_fact_id=(
                                        partial_fact.fact_id
                                    ),
                                    note=(
                                        "Transferable primary "
                                        "skill evidence."
                                    ),
                                )
                            ],
                            rationale=(
                                "The evidence is relevant "
                                "and transferable but does "
                                "not establish complete "
                                "equivalence."
                            ),
                        ),
                    GAP_KEY:
                        RequirementAssessmentProposal(
                            requirement_key=(
                                GAP_KEY
                            ),
                            proposed_status=(
                                MatchStatus.GAP
                            ),
                            evidence=[
                                ProfileEvidenceReference(
                                    profile_fact_id=(
                                        gap_fact.fact_id
                                    ),
                                    note=(
                                        "Confirmed numerical "
                                        "compensation evidence."
                                    ),
                                )
                            ],
                            rationale=(
                                "The confirmed value is "
                                "below the mandatory "
                                "numerical requirement."
                            ),
                            gap_basis=(
                                GapBasis
                                .NUMERIC_SHORTFALL
                            ),
                        ),
                    UNKNOWN_KEY:
                        RequirementAssessmentProposal(
                            requirement_key=(
                                UNKNOWN_KEY
                            ),
                            proposed_status=(
                                MatchStatus.UNKNOWN
                            ),
                            evidence=[],
                            rationale=(
                                "The governed evidence is "
                                "insufficient to reach a "
                                "defensible conclusion."
                            ),
                        ),
                }
            )
        )

        (
            result,
            fit_evaluation,
            assessment_evaluation,
            assessments,
            proposals,
        ) = pipeline.evaluate_with_provider_and_record(
            session=session,
            opportunity_id=(
                opportunity.opportunity_id
            ),
            provider=provider,
        )

        assert len(proposals) == 4
        assert len(assessments) == 4

        assessment_by_key = {
            assessment.requirement_key:
                assessment
            for assessment in assessments
        }

        assert (
            assessment_by_key[
                MATCH_KEY
            ].match_status
            == MatchStatus.MATCH
        )

        assert (
            assessment_by_key[
                PARTIAL_KEY
            ].match_status
            == MatchStatus.PARTIAL_MATCH
        )

        assert (
            assessment_by_key[
                GAP_KEY
            ].match_status
            == MatchStatus.GAP
        )

        assert (
            assessment_by_key[
                GAP_KEY
            ].gap_basis
            == GapBasis.NUMERIC_SHORTFALL
        )

        assert (
            assessment_by_key[
                UNKNOWN_KEY
            ].match_status
            == MatchStatus.UNKNOWN
        )

        assert (
            assessment_by_key[
                UNKNOWN_KEY
            ].evidence
            == []
        )

        assert result.score == 50.0

        assert result.known_weight == 12.0
        assert result.total_weight == 14.0

        assert result.coverage_percent == (
            pytest.approx(
                85.71,
                abs=0.01,
            )
        )

        assert (
            result.recommendation
            == FitRecommendation.NO_APPLY
        )

        assert GAP_KEY in (
            result.blocking_gap_keys
        )

        assert (
            assessment_evaluation.rule_set
            == "requirement_assessment"
        )

        assert (
            fit_evaluation.rule_set
            == "fit_scoring"
        )

        assert (
            assessment_evaluation
            .input_json["proposal_origin"]
            ["mode"]
            == "provider"
        )

        assert (
            assessment_evaluation
            .input_json["proposal_origin"]
            ["provider_name"]
            == "static_local"
        )

        assert session.scalar(
            select(func.count()).select_from(
                Source
            )
        ) == sources_before + 2

        assert session.scalar(
            select(func.count()).select_from(
                ProfileFact
            )
        ) == facts_before + 3

        assert session.scalar(
            select(func.count()).select_from(
                Opportunity
            )
        ) == opportunities_before + 1

        assert session.scalar(
            select(func.count()).select_from(
                JobRequirement
            )
        ) == requirements_before + 4

        assert session.scalar(
            select(func.count()).select_from(
                RuleEvaluation
            )
        ) == evaluations_before + 2

        session.rollback()

    with Session(engine) as session:
        assert session.scalar(
            select(func.count()).select_from(
                Source
            )
        ) == sources_before

        assert session.scalar(
            select(func.count()).select_from(
                ProfileFact
            )
        ) == facts_before

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