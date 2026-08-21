import re

from app.domain.enums import (
    RequirementPriority,
)
from app.domain.rules.jd_extraction import (
    JDExtractionPolicy,
)
from app.modules.opportunities.schemas import (
    JobDescriptionInput,
)


SNAKE_CASE_PATTERN = re.compile(
    r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$"
)


class JDExtractionValidator:
    def __init__(
        self,
        policy: JDExtractionPolicy | None = None,
    ) -> None:
        self.policy = (
            policy or JDExtractionPolicy()
        )

    def validate(
        self,
        extraction: JobDescriptionInput,
    ) -> JobDescriptionInput:
        raw_text = extraction.raw_text

        if not raw_text.strip():
            raise ValueError(
                "Job Description raw_text "
                "cannot be empty."
            )

        for requirement in extraction.requirements:
            self._validate_requirement_key(
                requirement.requirement_key
            )

            self._validate_evidence_text(
                raw_text=raw_text,
                evidence_text=(
                    requirement.evidence_text
                ),
                requirement_key=(
                    requirement.requirement_key
                ),
            )

            self._validate_blocking(
                priority=requirement.priority,
                blocking=requirement.blocking,
                requirement_key=(
                    requirement.requirement_key
                ),
            )

        return extraction

    @staticmethod
    def _validate_requirement_key(
        requirement_key: str,
    ) -> None:
        if not SNAKE_CASE_PATTERN.fullmatch(
            requirement_key
        ):
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
        if (
            evidence_text is None
            or not evidence_text
        ):
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
        if (
            blocking
            and priority
            != RequirementPriority.MUST_HAVE
        ):
            raise ValueError(
                "blocking=True is only valid "
                "for MUST_HAVE requirements. "
                f"Requirement: "
                f"'{requirement_key}'."
            )