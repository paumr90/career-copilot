import pytest

from app.domain.rules.source_authority import SourceAuthorityPolicy


def test_source_authority_rules_version() -> None:
    policy = SourceAuthorityPolicy()

    assert policy.version == "0.1"


def test_profile_source_has_priority_over_cv() -> None:
    policy = SourceAuthorityPolicy()

    winner = policy.compare_sources(
        domain="professional_profile",
        source_type_a="PROFILE",
        source_type_b="CV",
    )

    assert winner == "PROFILE"


def test_ats_has_priority_over_email_for_application_status() -> None:
    policy = SourceAuthorityPolicy()

    winner = policy.compare_sources(
        domain="application_status",
        source_type_a="ATS",
        source_type_b="EMAIL",
    )

    assert winner == "ATS"


def test_email_has_priority_over_user_for_application_status() -> None:
    policy = SourceAuthorityPolicy()

    winner = policy.compare_sources(
        domain="application_status",
        source_type_a="EMAIL",
        source_type_b="USER",
    )

    assert winner == "EMAIL"


def test_equal_priority_returns_tie() -> None:
    policy = SourceAuthorityPolicy()

    winner = policy.compare_sources(
        domain="professional_profile",
        source_type_a="UNKNOWN_SOURCE_A",
        source_type_b="UNKNOWN_SOURCE_B",
    )

    assert winner == "TIE"


def test_unknown_domain_is_rejected() -> None:
    policy = SourceAuthorityPolicy()

    with pytest.raises(ValueError, match="Unknown authority domain"):
        policy.get_priority(
            domain="unknown_domain",
            source_type="PROFILE",
        )