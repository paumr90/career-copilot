from typing import (
    Protocol,
    runtime_checkable,
)

from app.modules.opportunities.schemas import (
    JDExtractionProposal,
    RawJobDescriptionInput,
)


@runtime_checkable
class JDExtractionProvider(Protocol):
    @property
    def provider_name(self) -> str:
        ...

    @property
    def provider_version(self) -> str:
        ...

    def extract(
        self,
        *,
        raw_job: RawJobDescriptionInput,
    ) -> JDExtractionProposal:
        ...


class StaticJDExtractionProvider:
    """
    Local deterministic provider for development
    and tests.

    It performs no extraction validation and makes
    no network calls. Its output is deliberately
    treated as untrusted until it passes through
    JDExtractionValidator.
    """

    def __init__(
        self,
        *,
        proposal: JDExtractionProposal,
    ) -> None:
        self._proposal = proposal.model_copy(
            deep=True
        )

    @property
    def provider_name(self) -> str:
        return "static_local"

    @property
    def provider_version(self) -> str:
        return "0.1"

    def extract(
        self,
        *,
        raw_job: RawJobDescriptionInput,
    ) -> JDExtractionProposal:
        _ = raw_job

        return self._proposal.model_copy(
            deep=True
        )