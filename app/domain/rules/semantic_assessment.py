from pathlib import Path
from typing import Any

import yaml

from app.domain.enums import (
    GapBasis,
    MatchStatus,
)


DEFAULT_SEMANTIC_ASSESSMENT_PATH = (
    Path(__file__).resolve().parents[3]
    / "rules"
    / "semantic_assessment.yaml"
)


class SemanticAssessmentPolicy:
    EXPECTED_REQUIREMENT_FIELDS = {
        "requirement_key",
        "description",
        "priority",
        "category",
        "blocking",
        "evidence_text",
    }

    EXPECTED_EVIDENCE_FIELDS = {
        "profile_fact_id",
        "fact_type",
        "tier",
        "subject",
        "value_json",
        "relevance_score",
        "matched_terms",
    }

    def __init__(
        self,
        config_path: Path | None = None,
    ) -> None:
        self.config_path = (
            config_path
            or DEFAULT_SEMANTIC_ASSESSMENT_PATH
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
                "Semantic assessment configuration "
                "must be a mapping."
            )

        return config

    def _validate_config(self) -> None:
        if self.config.get("role") != (
            "requirement_assessment_proposer"
        ):
            raise ValueError(
                "Semantic assessment role must be "
                "'requirement_assessment_proposer'."
            )

        input_config = self.config.get("input")

        if not isinstance(input_config, dict):
            raise ValueError(
                "Semantic assessment input "
                "configuration must be a mapping."
            )

        requirement_fields = set(
            input_config.get(
                "include_requirement",
                [],
            )
        )

        if (
            requirement_fields
            != self.EXPECTED_REQUIREMENT_FIELDS
        ):
            missing = sorted(
                self.EXPECTED_REQUIREMENT_FIELDS
                - requirement_fields
            )

            extra = sorted(
                requirement_fields
                - self.EXPECTED_REQUIREMENT_FIELDS
            )

            raise ValueError(
                "Semantic assessment requirement "
                "fields do not match the contract. "
                f"Missing: {missing}. "
                f"Extra: {extra}."
            )

        evidence_fields = set(
            input_config.get(
                "include_ranked_evidence",
                [],
            )
        )

        if (
            evidence_fields
            != self.EXPECTED_EVIDENCE_FIELDS
        ):
            missing = sorted(
                self.EXPECTED_EVIDENCE_FIELDS
                - evidence_fields
            )

            extra = sorted(
                evidence_fields
                - self.EXPECTED_EVIDENCE_FIELDS
            )

            raise ValueError(
                "Semantic assessment evidence "
                "fields do not match the contract. "
                f"Missing: {missing}. "
                f"Extra: {extra}."
            )

        maximum_ranked_evidence = (
            input_config.get(
                "maximum_ranked_evidence"
            )
        )

        if (
            not isinstance(
                maximum_ranked_evidence,
                int,
            )
            or maximum_ranked_evidence < 1
        ):
            raise ValueError(
                "maximum_ranked_evidence must be "
                "a positive integer."
            )

        output_config = self.config.get(
            "output"
        )

        if not isinstance(
            output_config,
            dict,
        ):
            raise ValueError(
                "Semantic assessment output "
                "configuration must be a mapping."
            )

        if output_config.get("schema") != (
            "RequirementAssessmentProposal"
        ):
            raise ValueError(
                "Semantic assessment output schema "
                "must be "
                "'RequirementAssessmentProposal'."
            )

        configured_statuses = set(
            output_config.get(
                "allowed_statuses",
                [],
            )
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
                "Semantic assessment statuses "
                "do not match MatchStatus. "
                f"Missing: {missing}. "
                f"Extra: {extra}."
            )

        configured_gap_bases = set(
            output_config.get(
                "allowed_gap_bases",
                [],
            )
        )

        expected_gap_bases = {
            basis.value
            for basis in GapBasis
        }

        if (
            configured_gap_bases
            != expected_gap_bases
        ):
            missing = sorted(
                expected_gap_bases
                - configured_gap_bases
            )

            extra = sorted(
                configured_gap_bases
                - expected_gap_bases
            )

            raise ValueError(
                "Semantic assessment gap bases "
                "do not match GapBasis. "
                f"Missing: {missing}. "
                f"Extra: {extra}."
            )

        guardrails = self.config.get(
            "guardrails"
        )

        if not isinstance(
            guardrails,
            dict,
        ):
            raise ValueError(
                "Semantic assessment guardrails "
                "must be a mapping."
            )

        for key, value in guardrails.items():
            if not isinstance(value, bool):
                raise ValueError(
                    "Semantic assessment guardrail "
                    f"'{key}' must be boolean."
                )

        forbidden = self.config.get(
            "forbidden"
        )

        if (
            not isinstance(forbidden, list)
            or not forbidden
            or not all(
                isinstance(item, str)
                and item.strip()
                for item in forbidden
            )
        ):
            raise ValueError(
                "Semantic assessment forbidden "
                "rules must be a non-empty "
                "list of strings."
            )

        principles = self.config.get(
            "principles"
        )

        if (
            not isinstance(principles, list)
            or not principles
            or not all(
                isinstance(item, str)
                and item.strip()
                for item in principles
            )
        ):
            raise ValueError(
                "Semantic assessment principles "
                "must be a non-empty "
                "list of strings."
            )

    @property
    def version(self) -> str:
        return str(self.config["version"])

    @property
    def role(self) -> str:
        return str(self.config["role"])

    @property
    def maximum_ranked_evidence(self) -> int:
        return int(
            self.config["input"][
                "maximum_ranked_evidence"
            ]
        )

    @property
    def allowed_statuses(
        self,
    ) -> set[MatchStatus]:
        return {
            MatchStatus(value)
            for value in self.config[
                "output"
            ]["allowed_statuses"]
        }

    @property
    def allowed_gap_bases(
        self,
    ) -> set[GapBasis]:
        return {
            GapBasis(value)
            for value in self.config[
                "output"
            ]["allowed_gap_bases"]
        }

    @property
    def forbidden_rules(self) -> list[str]:
        return list(
            self.config["forbidden"]
        )

    @property
    def principles(self) -> list[str]:
        return list(
            self.config["principles"]
        )