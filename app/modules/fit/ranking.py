import json
import re
import unicodedata

from app.domain.enums import EvidenceTier
from app.domain.rules.evidence_ranking import (
    EvidenceRankingPolicy,
)
from app.modules.fit.schemas import (
    CareerEvidenceCandidate,
    EvidenceCandidateSet,
    EvidenceRankingResult,
    RankedEvidenceCandidate,
)
from app.modules.opportunities.models import (
    JobRequirement,
)


class EvidenceRelevanceRanker:
    def __init__(
        self,
        policy: EvidenceRankingPolicy | None = None,
    ) -> None:
        self.policy = (
            policy or EvidenceRankingPolicy()
        )

    def _normalize_text(
        self,
        value: str,
    ) -> str:
        text = value

        if self.policy.lowercase:
            text = text.lower()

        if self.policy.strip_accents:
            text = "".join(
                character
                for character in unicodedata.normalize(
                    "NFKD",
                    text,
                )
                if not unicodedata.combining(
                    character
                )
            )

        text = text.replace("_", " ")

        return " ".join(
            re.findall(
                r"[a-zA-Z0-9]+",
                text,
            )
        )

    def _tokenize(
        self,
        value: str,
    ) -> set[str]:
        normalized = self._normalize_text(
            value
        )

        return {
            token
            for token in normalized.split()
            if (
                len(token)
                >= self.policy.min_token_length
                and token
                not in self.policy.stopwords
            )
        }

    def _normalized_phrase(
        self,
        value: str,
    ) -> str:
        tokens = self._tokenize(value)

        return " ".join(
            sorted(tokens)
        )

    def _serialize_value_json(
        self,
        value_json: dict,
    ) -> str:
        return json.dumps(
            value_json,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )

    def _candidate_sort_key(
        self,
        candidate: CareerEvidenceCandidate,
    ) -> tuple[int, str, str, str]:
        tier_order = {
            EvidenceTier.PRIMARY: 0,
            EvidenceTier.SUPPORTING: 1,
        }

        return (
            tier_order[candidate.tier],
            candidate.fact_type.value,
            candidate.subject.lower(),
            str(candidate.profile_fact_id),
        )

    def _validate_inputs(
        self,
        requirement: JobRequirement,
        candidate_set: EvidenceCandidateSet,
    ) -> None:
        if (
            requirement.requirement_key
            != candidate_set.requirement_key
        ):
            raise ValueError(
                "Requirement key does not match "
                "EvidenceCandidateSet requirement_key."
            )

        if (
            requirement.category
            != candidate_set.requirement_category.value
        ):
            raise ValueError(
                "Requirement category does not match "
                "EvidenceCandidateSet requirement_category."
            )

        for candidate in (
            candidate_set.primary_candidates
        ):
            if (
                candidate.tier
                != EvidenceTier.PRIMARY
            ):
                raise ValueError(
                    "primary_candidates must contain "
                    "only PRIMARY evidence."
                )

        for candidate in (
            candidate_set.supporting_candidates
        ):
            if (
                candidate.tier
                != EvidenceTier.SUPPORTING
            ):
                raise ValueError(
                    "supporting_candidates must contain "
                    "only SUPPORTING evidence."
                )

        candidate_ids = [
            candidate.profile_fact_id
            for candidate in (
                candidate_set.primary_candidates
                + candidate_set.supporting_candidates
            )
        ]

        if len(candidate_ids) != len(
            set(candidate_ids)
        ):
            raise ValueError(
                "EvidenceCandidateSet contains "
                "duplicate profile_fact_id values."
            )

    def _score_candidate(
        self,
        requirement: JobRequirement,
        candidate: CareerEvidenceCandidate,
    ) -> RankedEvidenceCandidate:
        requirement_fields = {
            "requirement_key": (
                requirement.requirement_key
            ),
            "description": requirement.description,
            "evidence_text": (
                requirement.evidence_text or ""
            ),
        }

        candidate_fields = {
            "subject": candidate.subject,
            "value_json": (
                self._serialize_value_json(
                    candidate.value_json
                )
            ),
        }

        relevance_score = 0.0
        matched_terms: set[str] = set()
        exact_phrase_matches: set[str] = set()

        tier_weight = (
            self.policy.get_tier_weight(
                candidate.tier
            )
        )

        for (
            requirement_field_name,
            requirement_value,
        ) in requirement_fields.items():
            requirement_tokens = self._tokenize(
                requirement_value
            )

            if not requirement_tokens:
                continue

            requirement_weight = (
                self.policy.requirement_field_weights[
                    requirement_field_name
                ]
            )

            for (
                candidate_field_name,
                candidate_value,
            ) in candidate_fields.items():
                candidate_tokens = self._tokenize(
                    candidate_value
                )

                candidate_weight = (
                    self.policy.candidate_field_weights[
                        candidate_field_name
                    ]
                )

                overlap = (
                    requirement_tokens
                    & candidate_tokens
                )

                if overlap:
                    matched_terms.update(overlap)

                    relevance_score += (
                        len(overlap)
                        * requirement_weight
                        * candidate_weight
                        * tier_weight
                    )

                normalized_requirement_phrase = (
                    self._normalized_phrase(
                        requirement_value
                    )
                )

                normalized_candidate_phrase = (
                    self._normalized_phrase(
                        candidate_value
                    )
                )

                if (
                    normalized_requirement_phrase
                    and len(
                        normalized_requirement_phrase.split()
                    )
                    >= 2
                    and normalized_requirement_phrase
                    in normalized_candidate_phrase
                ):
                    exact_phrase_matches.add(
                        normalized_requirement_phrase
                    )

                    relevance_score += (
                        self.policy.exact_phrase_bonus
                        * requirement_weight
                        * candidate_weight
                        * tier_weight
                    )

        return RankedEvidenceCandidate(
            candidate=candidate,
            relevance_score=round(
                relevance_score,
                4,
            ),
            matched_terms=sorted(
                matched_terms
            ),
            exact_phrase_matches=sorted(
                exact_phrase_matches
            ),
        )

    def _fallback_candidates(
        self,
        candidates: list[
            CareerEvidenceCandidate
        ],
    ) -> list[RankedEvidenceCandidate]:
        ordered_candidates = sorted(
            candidates,
            key=self._candidate_sort_key,
        )

        if not self.policy.fallback_prefer_primary:
            ordered_candidates = sorted(
                candidates,
                key=lambda candidate: (
                    candidate.fact_type.value,
                    candidate.subject.lower(),
                    str(candidate.profile_fact_id),
                ),
            )

        selected = ordered_candidates[
            : self.policy.fallback_max_candidates
        ]

        return [
            RankedEvidenceCandidate(
                candidate=candidate,
                relevance_score=0.0,
                matched_terms=[],
                exact_phrase_matches=[],
            )
            for candidate in selected
        ]

    def rank(
        self,
        *,
        requirement: JobRequirement,
        candidate_set: EvidenceCandidateSet,
    ) -> EvidenceRankingResult:
        self._validate_inputs(
            requirement=requirement,
            candidate_set=candidate_set,
        )

        candidates = (
            candidate_set.primary_candidates
            + candidate_set.supporting_candidates
        )

        scored_candidates = [
            self._score_candidate(
                requirement=requirement,
                candidate=candidate,
            )
            for candidate in candidates
        ]

        positive_candidates = [
            candidate
            for candidate in scored_candidates
            if candidate.relevance_score > 0
        ]

        ranked_candidates = sorted(
            positive_candidates,
            key=lambda ranked: (
                -ranked.relevance_score,
                0
                if ranked.candidate.tier
                == EvidenceTier.PRIMARY
                else 1,
                ranked.candidate.fact_type.value,
                ranked.candidate.subject.lower(),
                str(
                    ranked.candidate.profile_fact_id
                ),
            ),
        )[
            : self.policy.max_ranked_candidates
        ]

        used_fallback = False

        if (
            not ranked_candidates
            and candidates
            and self.policy.fallback_enabled
        ):
            ranked_candidates = (
                self._fallback_candidates(
                    candidates
                )
            )

            used_fallback = True

        return EvidenceRankingResult(
            requirement_key=(
                requirement.requirement_key
            ),
            requirement_category=(
                candidate_set.requirement_category
            ),
            retrieval_rule_version=(
                candidate_set.retrieval_rule_version
            ),
            ranking_rule_version=(
                self.policy.version
            ),
            ranking_method=self.policy.method,
            total_candidate_count=len(candidates),
            ranked_candidates=ranked_candidates,
            used_fallback=used_fallback,
        )