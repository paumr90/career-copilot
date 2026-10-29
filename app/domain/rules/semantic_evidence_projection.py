from pathlib import Path
from typing import Any

import yaml

from app.domain.enums import (
    ProfileFactType,
    RequirementCategory,
)
from app.domain.rules.evidence_retrieval import (
    EvidenceRetrievalPolicy,
)


DEFAULT_SEMANTIC_EVIDENCE_PROJECTION_PATH = (
    Path(__file__).resolve().parents[3]
    / "rules"
    / "semantic_evidence_projection.yaml"
)


class SemanticEvidenceProjectionPolicy:
    def __init__(
        self,
        config_path: Path | None = None,
        retrieval_policy: (
            EvidenceRetrievalPolicy | None
        ) = None,
    ) -> None:
        self.config_path = (
            config_path
            or DEFAULT_SEMANTIC_EVIDENCE_PROJECTION_PATH
        )

        self.retrieval_policy = (
            retrieval_policy
            or EvidenceRetrievalPolicy()
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
                "Semantic evidence projection "
                "configuration must be a mapping."
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

        if (
            configured_categories
            != expected_categories
        ):
            missing = sorted(
                expected_categories
                - configured_categories
            )

            extra = sorted(
                configured_categories
                - expected_categories
            )

            raise ValueError(
                "Semantic evidence projection "
                "categories do not match "
                "RequirementCategory. "
                f"Missing: {missing}. "
                f"Extra: {extra}."
            )

        for category in RequirementCategory:
            category_config = self.config[
                "requirement_categories"
            ][category.value]

            if not isinstance(
                category_config,
                dict,
            ):
                raise ValueError(
                    "Semantic evidence projection "
                    f"{category.value} configuration "
                    "must be a mapping."
                )

            configured_fact_types = {
                ProfileFactType(
                    fact_type
                )
                for fact_type
                in category_config
            }

            retrieval_fact_types = (
                self._retrieval_fact_types(
                    category
                )
            )

            if (
                configured_fact_types
                != retrieval_fact_types
            ):
                missing = sorted(
                    fact_type.value
                    for fact_type
                    in (
                        retrieval_fact_types
                        - configured_fact_types
                    )
                )

                extra = sorted(
                    fact_type.value
                    for fact_type
                    in (
                        configured_fact_types
                        - retrieval_fact_types
                    )
                )

                raise ValueError(
                    "Semantic evidence projection "
                    f"{category.value} fact types "
                    "must exactly match evidence "
                    "retrieval eligibility. "
                    f"Missing: {missing}. "
                    f"Extra: {extra}."
                )

            for (
                fact_type,
                allowed_fields,
            ) in category_config.items():
                if not isinstance(
                    allowed_fields,
                    list,
                ):
                    raise ValueError(
                        "Semantic evidence projection "
                        f"{category.value}.{fact_type} "
                        "must be a list."
                    )

                if len(allowed_fields) != len(
                    set(allowed_fields)
                ):
                    raise ValueError(
                        "Semantic evidence projection "
                        f"{category.value}.{fact_type} "
                        "cannot contain duplicate "
                        "field names."
                    )

                for field_name in allowed_fields:
                    if (
                        not isinstance(
                            field_name,
                            str,
                        )
                        or not field_name.strip()
                    ):
                        raise ValueError(
                            "Semantic evidence projection "
                            f"{category.value}.{fact_type} "
                            "field names must be "
                            "non-empty strings."
                        )

    def _retrieval_fact_types(
        self,
        category: RequirementCategory,
    ) -> set[ProfileFactType]:
        primary = (
            self.retrieval_policy
            .get_primary_fact_types(
                category
            )
        )

        supporting = (
            self.retrieval_policy
            .get_supporting_fact_types(
                category
            )
        )

        conditional = []
        if category == RequirementCategory.OTHER:
            conditional = [
                ProfileFactType(value) for value in self.retrieval_policy.config.get(
                    "conditional_retrieval", {}
                ).get("own_vehicle_primary_fact_types", [])
            ]
        return set(primary) | set(supporting) | set(conditional)

    @property
    def version(self) -> str:
        return str(
            self.config["version"]
        )

    def allowed_fields(
        self,
        *,
        category: RequirementCategory,
        fact_type: ProfileFactType,
    ) -> tuple[str, ...]:
        category_config = self.config[
            "requirement_categories"
        ][category.value]

        fields = category_config.get(
            fact_type.value
        )

        if fields is None:
            raise ValueError(
                "ProfileFactType "
                f"'{fact_type.value}' is not "
                "eligible for requirement category "
                f"'{category.value}'."
            )

        return tuple(fields)