from pathlib import Path
from typing import Any

import yaml

from app.domain.enums import EvidenceTier


DEFAULT_EVIDENCE_RANKING_PATH = (
    Path(__file__).resolve().parents[3]
    / "rules"
    / "evidence_ranking.yaml"
)


class EvidenceRankingPolicy:
    def __init__(
        self,
        config_path: Path | None = None,
    ) -> None:
        self.config_path = (
            config_path or DEFAULT_EVIDENCE_RANKING_PATH
        )

        self.config = self._load_config()
        self._validate_config()

    def _load_config(self) -> dict[str, Any]:
        with self.config_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            config = yaml.safe_load(file)

        if not isinstance(config, dict):
            raise ValueError(
                "Evidence ranking configuration "
                "must be a mapping."
            )

        return config

    def _validate_config(self) -> None:
        if self.config.get("method") != (
            "deterministic_lexical_shortlisting"
        ):
            raise ValueError(
                "Unsupported evidence ranking method."
            )

        max_candidates = self.config.get(
            "max_ranked_candidates"
        )

        if (
            not isinstance(max_candidates, int)
            or max_candidates < 1
        ):
            raise ValueError(
                "max_ranked_candidates must be "
                "a positive integer."
            )

        expected_requirement_fields = {
            "requirement_key",
            "description",
            "evidence_text",
        }

        configured_requirement_fields = set(
            self.config[
                "requirement_field_weights"
            ].keys()
        )

        if (
            configured_requirement_fields
            != expected_requirement_fields
        ):
            raise ValueError(
                "requirement_field_weights must define "
                "requirement_key, description and "
                "evidence_text."
            )

        expected_candidate_fields = {
            "subject",
            "value_json",
        }

        configured_candidate_fields = set(
            self.config[
                "candidate_field_weights"
            ].keys()
        )

        if (
            configured_candidate_fields
            != expected_candidate_fields
        ):
            raise ValueError(
                "candidate_field_weights must define "
                "subject and value_json."
            )

        expected_tiers = {
            tier.value
            for tier in EvidenceTier
        }

        configured_tiers = set(
            self.config["tier_weights"].keys()
        )

        if configured_tiers != expected_tiers:
            raise ValueError(
                "tier_weights must exactly match "
                "EvidenceTier."
            )

        weight_groups = [
            self.config[
                "requirement_field_weights"
            ],
            self.config[
                "candidate_field_weights"
            ],
            self.config["tier_weights"],
        ]

        for weight_group in weight_groups:
            for value in weight_group.values():
                if (
                    not isinstance(
                        value,
                        (int, float),
                    )
                    or value < 0
                ):
                    raise ValueError(
                        "Evidence ranking weights must "
                        "be non-negative numbers."
                    )

        exact_phrase_bonus = self.config.get(
            "exact_phrase_bonus"
        )

        if (
            not isinstance(
                exact_phrase_bonus,
                (int, float),
            )
            or exact_phrase_bonus < 0
        ):
            raise ValueError(
                "exact_phrase_bonus must be a "
                "non-negative number."
            )

        normalization = self.config.get(
            "lexical_normalization"
        )

        if not isinstance(normalization, dict):
            raise ValueError(
                "lexical_normalization must be "
                "a mapping."
            )

        min_token_length = normalization.get(
            "min_token_length"
        )

        if (
            not isinstance(min_token_length, int)
            or min_token_length < 1
        ):
            raise ValueError(
                "min_token_length must be "
                "a positive integer."
            )

        stopwords = normalization.get("stopwords")

        if not isinstance(stopwords, list):
            raise ValueError(
                "lexical_normalization.stopwords "
                "must be a list."
            )

        fallback = self.config.get("fallback")

        if not isinstance(fallback, dict):
            raise ValueError(
                "fallback must be a mapping."
            )

        fallback_max = fallback.get(
            "max_candidates"
        )

        if (
            not isinstance(fallback_max, int)
            or fallback_max < 1
            or fallback_max > max_candidates
        ):
            raise ValueError(
                "fallback.max_candidates must be "
                "between 1 and max_ranked_candidates."
            )

    @property
    def version(self) -> str:
        return str(self.config["version"])

    @property
    def method(self) -> str:
        return str(self.config["method"])

    @property
    def max_ranked_candidates(self) -> int:
        return int(
            self.config["max_ranked_candidates"]
        )

    @property
    def requirement_field_weights(
        self,
    ) -> dict[str, float]:
        return {
            key: float(value)
            for key, value in self.config[
                "requirement_field_weights"
            ].items()
        }

    @property
    def candidate_field_weights(
        self,
    ) -> dict[str, float]:
        return {
            key: float(value)
            for key, value in self.config[
                "candidate_field_weights"
            ].items()
        }

    def get_tier_weight(
        self,
        tier: EvidenceTier,
    ) -> float:
        return float(
            self.config["tier_weights"][
                tier.value
            ]
        )

    @property
    def exact_phrase_bonus(self) -> float:
        return float(
            self.config["exact_phrase_bonus"]
        )

    @property
    def stopwords(self) -> set[str]:
        return {
            str(value)
            for value in self.config[
                "lexical_normalization"
            ]["stopwords"]
        }

    @property
    def min_token_length(self) -> int:
        return int(
            self.config[
                "lexical_normalization"
            ]["min_token_length"]
        )

    @property
    def strip_accents(self) -> bool:
        return bool(
            self.config[
                "lexical_normalization"
            ]["strip_accents"]
        )

    @property
    def lowercase(self) -> bool:
        return bool(
            self.config[
                "lexical_normalization"
            ]["lowercase"]
        )

    @property
    def fallback_enabled(self) -> bool:
        return bool(
            self.config["fallback"]["enabled"]
        )

    @property
    def fallback_max_candidates(self) -> int:
        return int(
            self.config["fallback"][
                "max_candidates"
            ]
        )

    @property
    def fallback_prefer_primary(self) -> bool:
        return bool(
            self.config["fallback"][
                "prefer_primary"
            ]
        )