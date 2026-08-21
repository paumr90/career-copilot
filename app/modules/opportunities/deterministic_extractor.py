import re

from app.domain.enums import (
    RequirementCategory,
    RequirementPriority,
)
from app.modules.opportunities.schemas import (
    JDExtractionProposal,
    JDExtractionRequest,
    JobRequirementInput,
)


SEGMENT_PATTERN = re.compile(
    r"[^.\n!?]+(?:[.!?]+|$)"
)

NEGATED_REQUIREMENT_PATTERNS = (
    re.compile(
        r"\bnot\s+required\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bnot\s+mandatory\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bnot\s+essential\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bno\s+experience\s+required\b",
        re.IGNORECASE,
    ),
)

MUST_HAVE_PATTERNS = (
    re.compile(
        r"\bmust\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\brequired\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bmandatory\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bminimum\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bessential\b",
        re.IGNORECASE,
    ),
)

NICE_TO_HAVE_PATTERNS = (
    re.compile(
        r"\bpreferred\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdesirable\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bnice[\s-]+to[\s-]+have\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\ba\s+plus\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\badvantage\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bideally\b",
        re.IGNORECASE,
    ),
)

SECONDARY_REQUIREMENT_PATTERNS = (
    re.compile(
        r"\bexperience\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\byears?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdegree\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bqualification\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bcertification\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bproficiency\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bknowledge\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bskills?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bfluent\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\blanguage\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\btravel\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bhybrid\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bremote\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bbased\s+in\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\brelocat",
        re.IGNORECASE,
    ),
)

RESPONSIBILITY_ONLY_PATTERNS = (
    re.compile(
        r"^\s*(?:you\s+will|you'll)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:responsibilities|what\s+you'll\s+do)\b",
        re.IGNORECASE,
    ),
)


