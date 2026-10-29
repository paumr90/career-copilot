import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import SourceType
from app.modules.audit.models import RuleEvaluation
from app.modules.audit.service import RuleEvaluationService
from app.modules.fit.assessment import (
    RequirementAssessmentValidator,
)
from app.modules.fit.compatibility import CompatibilityAssessmentRules
from app.modules.fit.providers import (
    SemanticAssessmentProvider,
)
from app.modules.fit.ranking import (
    EvidenceRelevanceRanker,
)
from app.modules.fit.retrieval import (
    CareerEvidenceRetriever,
)
from app.modules.fit.schemas import (
    EvidenceRankingResult,
    FitResult,
    RequirementAssessment,
    RequirementAssessmentProposal,
    SemanticAssessmentRequest,
)
from app.modules.fit.semantic import (
    SemanticAssessmentRequestBuilder,
)
from app.modules.fit.service import (
    FitEvaluationService,
)
from app.modules.governance.models import Source
from app.modules.opportunities.models import (
    JobRequirement,
    Opportunity,
)


@dataclass(frozen=True)
class PreparedRequirementAssessmentContext:
    requirement: JobRequirement
    ranking_result: EvidenceRankingResult


class RequirementAssessmentPipeline:
    def __init__(
        self,
        retriever: CareerEvidenceRetriever | None = None,
        ranker: EvidenceRelevanceRanker | None = None,
        validator: RequirementAssessmentValidator | None = None,
        fit_service: FitEvaluationService | None = None,
        audit_service: RuleEvaluationService | None = None,
        semantic_request_builder: (SemanticAssessmentRequestBuilder | None) = None,
    ) -> None:
        self.compatibility_rules = CompatibilityAssessmentRules()
        self.retriever = retriever or CareerEvidenceRetriever()

        self.ranker = ranker or EvidenceRelevanceRanker()

        self.validator = validator or RequirementAssessmentValidator()

        self.fit_service = fit_service or FitEvaluationService()

        self.audit_service = audit_service or RuleEvaluationService()

        self.semantic_request_builder = (
            semantic_request_builder or SemanticAssessmentRequestBuilder()
        )

    def _load_canonical_requirements(
        self,
        session: Session,
        opportunity_id: uuid.UUID,
    ) -> list[JobRequirement]:
        opportunity = session.scalar(
            select(Opportunity)
            .join(
                Source,
                Opportunity.jd_source_id == Source.source_id,
            )
            .where(
                Opportunity.opportunity_id == opportunity_id,
                Source.source_type == SourceType.JD.value,
                Source.authority_level == "CANONICAL_JD",
                Source.immutable.is_(True),
            )
        )

        if opportunity is None:
            raise ValueError(
                "Requirement assessment requires "
                "an existing Opportunity backed by "
                "an immutable canonical JD Source."
            )

        return list(
            session.scalars(
                select(JobRequirement)
                .where(JobRequirement.opportunity_id == opportunity_id)
                .order_by(JobRequirement.requirement_key)
            ).all()
        )

    def prepare_context(
        self,
        session: Session,
        *,
        opportunity_id: uuid.UUID,
    ) -> list[PreparedRequirementAssessmentContext]:
        requirements = self._load_canonical_requirements(
            session=session,
            opportunity_id=opportunity_id,
        )

        contexts: list[PreparedRequirementAssessmentContext] = []

        for requirement in requirements:
            candidate_set = self.retriever.retrieve_for_requirement(
                session=session,
                requirement=requirement,
            )

            ranking_result = self.ranker.rank(
                requirement=requirement,
                candidate_set=candidate_set,
            )

            contexts.append(
                PreparedRequirementAssessmentContext(
                    requirement=requirement,
                    ranking_result=ranking_result,
                )
            )

        return contexts

    @staticmethod
    def _validate_provider_proposal_against_request(
        *,
        request: SemanticAssessmentRequest,
        proposal: RequirementAssessmentProposal,
    ) -> None:
        if proposal.requirement_key != request.requirement.requirement_key:
            raise ValueError(
                "Provider assessment proposal "
                "requirement_key must match the "
                "semantic assessment request."
            )

        supplied_ids = {evidence.profile_fact_id for evidence in request.ranked_evidence}

        cited_ids = {evidence.profile_fact_id for evidence in proposal.evidence}

        unsupplied_ids = cited_ids - supplied_ids

        if unsupplied_ids:
            raise ValueError(
                "Provider assessment evidence must "
                "come from the exact semantic "
                "assessment request evidence. "
                "Unsupplied profile_fact_id values: "
                f"{sorted(str(value) for value in unsupplied_ids)}"
            )

    @staticmethod
    def _validate_provider_telemetry_identity(
        *,
        provider: SemanticAssessmentProvider,
        provider_name: str,
        provider_version: str,
    ) -> None:
        if provider_name != provider.provider_name or provider_version != provider.provider_version:
            raise ValueError(
                "Semantic assessment telemetry provider identity must match the active provider."
            )

    def propose_with_provider(
        self,
        session: Session,
        *,
        opportunity_id: uuid.UUID,
        provider: SemanticAssessmentProvider,
    ) -> tuple[
        list[RequirementAssessmentProposal],
        dict[str, dict],
    ]:
        contexts = self.prepare_context(
            session=session,
            opportunity_id=opportunity_id,
        )

        proposals: list[RequirementAssessmentProposal] = []

        provider_telemetry: dict[
            str,
            dict,
        ] = {}

        for context in contexts:
            request = self.semantic_request_builder.build(
                requirement=context.requirement,
                ranking_result=(context.ranking_result),
            )

            proposal, telemetry = self._propose_validated(
                provider=provider,
                request=request,
                context=context,
            )
            if telemetry is not None:
                provider_telemetry[context.requirement.requirement_key] = telemetry

            proposals.append(proposal)

        return (
            proposals,
            provider_telemetry,
        )

    def _propose_validated(self, *, provider, request, context):
        attempts = []
        proposal = None
        validation_error = None
        for attempt in range(2):
            telemetry = None
            try:
                if attempt:
                    repair = getattr(provider, "repair_with_telemetry", None)
                    if not callable(repair):
                        raise ValueError(validation_error)
                    result = repair(
                        request=request,
                        proposal=proposal,
                        validation_error=validation_error,
                    )
                    proposal, telemetry = result.proposal, result.telemetry
                else:
                    propose = getattr(provider, "propose_with_telemetry", None)
                    if callable(propose):
                        result = propose(request=request)
                        proposal, telemetry = result.proposal, result.telemetry
                    else:
                        proposal = provider.propose(request=request)
                if telemetry is not None:
                    self._validate_provider_telemetry_identity(
                        provider=provider,
                        provider_name=telemetry.provider_name,
                        provider_version=telemetry.provider_version,
                    )
                self._validate_provider_proposal_against_request(
                    request=request,
                    proposal=proposal,
                )
                self.validator.validate(
                    proposal=proposal,
                    ranking_result=context.ranking_result,
                )
                self.compatibility_rules.validate(request=request, proposal=proposal)
            except ValueError as error:
                proposal = getattr(error, "provider_proposal", proposal)
                validation_error = str(error)
                attempts.append(
                    {
                        "proposal": proposal.model_dump(mode="json") if proposal else None,
                        "telemetry": telemetry.model_dump(mode="json") if telemetry else None,
                        "validation_error": validation_error,
                    }
                )
                if attempt or not callable(getattr(provider, "repair_with_telemetry", None)):
                    # The caller can export failed attempts even if its transaction rolls back.
                    error.assessment_attempts = attempts
                    raise
            else:
                payload = telemetry.model_dump(mode="json") if telemetry else None
                if attempts:
                    attempts.append(
                        {
                            "proposal": proposal.model_dump(mode="json"),
                            "telemetry": payload,
                            "validation_error": None,
                        }
                    )
                    payload = dict(payload or {})
                    payload["validation_attempts"] = attempts
                return proposal, payload

    def _validate_proposal_keys(
        self,
        *,
        contexts: list[PreparedRequirementAssessmentContext],
        proposals: list[RequirementAssessmentProposal],
    ) -> None:
        proposal_keys = [proposal.requirement_key for proposal in proposals]

        if len(proposal_keys) != len(set(proposal_keys)):
            raise ValueError("Duplicate requirement assessment proposals are not allowed.")

        canonical_keys = {context.requirement.requirement_key for context in contexts}

        provided_keys = set(proposal_keys)

        if canonical_keys != provided_keys:
            missing_keys = sorted(canonical_keys - provided_keys)

            extra_keys = sorted(provided_keys - canonical_keys)

            raise ValueError(
                "Assessment proposal keys must "
                "exactly match the canonical "
                "JobRequirements. "
                f"Missing: {missing_keys}. "
                f"Extra: {extra_keys}."
            )

    def _build_assessment_audit_input(
        self,
        *,
        opportunity_id: uuid.UUID,
        contexts: list[PreparedRequirementAssessmentContext],
        proposals: list[RequirementAssessmentProposal],
        proposal_origin: dict | None = None,
        provider_telemetry: dict[
            str,
            dict,
        ]
        | None = None,
    ) -> dict:
        context_payloads = []

        for context in contexts:
            requirement = context.requirement
            ranking = context.ranking_result

            context_payloads.append(
                {
                    "requirement": {
                        "requirement_key": (requirement.requirement_key),
                        "description": (requirement.description),
                        "priority": requirement.priority,
                        "category": requirement.category,
                        "blocking": requirement.blocking,
                        "evidence_text": (requirement.evidence_text),
                    },
                    "ranking": {
                        "requirement_key": (ranking.requirement_key),
                        "requirement_category": (ranking.requirement_category.value),
                        "retrieval_rule_version": (ranking.retrieval_rule_version),
                        "ranking_rule_version": (ranking.ranking_rule_version),
                        "ranking_method": (ranking.ranking_method),
                        "total_candidate_count": (ranking.total_candidate_count),
                        "used_fallback": (ranking.used_fallback),
                        "ranked_candidates": [
                            {
                                "profile_fact_id": str(ranked.candidate.profile_fact_id),
                                "fact_type": (ranked.candidate.fact_type.value),
                                "tier": (ranked.candidate.tier.value),
                                "relevance_score": (ranked.relevance_score),
                                "matched_terms": (ranked.matched_terms),
                                "exact_phrase_matches": (ranked.exact_phrase_matches),
                            }
                            for ranked in ranking.ranked_candidates
                        ],
                    },
                }
            )

        rules_snapshot = {
            "compatibility_assessment": {
                "version": self.compatibility_rules.VERSION,
                "guards": [
                    "residency_requires_actual_fact_and_scope",
                    "vehicle_requires_explicit_ownership",
                    "salary_boundary_overlap_is_conditional",
                    "conditional_onsite_acceptance_is_not_match",
                ],
            },
            "evidence_retrieval": (self.retriever.policy.config),
            "evidence_ranking": (self.ranker.policy.config),
            "requirement_assessment": (self.validator.policy.config),
        }

        resolved_origin = proposal_origin or {
            "mode": "manual",
        }

        if resolved_origin.get("mode") == "provider":
            rules_snapshot["semantic_assessment"] = self.semantic_request_builder.policy.config

            rules_snapshot["semantic_evidence_projection"] = (
                self.semantic_request_builder.projector.policy.config
            )

        audit_input = {
            "opportunity_id": str(opportunity_id),
            "proposal_origin": resolved_origin,
            "contexts": context_payloads,
            "proposals": [proposal.model_dump(mode="json") for proposal in proposals],
            "rules_snapshot": rules_snapshot,
        }

        if provider_telemetry:
            audit_input["provider_telemetry"] = provider_telemetry

        return audit_input

    def evaluate_proposals_and_record(
        self,
        session: Session,
        *,
        opportunity_id: uuid.UUID,
        proposals: list[RequirementAssessmentProposal],
        proposal_origin: dict | None = None,
        provider_telemetry: dict[
            str,
            dict,
        ]
        | None = None,
    ) -> tuple[
        FitResult,
        RuleEvaluation,
        RuleEvaluation,
        list[RequirementAssessment],
    ]:
        contexts = self.prepare_context(
            session=session,
            opportunity_id=opportunity_id,
        )

        self._validate_proposal_keys(
            contexts=contexts,
            proposals=proposals,
        )

        proposal_by_key = {proposal.requirement_key: proposal for proposal in proposals}

        assessments: list[RequirementAssessment] = []

        for context in contexts:
            requirement_key = context.requirement.requirement_key

            proposal = proposal_by_key[requirement_key]

            assessment = self.validator.validate(
                proposal=proposal,
                ranking_result=(context.ranking_result),
            )

            request = self.semantic_request_builder.build(
                requirement=context.requirement,
                ranking_result=context.ranking_result,
            )
            self.compatibility_rules.validate(request=request, proposal=proposal)
            assessments.append(assessment)

        assessment_input = self._build_assessment_audit_input(
            opportunity_id=opportunity_id,
            contexts=contexts,
            proposals=proposals,
            proposal_origin=proposal_origin,
            provider_telemetry=provider_telemetry,
        )

        assessment_evaluation = self.audit_service.record(
            session,
            rule_set="requirement_assessment",
            ruleset_version=(self.validator.policy.version),
            input_payload=assessment_input,
            result_json={
                "assessments": [assessment.model_dump(mode="json") for assessment in assessments]
            },
            entity_type="opportunity",
            entity_id=opportunity_id,
        )

        result, fit_evaluation = self.fit_service.evaluate_opportunity_and_record(
            session=session,
            opportunity_id=opportunity_id,
            assessments=assessments,
        )

        return (
            result,
            fit_evaluation,
            assessment_evaluation,
            assessments,
        )

    def evaluate_with_provider_and_record(
        self,
        session: Session,
        *,
        opportunity_id: uuid.UUID,
        provider: SemanticAssessmentProvider,
    ) -> tuple[
        FitResult,
        RuleEvaluation,
        RuleEvaluation,
        list[RequirementAssessment],
        list[RequirementAssessmentProposal],
    ]:
        (
            proposals,
            provider_telemetry,
        ) = self.propose_with_provider(
            session=session,
            opportunity_id=opportunity_id,
            provider=provider,
        )

        proposal_origin = {
            "mode": "provider",
            "provider_name": (provider.provider_name),
            "provider_version": (provider.provider_version),
            "semantic_rule_version": (self.semantic_request_builder.policy.version),
            "projection_rule_version": (self.semantic_request_builder.projector.version),
        }

        (
            result,
            fit_evaluation,
            assessment_evaluation,
            assessments,
        ) = self.evaluate_proposals_and_record(
            session=session,
            opportunity_id=opportunity_id,
            proposals=proposals,
            proposal_origin=proposal_origin,
            provider_telemetry=provider_telemetry,
        )

        return (
            result,
            fit_evaluation,
            assessment_evaluation,
            assessments,
            proposals,
        )
