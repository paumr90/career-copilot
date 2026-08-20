from pathlib import Path
from typing import Any

import yaml

from app.domain.enums import (
    FitRecommendation,
    MatchStatus,
    RequirementPriority,
)
from app.modules.fit.schemas import (
    FitResult,
    FitScoringRequirement,
)


DEFAULT_FIT_SCORING_PATH = (
    Path(__file__).resolve().parents[3]
    / "rules"
    / "fit_scoring.yaml"
)


class FitScoringPolicy:
    def __init__(
        self,
        config_path: Path | None = None,
    ) -> None:
        self.config_path = (
            config_path or DEFAULT_FIT_SCORING_PATH
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
                "Fit scoring configuration must be a mapping."
            )

        return config

    def _validate_config(self) -> None:
        required_match_statuses = {
            MatchStatus.MATCH.value,
            MatchStatus.PARTIAL_MATCH.value,
            MatchStatus.GAP.value,
        }

        configured_match_statuses = set(
            self.config["match_scores"].keys()
        )

        if (
            configured_match_statuses
            != required_match_statuses
        ):
            raise ValueError(
                "fit_scoring.yaml match_scores must define "
                "MATCH, PARTIAL_MATCH and GAP."
            )

        required_priorities = {
            RequirementPriority.MUST_HAVE.value,
            RequirementPriority.NICE_TO_HAVE.value,
            RequirementPriority.SECONDARY.value,
        }

        configured_priorities = set(
            self.config["priority_weights"].keys()
        )

        if configured_priorities != required_priorities:
            raise ValueError(
                "fit_scoring.yaml priority_weights must define "
                "MUST_HAVE, NICE_TO_HAVE and SECONDARY."
            )

        recommendation_values = [
            self.config["recommendation"][
                "at_or_above_threshold"
            ],
            self.config["recommendation"][
                "below_threshold"
            ],
            self.config["blocking_rules"][
                "blocking_must_have_gap"
            ],
            self.config["blocking_rules"][
                "blocking_must_have_partial_match"
            ],
            self.config["uncertainty_rules"][
                "any_must_have_unknown"
            ],
            self.config["uncertainty_rules"][
                "no_known_requirements"
            ],
        ]

        for value in recommendation_values:
            FitRecommendation(value)

    @property
    def version(self) -> str:
        return str(self.config["version"])

    def _recommendation_from_config(
        self,
        section: str,
        key: str,
    ) -> FitRecommendation:
        return FitRecommendation(
            self.config[section][key]
        )

    def evaluate(
        self,
        requirements: list[FitScoringRequirement],
    ) -> FitResult:
        total_weight = 0.0
        known_weight = 0.0
        earned_weight = 0.0

        blocking_gap_keys: list[str] = []
        review_required_keys: list[str] = []

        for requirement in requirements:
            priority = requirement.priority.value
            match_status = (
                requirement.assessment.match_status
            )

            weight = float(
                self.config["priority_weights"][priority]
            )

            total_weight += weight

            if match_status != MatchStatus.UNKNOWN:
                known_weight += weight

                match_score = float(
                    self.config["match_scores"][
                        match_status.value
                    ]
                )

                earned_weight += weight * match_score

            if (
                requirement.priority
                == RequirementPriority.MUST_HAVE
                and requirement.blocking
                and match_status == MatchStatus.GAP
            ):
                blocking_gap_keys.append(
                    requirement.requirement_key
                )

            if (
                requirement.priority
                == RequirementPriority.MUST_HAVE
                and requirement.blocking
                and match_status
                == MatchStatus.PARTIAL_MATCH
            ):
                review_required_keys.append(
                    requirement.requirement_key
                )

            if (
                requirement.priority
                == RequirementPriority.MUST_HAVE
                and match_status == MatchStatus.UNKNOWN
            ):
                review_required_keys.append(
                    requirement.requirement_key
                )

        if known_weight > 0:
            score = (
                earned_weight
                / known_weight
                * 100.0
            )
        else:
            score = 0.0

        if total_weight > 0:
            coverage_percent = (
                known_weight
                / total_weight
                * 100.0
            )
        else:
            coverage_percent = 0.0

        if blocking_gap_keys:
            recommendation = (
                self._recommendation_from_config(
                    "blocking_rules",
                    "blocking_must_have_gap",
                )
            )

        elif any(
            requirement.priority
            == RequirementPriority.MUST_HAVE
            and requirement.blocking
            and requirement.assessment.match_status
            == MatchStatus.PARTIAL_MATCH
            for requirement in requirements
        ):
            recommendation = (
                self._recommendation_from_config(
                    "blocking_rules",
                    "blocking_must_have_partial_match",
                )
            )

        elif any(
            requirement.priority
            == RequirementPriority.MUST_HAVE
            and requirement.assessment.match_status
            == MatchStatus.UNKNOWN
            for requirement in requirements
        ):
            recommendation = (
                self._recommendation_from_config(
                    "uncertainty_rules",
                    "any_must_have_unknown",
                )
            )

        elif known_weight == 0:
            recommendation = (
                self._recommendation_from_config(
                    "uncertainty_rules",
                    "no_known_requirements",
                )
            )

        elif (
            score
            >= float(
                self.config["recommendation"][
                    "apply_threshold"
                ]
            )
        ):
            recommendation = (
                self._recommendation_from_config(
                    "recommendation",
                    "at_or_above_threshold",
                )
            )

        else:
            recommendation = (
                self._recommendation_from_config(
                    "recommendation",
                    "below_threshold",
                )
            )

        return FitResult(
            score=round(score, 2),
            recommendation=recommendation,
            rule_version=self.version,
            known_weight=known_weight,
            total_weight=total_weight,
            coverage_percent=round(
                coverage_percent,
                2,
            ),
            blocking_gap_keys=blocking_gap_keys,
            review_required_keys=review_required_keys,
        )