from pathlib import Path
from typing import Any

import yaml

from app.domain.enums import (
    ProfileFactType,
    RequirementCategory,
)


DEFAULT_EVIDENCE_RETRIEVAL_PATH = (
    Path(__file__).resolve().parents[3]
    / "rules"
    / "evidence_retrieval.yaml"
)


class EvidenceRetrievalPolicy:
    def __init__(
        self,
        config_path: Path | None = None,
    ) -> None:
        self.config_path = (
            config_path
            or DEFAULT_EVIDENCE_RETRIEVAL_PATH
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
                "Evidence retrieval configuration "
                "must be a mapping."
            )

        return config

    def _validate_config(self) -> None:
        configured_categories = set(
            self.config[
                "requirement_categories"
            ].keys()
        )

        expected_categories = {
            category.value
            for category
            in RequirementCategory
        }

        if configured_categories != expected_categories:
            missing = sorted(
                expected_categories
                - configured_categories
            )

            extra = sorted(
                configured_categories
                - expected_categories
            )

            raise ValueError(
                "Evidence retrieval categories do "
                "not match RequirementCategory. "
                f"Missing: {missing}. "
                f"Extra: {extra}."
            )

        valid_fact_types = {
            fact_type.value
            for fact_type
            in ProfileFactType
        }

        for (
            category,
            category_config,
        ) in self.config[
            "requirement_categories"
        ].items():
            for key in (
                "primary_fact_types",
                "supporting_fact_types",
            ):
                values = category_config.get(key)

                if not isinstance(values, list):
                    raise ValueError(
                        f"{category}.{key} must "
                        "be a list."
                    )

                invalid_fact_types = sorted(
                    set(values)
                    - valid_fact_types
                )

                if invalid_fact_types:
                    raise ValueError(
                        f"{category}.{key} contains "
                        "invalid ProfileFactType "
                        f"values: {invalid_fact_types}"
                    )

            overlap = set(
                category_config[
                    "primary_fact_types"
                ]
            ) & set(
                category_config[
                    "supporting_fact_types"
                ]
            )

            if overlap:
                raise ValueError(
                    f"{category} contains fact "
                    "types in both primary and "
                    "supporting tiers: "
                    f"{sorted(overlap)}"
                )

    @property
    def version(self) -> str:
        return str(self.config["version"])

    def get_primary_fact_types(
        self,
        category: RequirementCategory,
    ) -> list[ProfileFactType]:
        values = self.config[
            "requirement_categories"
        ][category.value]["primary_fact_types"]

        return [
            ProfileFactType(value)
            for value in values
        ]

    def get_supporting_fact_types(
        self,
        category: RequirementCategory,
    ) -> list[ProfileFactType]:
        values = self.config[
            "requirement_categories"
        ][category.value][
            "supporting_fact_types"
        ]

        return [
            ProfileFactType(value)
            for value in values
        ]