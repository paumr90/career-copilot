from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from app.domain.enums import (
    RequirementCategory,
    RequirementPriority,
)
from app.domain.rules.jd_extraction import (
    JDExtractionPolicy,
)
from app.modules.opportunities.schemas import (
    JobRequirementInput,
)


def write_config(
    tmp_path: Path,
    config: dict,
) -> Path:
    config_path = (
        tmp_path
        / "jd_extraction_test.yaml"
    )

    config_path.write_text(
        yaml.safe_dump(
            config,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    return config_path


def test_default_policy_matches_domain_contract() -> None:
    policy = JDExtractionPolicy()

    assert policy.version == "0.3"

    assert policy.role == (
        "job_description_requirement_extractor"
    )

    assert policy.output_schema == (
        "JDExtractionProposal"
    )

    assert policy.allowed_categories == set(
        RequirementCategory
    )

    assert policy.explicit_priorities == set(
        RequirementPriority
    )

    assert (
        policy.uncertain_priority
        == RequirementPriority.SECONDARY
    )

    assert (
        policy.uncertain_category
        == RequirementCategory.OTHER
    )

    assert policy.uncertain_blocking is False

    assert (
        policy.maximum_requirement_fields
        == set(
            JobRequirementInput.model_fields
        )
    )


def test_wrong_output_schema_is_rejected(
    tmp_path: Path,
) -> None:
    base_policy = JDExtractionPolicy()
    config = deepcopy(base_policy.config)

    config["output_schema"] = (
        "JobDescriptionInput"
    )

    config_path = write_config(
        tmp_path,
        config,
    )

    with pytest.raises(
        ValueError,
        match=(
            "JD extraction output_schema "
            "must match JDExtractionProposal"
        ),
    ):
        JDExtractionPolicy(
            config_path=config_path
        )


def test_missing_priority_rule_is_rejected(
    tmp_path: Path,
) -> None:
    base_policy = JDExtractionPolicy()
    config = deepcopy(base_policy.config)
    config["priority_rules"].pop("SECONDARY")
    config_path = write_config(tmp_path, config)

    with pytest.raises(
        ValueError,
        match=(
            "priority_rules must define every "
            "RequirementPriority exactly"
        ),
    ):
        JDExtractionPolicy(config_path=config_path)


def test_unknown_priority_rule_is_rejected(
    tmp_path: Path,
) -> None:
    base_policy = JDExtractionPolicy()
    config = deepcopy(base_policy.config)
    config["priority_rules"]["MANDATORY_PLUS"] = {
        "allowed_when": [
            "Invalid test priority."
        ]
    }
    config_path = write_config(tmp_path, config)

    with pytest.raises(
        ValueError,
        match=(
            "priority_rules contains an "
            "unknown RequirementPriority"
        ),
    ):
        JDExtractionPolicy(config_path=config_path)


def test_unknown_category_is_rejected(
    tmp_path: Path,
) -> None:
    base_policy = JDExtractionPolicy()
    config = deepcopy(base_policy.config)
    config["categories"]["allowed"].append(
        "PERSONALITY_SCORE"
    )
    config_path = write_config(tmp_path, config)

    with pytest.raises(
        ValueError,
        match=(
            "JD extraction categories do not "
            "match RequirementCategory"
        ),
    ):
        JDExtractionPolicy(config_path=config_path)


def test_uncertain_priority_must_be_secondary(
    tmp_path: Path,
) -> None:
    base_policy = JDExtractionPolicy()
    config = deepcopy(base_policy.config)
    config["ambiguity_rules"][
        "uncertain_priority"
    ] = "MUST_HAVE"
    config_path = write_config(tmp_path, config)

    with pytest.raises(
        ValueError,
        match=(
            "uncertain_priority must "
            "be SECONDARY"
        ),
    ):
        JDExtractionPolicy(config_path=config_path)


def test_blocking_default_must_be_false(
    tmp_path: Path,
) -> None:
    base_policy = JDExtractionPolicy()
    config = deepcopy(base_policy.config)
    config["blocking_rules"]["default"] = True
    config_path = write_config(tmp_path, config)

    with pytest.raises(
        ValueError,
        match=(
            "blocking_rules.default "
            "must be false"
        ),
    ):
        JDExtractionPolicy(config_path=config_path)


def test_requirement_fields_must_match_schema(
    tmp_path: Path,
) -> None:
    base_policy = JDExtractionPolicy()
    config = deepcopy(base_policy.config)
    config[
        "requirement_contract"
    ][
        "required_fields"
    ].remove(
        "evidence_text"
    )
    config_path = write_config(tmp_path, config)

    with pytest.raises(
        ValueError,
        match=(
            "JD extraction requirement fields "
            "do not match JobRequirementInput"
        ),
    ):
        JDExtractionPolicy(config_path=config_path)


def test_verbatim_evidence_rule_cannot_be_disabled(
    tmp_path: Path,
) -> None:
    base_policy = JDExtractionPolicy()
    config = deepcopy(base_policy.config)
    config[
        "requirement_contract"
    ][
        "evidence_text"
    ][
        "must_be_verbatim_from_jd"
    ] = False
    config_path = write_config(tmp_path, config)

    with pytest.raises(
        ValueError,
        match=(
            "JD extraction evidence_text "
            "rule 'must_be_verbatim_from_jd' "
            "must be true"
        ),
    ):
        JDExtractionPolicy(config_path=config_path)