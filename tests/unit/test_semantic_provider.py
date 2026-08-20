import uuid

import pytest

from app.domain.enums import (
    MatchStatus,
    RequirementCategory,
    RequirementPriority,
)
from app.modules.fit.providers import (
    SemanticAssessmentProvider,
    StaticSemanticAssessmentProvider,
)
from app.modules.fit.schemas import (
    ProfileEvidenceReference,
    RequirementAssessmentProposal,
    SemanticAssessmentRequest,
    SemanticAssessmentRequirement,
)


def build_request(
    *,
    requirement_key: str = "project_management",
) -> SemanticAssessmentRequest:
    return SemanticAssessmentRequest(
        semantic_rule_version="0.1",
        retrieval_rule_version="0.1",
        ranking_rule_version="0.1",
        requirement=SemanticAssessmentRequirement(
            requirement_key=requirement_key,
            description=(
                "Experience managing complex projects"
            ),
            priority=RequirementPriority.MUST_HAVE,
            category=RequirementCategory.EXPERIENCE,
            blocking=False,
            evidence_text=(
                "Project management experience required."
            ),
        ),
        ranked_evidence=[],
    )


def test_static_provider_implements_protocol() -> None:
    provider = StaticSemanticAssessmentProvider(
        proposals={}
    )

    assert isinstance(
        provider,
        SemanticAssessmentProvider,
    )

    assert provider.provider_name == "static_local"
    assert provider.provider_version == "0.1"


def test_static_provider_returns_configured_proposal() -> None:
    proposal = RequirementAssessmentProposal(
        requirement_key="project_management",
        proposed_status=MatchStatus.UNKNOWN,
        evidence=[],
        rationale=(
            "Insufficient evidence for a "
            "defensible conclusion."
        ),
    )

    provider = StaticSemanticAssessmentProvider(
        proposals={
            "project_management": proposal,
        }
    )

    result = provider.propose(
        request=build_request()
    )

    assert result == proposal

    assert result is not proposal


def test_static_provider_rejects_missing_configuration() -> None:
    provider = StaticSemanticAssessmentProvider(
        proposals={}
    )

    with pytest.raises(
        ValueError,
        match=(
            "has no proposal configured for "
            "requirement_key"
        ),
    ):
        provider.propose(
            request=build_request()
        )


def test_provider_output_remains_untrusted() -> None:
    invented_evidence_id = uuid.uuid4()

    untrusted_proposal = (
        RequirementAssessmentProposal(
            requirement_key=(
                "project_management"
            ),
            proposed_status=MatchStatus.MATCH,
            evidence=[
                ProfileEvidenceReference(
                    profile_fact_id=(
                        invented_evidence_id
                    ),
                    note=(
                        "Provider-supplied reference."
                    ),
                )
            ],
            rationale=(
                "Provider claims this is a match."
            ),
        )
    )

    provider = StaticSemanticAssessmentProvider(
        proposals={
            "project_management":
                untrusted_proposal,
        }
    )

    result = provider.propose(
        request=build_request()
    )

    assert (
        result.proposed_status
        == MatchStatus.MATCH
    )

    assert (
        result.evidence[0].profile_fact_id
        == invented_evidence_id
    )