import re

from app.domain.enums import (
    RequirementPriority,
)
from app.domain.rules.jd_extraction import (
    JDExtractionPolicy,
)
from app.modules.opportunities.schemas import (
    JDExtractionProposal,
    JobDescriptionInput,
    RawJobDescriptionInput,
)

SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class JDExtractionValidator:
    def __init__(
        self,
        policy: JDExtractionPolicy | None = None,
    ) -> None:
        self.policy = policy or JDExtractionPolicy()

    def validate_proposal(
        self,
        *,
        raw_job: RawJobDescriptionInput,
        proposal: JDExtractionProposal,
    ) -> JobDescriptionInput:
        extraction = JobDescriptionInput(
            company=raw_job.company,
            role_title=raw_job.role_title,
            location=raw_job.location,
            raw_text=raw_job.raw_text,
            requirements=[
                requirement.model_copy(deep=True) for requirement in proposal.requirements
            ],
        )

        return self.validate(extraction)

    def validate(
        self,
        extraction: JobDescriptionInput,
    ) -> JobDescriptionInput:
        raw_text = extraction.raw_text

        if not raw_text.strip():
            raise ValueError("Job Description raw_text cannot be empty.")

        for requirement in extraction.requirements:
            if requirement.criterion_type:
                kind = str(requirement.criterion_type)
                expected = {
                    "ESSENTIAL": "MUST_HAVE",
                    "DESIRABLE": "NICE_TO_HAVE",
                    "CONTEXT": "SECONDARY",
                    "ROLE_CAPABILITY": "SECONDARY",
                    "UNCLASSIFIED": "SECONDARY",
                }.get(kind)
                if expected and str(requirement.priority) != expected:
                    raise ValueError(f"Criterion type {kind} requires priority {expected}.")
                if not requirement.classification_reason.strip():
                    raise ValueError(
                        "Explicit criterion classification requires a source-based reason."
                    )
                if (
                    kind in {"CONTEXT", "ROLE_CAPABILITY", "DESIRABLE", "UNCLASSIFIED"}
                    and requirement.blocking
                ):
                    raise ValueError(
                        "Only explicit essential requirements or practical eligibility conditions can block."
                    )
            for excerpt in requirement.source_excerpts:
                self._validate_evidence_text(
                    raw_text=raw_text,
                    evidence_text=excerpt,
                    requirement_key=requirement.requirement_key,
                )
            self._validate_requirement_key(requirement.requirement_key)

            self._validate_evidence_text(
                raw_text=raw_text,
                evidence_text=(requirement.evidence_text),
                requirement_key=(requirement.requirement_key),
            )

            self._validate_blocking(
                priority=requirement.priority,
                blocking=requirement.blocking,
                requirement_key=(requirement.requirement_key),
            )

        return extraction

    @staticmethod
    def _validate_requirement_key(
        requirement_key: str,
    ) -> None:
        if not SNAKE_CASE_PATTERN.fullmatch(requirement_key):
            raise ValueError(
                "requirement_key must use "
                "lowercase snake_case. "
                f"Invalid value: "
                f"'{requirement_key}'."
            )

    @staticmethod
    def _validate_evidence_text(
        *,
        raw_text: str,
        evidence_text: str | None,
        requirement_key: str,
    ) -> None:
        if evidence_text is None or not evidence_text:
            raise ValueError(
                "Every extracted requirement "
                "requires non-empty evidence_text. "
                f"Requirement: "
                f"'{requirement_key}'."
            )

        if evidence_text not in raw_text:
            raise ValueError(
                "Requirement evidence_text must "
                "be a verbatim contiguous substring "
                "of the Job Description raw_text. "
                f"Requirement: "
                f"'{requirement_key}'."
            )

    @staticmethod
    def _validate_blocking(
        *,
        priority: RequirementPriority,
        blocking: bool,
        requirement_key: str,
    ) -> None:
        if blocking and priority != RequirementPriority.MUST_HAVE:
            raise ValueError(
                "blocking=True is only valid "
                "for MUST_HAVE requirements. "
                f"Requirement: "
                f"'{requirement_key}'."
            )
