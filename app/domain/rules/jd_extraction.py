from pathlib import Path
from typing import Any

import yaml

from app.domain.enums import (
    RequirementCategory,
    RequirementPriority,
)
from app.modules.opportunities.schemas import (
    JobDescriptionInput,
    JobRequirementInput,
)


DEFAULT_JD_EXTRACTION_PATH = (
    Path(__file__).resolve().parents[3]
    / "rules"
    / "jd_extraction.yaml"
)


class JDExtractionPolicy:
    EXPECTED_ROLE = (
        "job_description_requirement_extractor"
    )

    EXPECTED_REQUIREMENT_KEY_FORMAT = (
        "snake_case"
    )

    EXPECTED_PRIORITY_RULES = set(
        RequirementPriority
    )

    def __init__(
        self,
        config_path: Path | None = None,
    ) -> None:
        self.config_path = (
            config_path
            or DEFAULT_JD_EXTRACTION_PATH
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
                "JD extraction configuration "
                "must be a mapping."
            )

        return config

    def _validate_config(self) -> None:
        if self.config.get("role") != (
            self.EXPECTED_ROLE
        ):
            raise ValueError(
                "JD extraction role must be "
                f"'{self.EXPECTED_ROLE}'."
            )

        if self.config.get(
            "output_schema"
        ) != JobDescriptionInput.__name__:
            raise ValueError(
                "JD extraction output_schema "
                "must match JobDescriptionInput."
            )

        self._validate_requirement_contract()
        self._validate_priorities()
        self._validate_categories()
        self._validate_blocking_rules()
        self._validate_ambiguity_rules()
        self._validate_rule_lists()

    def _validate_requirement_contract(
        self,
    ) -> None:
        contract = self.config.get(
            "requirement_contract"
        )

        if not isinstance(contract, dict):
            raise ValueError(
                "requirement_contract must "
                "be a mapping."
            )

        configured_fields = set(
            contract.get(
                "required_fields",
                [],
            )
        )

        schema_fields = set(
            JobRequirementInput.model_fields
        )

        if configured_fields != schema_fields:
            missing = sorted(
                schema_fields - configured_fields
            )

            extra = sorted(
                configured_fields - schema_fields
            )

            raise ValueError(
                "JD extraction requirement fields "
                "do not match JobRequirementInput. "
                f"Missing: {missing}. "
                f"Extra: {extra}."
            )

        key_config = contract.get(
            "requirement_key"
        )

        if not isinstance(
            key_config,
            dict,
        ):
            raise ValueError(
                "requirement_key configuration "
                "must be a mapping."
            )

        if key_config.get("format") != (
            self.EXPECTED_REQUIREMENT_KEY_FORMAT
        ):
            raise ValueError(
                "requirement_key format must be "
                "'snake_case'."
            )

        if key_config.get("unique") is not True:
            raise ValueError(
                "requirement_key.unique "
                "must be true."
            )

        evidence_config = contract.get(
            "evidence_text"
        )

        if not isinstance(
            evidence_config,
            dict,
        ):
            raise ValueError(
                "evidence_text configuration "
                "must be a mapping."
            )

        required_evidence_rules = {
            "required": True,
            "must_be_verbatim_from_jd": True,
            "must_be_contiguous_substring": True,
            "prefer_smallest_sufficient_fragment": True,
        }

        for (
            key,
            expected_value,
        ) in required_evidence_rules.items():
            if evidence_config.get(
                key
            ) is not expected_value:
                raise ValueError(
                    "JD extraction evidence_text "
                    f"rule '{key}' must be true."
                )

    def _validate_priorities(self) -> None:
        priority_rules = self.config.get(
            "priority_rules"
        )

        if not isinstance(
            priority_rules,
            dict,
        ):
            raise ValueError(
                "priority_rules must "
                "be a mapping."
            )

        try:
            configured_priorities = {
                RequirementPriority(value)
                for value in priority_rules
            }
        except ValueError as exc:
            raise ValueError(
                "priority_rules contains an "
                "unknown RequirementPriority."
            ) from exc

        if (
            configured_priorities
            != self.EXPECTED_PRIORITY_RULES
        ):
            expected = sorted(
                priority.value
                for priority
                in self.EXPECTED_PRIORITY_RULES
            )

            configured = sorted(
                priority.value
                for priority
                in configured_priorities
            )

            raise ValueError(
                "priority_rules must define every "
                "RequirementPriority exactly. "
                f"Expected: {expected}. "
                f"Configured: {configured}."
            )

        for (
            priority,
            priority_config,
        ) in priority_rules.items():
            if not isinstance(
                priority_config,
                dict,
            ):
                raise ValueError(
                    f"{priority} priority rule "
                    "must be a mapping."
                )

            allowed_when = (
                priority_config.get(
                    "allowed_when"
                )
            )

            self._validate_non_empty_strings(
                allowed_when,
                label=(
                    f"{priority}.allowed_when"
                ),
            )

    def _validate_categories(self) -> None:
        categories = self.config.get(
            "categories"
        )

        if not isinstance(categories, dict):
            raise ValueError(
                "categories must be a mapping."
            )

        configured_categories = set(
            categories.get(
                "allowed",
                [],
            )
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
                "JD extraction categories do not "
                "match RequirementCategory. "
                f"Missing: {missing}. "
                f"Extra: {extra}."
            )

        guidance = categories.get(
            "guidance"
        )

        if not isinstance(
            guidance,
            dict,
        ):
            raise ValueError(
                "categories.guidance must "
                "be a mapping."
            )

        if set(guidance) != (
            expected_categories
        ):
            missing = sorted(
                expected_categories
                - set(guidance)
            )

            extra = sorted(
                set(guidance)
                - expected_categories
            )

            raise ValueError(
                "Category guidance does not cover "
                "RequirementCategory exactly. "
                f"Missing: {missing}. "
                f"Extra: {extra}."
            )

        for (
            category,
            category_guidance,
        ) in guidance.items():
            self._validate_non_empty_strings(
                category_guidance,
                label=(
                    "categories.guidance."
                    f"{category}"
                ),
            )

    def _validate_blocking_rules(
        self,
    ) -> None:
        blocking_rules = self.config.get(
            "blocking_rules"
        )

        if not isinstance(
            blocking_rules,
            dict,
        ):
            raise ValueError(
                "blocking_rules must "
                "be a mapping."
            )

        if blocking_rules.get(
            "default"
        ) is not False:
            raise ValueError(
                "blocking_rules.default "
                "must be false."
            )

        self._validate_non_empty_strings(
            blocking_rules.get(
                "blocking_true_requires"
            ),
            label=(
                "blocking_true_requires"
            ),
        )

        self._validate_non_empty_strings(
            blocking_rules.get(
                "principles"
            ),
            label=(
                "blocking_rules.principles"
            ),
        )

    def _validate_ambiguity_rules(
        self,
    ) -> None:
        ambiguity_rules = self.config.get(
            "ambiguity_rules"
        )

        if not isinstance(
            ambiguity_rules,
            dict,
        ):
            raise ValueError(
                "ambiguity_rules must "
                "be a mapping."
            )

        if ambiguity_rules.get(
            "uncertain_priority"
        ) != RequirementPriority.SECONDARY.value:
            raise ValueError(
                "uncertain_priority must "
                "be SECONDARY."
            )

        if ambiguity_rules.get(
            "uncertain_blocking"
        ) is not False:
            raise ValueError(
                "uncertain_blocking must "
                "be false."
            )

        if ambiguity_rules.get(
            "uncertain_category"
        ) != RequirementCategory.OTHER.value:
            raise ValueError(
                "uncertain_category must "
                "be OTHER."
            )

        self._validate_non_empty_strings(
            ambiguity_rules.get(
                "principle"
            ),
            label=(
                "ambiguity_rules.principle"
            ),
        )

    def _validate_rule_lists(self) -> None:
        self._validate_non_empty_strings(
            self.config.get(
                "extraction_rules"
            ),
            label="extraction_rules",
        )

        self._validate_non_empty_strings(
            self.config.get(
                "forbidden"
            ),
            label="forbidden",
        )

        self._validate_non_empty_strings(
            self.config.get(
                "principles"
            ),
            label="principles",
        )

    @staticmethod
    def _validate_non_empty_strings(
        values: Any,
        *,
        label: str,
    ) -> None:
        if (
            not isinstance(values, list)
            or not values
            or not all(
                isinstance(value, str)
                and value.strip()
                for value in values
            )
        ):
            raise ValueError(
                f"{label} must be a non-empty "
                "list of strings."
            )

    @property
    def version(self) -> str:
        return str(self.config["version"])

    @property
    def role(self) -> str:
        return str(self.config["role"])

    @property
    def output_schema(self) -> str:
        return str(
            self.config["output_schema"]
        )

    @property
    def allowed_categories(
        self,
    ) -> set[RequirementCategory]:
        return {
            RequirementCategory(value)
            for value in self.config[
                "categories"
            ]["allowed"]
        }

    @property
    def explicit_priorities(
        self,
    ) -> set[RequirementPriority]:
        return {
            RequirementPriority(value)
            for value in self.config[
                "priority_rules"
            ]
        }

    @property
    def uncertain_priority(
        self,
    ) -> RequirementPriority:
        return RequirementPriority(
            self.config[
                "ambiguity_rules"
            ]["uncertain_priority"]
        )

    @property
    def uncertain_category(
        self,
    ) -> RequirementCategory:
        return RequirementCategory(
            self.config[
                "ambiguity_rules"
            ]["uncertain_category"]
        )

    @property
    def uncertain_blocking(self) -> bool:
        return bool(
            self.config[
                "ambiguity_rules"
            ]["uncertain_blocking"]
        )

    @property
    def maximum_requirement_fields(
        self,
    ) -> set[str]:
        return set(
            self.config[
                "requirement_contract"
            ]["required_fields"]
        )