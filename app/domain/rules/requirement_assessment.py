from pathlib import Path
from typing import Any

import yaml

from app.domain.enums import (
    GapBasis,
    MatchStatus,
)


DEFAULT_REQUIREMENT_ASSESSMENT_PATH = (
    Path(__file__).resolve().parents[3]
    / "rules"
    / "requirement_assessment.yaml"
)


class RequirementAssessmentPolicy:
    def __init__(
        self,
        config_path: Path | None = None,
    ) -> None:
        self.config_path = (
            config_path
            or DEFAULT_REQUIREMENT_ASSESSMENT_PATH
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
                "Requirement assessment configuration "
                "must be a mapping."
            )

        return config

    def _validate_config(self) -> None:
        configured_statuses = set(
            self.config["statuses"].keys()
        )

        expected_statuses = {
            status.value
            for status in MatchStatus
        }

        if configured_statuses != expected_statuses:
            missing = sorted(
                expected_statuses
                - configured_statuses
            )

            extra = sorted(
                configured_statuses
                - expected_statuses
            )

            raise ValueError(
                "Requirement assessment statuses "
                "do not match MatchStatus. "
                f"Missing: {missing}. "
                f"Extra: {extra}."
            )

        configured_gap_bases = set(
            self.config["gap_bases"]
        )

        expected_gap_bases = {
            basis.value
            for basis in GapBasis
        }

        if configured_gap_bases != expected_gap_bases:
            missing = sorted(
                expected_gap_bases
                - configured_gap_bases
            )

            extra = sorted(
                configured_gap_bases
                - expected_gap_bases
            )

            raise ValueError(
                "Requirement assessment gap_bases "
                "do not match GapBasis. "
                f"Missing: {missing}. "
                f"Extra: {extra}."
            )

        for (
            status,
            status_config,
        ) in self.config["statuses"].items():
            minimum_primary = status_config.get(
                "minimum_primary_evidence"
            )

            if (
                not isinstance(
                    minimum_primary,
                    int,
                )
                or minimum_primary < 0
            ):
                raise ValueError(
                    f"{status}.minimum_primary_evidence "
                    "must be a non-negative integer."
                )

            supporting_only = status_config.get(
                "supporting_only_allowed"
            )

            if not isinstance(
                supporting_only,
                bool,
            ):
                raise ValueError(
                    f"{status}.supporting_only_allowed "
                    "must be boolean."
                )

            evidence_allowed = status_config.get(
                "evidence_allowed",
                True,
            )

            if not isinstance(
                evidence_allowed,
                bool,
            ):
                raise ValueError(
                    f"{status}.evidence_allowed "
                    "must be boolean when configured."
                )

        gap_config = self.config["statuses"][
            MatchStatus.GAP.value
        ]

        if not isinstance(
            gap_config.get(
                "explicit_gap_basis_required"
            ),
            bool,
        ):
            raise ValueError(
                "GAP.explicit_gap_basis_required "
                "must be boolean."
            )

        shortlist_rules = self.config.get(
            "shortlist_rules"
        )

        if not isinstance(
            shortlist_rules,
            dict,
        ):
            raise ValueError(
                "shortlist_rules must be a mapping."
            )

        if not isinstance(
            shortlist_rules.get(
                "cited_evidence_must_be_ranked"
            ),
            bool,
        ):
            raise ValueError(
                "cited_evidence_must_be_ranked "
                "must be boolean."
            )

        maximum_cited = shortlist_rules.get(
            "maximum_cited_evidence"
        )

        if (
            not isinstance(maximum_cited, int)
            or maximum_cited < 1
        ):
            raise ValueError(
                "maximum_cited_evidence must be "
                "a positive integer."
            )

    @property
    def version(self) -> str:
        return str(self.config["version"])

    @property
    def maximum_cited_evidence(self) -> int:
        return int(
            self.config["shortlist_rules"][
                "maximum_cited_evidence"
            ]
        )

    @property
    def cited_evidence_must_be_ranked(
        self,
    ) -> bool:
        return bool(
            self.config["shortlist_rules"][
                "cited_evidence_must_be_ranked"
            ]
        )

    def minimum_primary_evidence(
        self,
        status: MatchStatus,
    ) -> int:
        return int(
            self.config["statuses"][
                status.value
            ]["minimum_primary_evidence"]
        )

    def supporting_only_allowed(
        self,
        status: MatchStatus,
    ) -> bool:
        return bool(
            self.config["statuses"][
                status.value
            ]["supporting_only_allowed"]
        )

    def evidence_allowed(
        self,
        status: MatchStatus,
    ) -> bool:
        return bool(
            self.config["statuses"][
                status.value
            ].get(
                "evidence_allowed",
                True,
            )
        )

    @property
    def explicit_gap_basis_required(
        self,
    ) -> bool:
        return bool(
            self.config["statuses"][
                MatchStatus.GAP.value
            ]["explicit_gap_basis_required"]
        )

    @property
    def allowed_gap_bases(
        self,
    ) -> set[GapBasis]:
        return {
            GapBasis(value)
            for value in self.config[
                "gap_bases"
            ]
        }