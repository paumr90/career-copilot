from typing import Protocol, runtime_checkable

from app.modules.fit.schemas import (
    RequirementAssessmentProposal,
    SemanticAssessmentRequest,
)


@runtime_checkable
class SemanticAssessmentProvider(Protocol):
    @property
    def provider_name(self) -> str:
        ...

    @property
    def provider_version(self) -> str:
        ...

    def propose(
        self,
        *,
        request: SemanticAssessmentRequest,
    ) -> RequirementAssessmentProposal:
        ...


class StaticSemanticAssessmentProvider:
    """
    Local deterministic provider for development and tests.

    It performs no semantic validation and makes no network
    calls. Configured proposals are deliberately treated as
    untrusted output so downstream assessment guardrails remain
    the authority.
    """

    def __init__(
        self,
        *,
        proposals: dict[
            str,
            RequirementAssessmentProposal,
        ],
    ) -> None:
        self._proposals = {
            requirement_key: proposal.model_copy(
                deep=True
            )
            for requirement_key, proposal
            in proposals.items()
        }

    @property
    def provider_name(self) -> str:
        return "static_local"

    @property
    def provider_version(self) -> str:
        return "0.1"

    def propose(
        self,
        *,
        request: SemanticAssessmentRequest,
    ) -> RequirementAssessmentProposal:
        requirement_key = (
            request.requirement.requirement_key
        )

        proposal = self._proposals.get(
            requirement_key
        )

        if proposal is None:
            raise ValueError(
                "Static semantic assessment provider "
                "has no proposal configured for "
                f"requirement_key '{requirement_key}'."
            )

        return proposal.model_copy(
            deep=True
        )