from app.domain.enums import (
    EvidenceTier,
    MatchStatus,
)
from app.domain.rules.requirement_assessment import (
    RequirementAssessmentPolicy,
)
from app.modules.fit.schemas import (
    EvidenceRankingResult,
    RequirementAssessment,
    RequirementAssessmentProposal,
)


class RequirementAssessmentValidator:
    def __init__(
        self,
        policy: RequirementAssessmentPolicy | None = None,
    ) -> None:
        self.policy = (
            policy or RequirementAssessmentPolicy()
        )

    def validate(
        self,
        *,
        proposal: RequirementAssessmentProposal,
        ranking_result: EvidenceRankingResult,
    ) -> RequirementAssessment:
        if (
            proposal.requirement_key
            != ranking_result.requirement_key
        ):
            raise ValueError(
                "Assessment proposal requirement_key "
                "must match the ranked requirement."
            )

        if (
            len(proposal.evidence)
            > self.policy.maximum_cited_evidence
        ):
            raise ValueError(
                "Assessment proposal cites more evidence "
                "than maximum_cited_evidence allows."
            )

        ranked_candidates_by_id = {
            ranked.candidate.profile_fact_id:
                ranked.candidate
            for ranked
            in ranking_result.ranked_candidates
        }

        cited_ids = {
            evidence.profile_fact_id
            for evidence in proposal.evidence
        }

        if self.policy.cited_evidence_must_be_ranked:
            unranked_ids = (
                cited_ids
                - set(ranked_candidates_by_id)
            )

            if unranked_ids:
                raise ValueError(
                    "Assessment evidence must come "
                    "from the governed ranked shortlist. "
                    f"Unranked profile_fact_id values: "
                    f"{sorted(str(value) for value in unranked_ids)}"
                )

        status = proposal.proposed_status

        if (
            proposal.evidence
            and not self.policy.evidence_allowed(
                status
            )
        ):
            raise ValueError(
                f"{status.value} does not allow "
                "cited evidence."
            )

        primary_count = sum(
            1
            for evidence in proposal.evidence
            if (
                evidence.profile_fact_id
                in ranked_candidates_by_id
                and ranked_candidates_by_id[
                    evidence.profile_fact_id
                ].tier
                == EvidenceTier.PRIMARY
            )
        )

        minimum_primary = (
            self.policy.minimum_primary_evidence(
                status
            )
        )

        if primary_count < minimum_primary:
            raise ValueError(
                f"{status.value} requires at least "
                f"{minimum_primary} PRIMARY evidence "
                "reference(s) from the ranked shortlist."
            )

        if (
            proposal.evidence
            and primary_count == 0
            and not self.policy.supporting_only_allowed(
                status
            )
        ):
            raise ValueError(
                f"{status.value} cannot be established "
                "using SUPPORTING evidence only."
            )

        if status == MatchStatus.GAP:
            if (
                self.policy.explicit_gap_basis_required
                and proposal.gap_basis is None
            ):
                raise ValueError(
                    "GAP requires an explicit gap_basis."
                )

            if (
                proposal.gap_basis is not None
                and proposal.gap_basis
                not in self.policy.allowed_gap_bases
            ):
                raise ValueError(
                    "GAP uses a gap_basis not allowed "
                    "by the assessment policy."
                )

        elif proposal.gap_basis is not None:
            raise ValueError(
                "gap_basis is only valid when "
                "proposed_status is GAP."
            )

        return RequirementAssessment(
            requirement_key=proposal.requirement_key,
            match_status=status,
            evidence=proposal.evidence,
            rationale=proposal.rationale,
            gap_basis=proposal.gap_basis,
        )