class DeterministicJDExtractionProvider:
    """
    Conservative offline JD extractor.

    This provider exists to prove the automated
    extraction pipeline without network calls or
    model inference.

    It only extracts text segments that contain
    explicit requirement signals or conservative
    candidate-qualification signals.

    Its output remains untrusted and must always
    pass through JDExtractionValidator.
    """

    @property
    def provider_name(self) -> str:
        return "deterministic_local"

    @property
    def provider_version(self) -> str:
        return "0.1"

    def extract(
        self,
        *,
        request: JDExtractionRequest,
    ) -> JDExtractionProposal:
        requirements: list[
            JobRequirementInput
        ] = []

        used_keys: set[str] = set()

        for evidence_text in self._segments(
            request.raw_text
        ):
            if self._is_negated_requirement(
                evidence_text
            ):
                continue

            priority = self._classify_priority(
                evidence_text
            )

            if priority is None:
                continue

            category = self._classify_category(
                evidence_text
            )

            description = self._description(
                evidence_text
            )

            requirement_key = (
                self._requirement_key(
                    description=description,
                    category=category,
                    used_keys=used_keys,
                )
            )

            requirements.append(
                JobRequirementInput(
                    requirement_key=(
                        requirement_key
                    ),
                    description=description,
                    priority=priority,
                    category=category,
                    blocking=False,
                    evidence_text=evidence_text,
                )
            )

        return JDExtractionProposal(
            requirements=requirements
        )

    @staticmethod
    def _segments(
        raw_text: str,
    ) -> list[str]:
        segments: list[str] = []

        for match in SEGMENT_PATTERN.finditer(
            raw_text
        ):
            segment = match.group(0).strip()

            if segment:
                segments.append(segment)

        return segments

    @staticmethod
    def _matches_any(
        text: str,
        patterns: tuple[
            re.Pattern[str],
            ...,
        ],
    ) -> bool:
        return any(
            pattern.search(text)
            for pattern in patterns
        )

    def _is_negated_requirement(
        self,
        text: str,
    ) -> bool:
        return self._matches_any(
            text,
            NEGATED_REQUIREMENT_PATTERNS,
        )

    def _classify_priority(
        self,
        text: str,
    ) -> RequirementPriority | None:
        if self._matches_any(
            text,
            MUST_HAVE_PATTERNS,
        ):
            return RequirementPriority.MUST_HAVE

        if self._matches_any(
            text,
            NICE_TO_HAVE_PATTERNS,
        ):
            return RequirementPriority.NICE_TO_HAVE

        if self._matches_any(
            text,
            RESPONSIBILITY_ONLY_PATTERNS,
        ):
            return None

        if self._matches_any(
            text,
            SECONDARY_REQUIREMENT_PATTERNS,
        ):
            return RequirementPriority.SECONDARY

        return None

    @staticmethod
    def _classify_category(
        text: str,
    ) -> RequirementCategory:
        lowered = text.lower()

        if any(
            term in lowered
            for term in (
                "salary",
                "compensation",
                "remuneration",
                "base pay",
                "pay range",
            )
        ):
            return RequirementCategory.COMPENSATION

        if any(
            term in lowered
            for term in (
                "hybrid",
                "remote",
                "on-site",
                "onsite",
                "office presence",
            )
        ):
            return RequirementCategory.WORK_MODE

        if any(
            term in lowered
            for term in (
                "based in",
                "located in",
                "relocate",
                "relocation",
                "location",
            )
        ):
            return RequirementCategory.LOCATION

        if any(
            term in lowered
            for term in (
                "language",
                "fluent",
                "fluency",
                "english",
                "spanish",
                "catalan",
                "french",
                "german",
            )
        ):
            return RequirementCategory.LANGUAGE

        if any(
            term in lowered
            for term in (
                "degree",
                "bachelor",
                "master",
                "phd",
                "university",
                "academic qualification",
            )
        ):
            return RequirementCategory.EDUCATION

        if any(
            term in lowered
            for term in (
                "software",
                "platform",
                "cloud",
                "artificial intelligence",
                "machine learning",
                "data",
                "sql",
                "sap",
                "salesforce",
                "jira",
                "power bi",
                "tableau",
                "azure",
                "aws",
                "gcp",
            )
        ):
            return RequirementCategory.TECHNOLOGY

        if any(
            term in lowered
            for term in (
                "industry",
                "sector",
                "banking",
                "financial services",
                "pharma",
                "pharmaceutical",
                "healthcare",
                "manufacturing",
                "automotive",
            )
        ):
            return RequirementCategory.INDUSTRY

        if any(
            term in lowered
            for term in (
                "experience",
                "years",
                "background",
                "track record",
            )
        ):
            return RequirementCategory.EXPERIENCE

        if any(
            term in lowered
            for term in (
                "lead ",
                "manage ",
                "responsible for",
                "ownership",
                "own ",
            )
        ):
            return RequirementCategory.RESPONSIBILITY

        if any(
            term in lowered
            for term in (
                "skill",
                "ability",
                "knowledge",
                "communication",
                "analytical",
                "stakeholder",
            )
        ):
            return RequirementCategory.SKILL

        return RequirementCategory.OTHER

    @staticmethod
    def _description(
        evidence_text: str,
    ) -> str:
        description = re.sub(
            r"^[\s\-*•]+",
            "",
            evidence_text,
        ).strip()

        return description

    @staticmethod
    def _slugify(
        text: str,
    ) -> str:
        slug = re.sub(
            r"[^a-z0-9]+",
            "_",
            text.lower(),
        )

        slug = slug.strip("_")

        return slug

    def _requirement_key(
        self,
        *,
        description: str,
        category: RequirementCategory,
        used_keys: set[str],
    ) -> str:
        slug = self._slugify(
            description
        )

        if not slug:
            slug = category.value.lower()

        base_key = slug[:120].rstrip("_")

        if not base_key:
            base_key = (
                category.value.lower()
            )

        candidate = base_key
        suffix = 2

        while candidate in used_keys:
            suffix_text = f"_{suffix}"

            candidate = (
                base_key[
                    : 150 - len(suffix_text)
                ]
                + suffix_text
            )

            suffix += 1

        used_keys.add(candidate)

        return candidate