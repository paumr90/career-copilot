from enum import StrEnum


class SourceType(StrEnum):
    PROFILE = "PROFILE"
    CV = "CV"
    JD = "JD"
    EMAIL = "EMAIL"
    ATS = "ATS"
    USER = "USER"
    INTERVIEW = "INTERVIEW"
    FEEDBACK = "FEEDBACK"


class EvidenceState(StrEnum):
    CONFIRMED = "CONFIRMED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class ProfileFactType(StrEnum):
    PROFESSIONAL_SUMMARY = "professional_summary"
    EMPLOYMENT = "employment"
    EDUCATION = "education"
    CERTIFICATION = "certification"
    SKILL = "skill"
    LANGUAGE = "language"
    PROJECT = "project"
    ACHIEVEMENT = "achievement"
    POSITIONING = "positioning"
    CAREER_OBJECTIVE = "career_objective"
    WORK_PREFERENCE = "work_preference"
    COMPENSATION_PREFERENCE = "compensation_preference"


class RequirementPriority(StrEnum):
    MUST_HAVE = "MUST_HAVE"
    NICE_TO_HAVE = "NICE_TO_HAVE"
    SECONDARY = "SECONDARY"


class RequirementCategory(StrEnum):
    EXPERIENCE = "EXPERIENCE"
    EDUCATION = "EDUCATION"
    SKILL = "SKILL"
    LANGUAGE = "LANGUAGE"
    INDUSTRY = "INDUSTRY"
    TECHNOLOGY = "TECHNOLOGY"
    RESPONSIBILITY = "RESPONSIBILITY"
    LOCATION = "LOCATION"
    WORK_MODE = "WORK_MODE"
    COMPENSATION = "COMPENSATION"
    OTHER = "OTHER"


class MatchStatus(StrEnum):
    MATCH = "MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    GAP = "GAP"
    UNKNOWN = "UNKNOWN"


class GapBasis(StrEnum):
    EXPLICIT_CONTRADICTION = "EXPLICIT_CONTRADICTION"
    NUMERIC_SHORTFALL = "NUMERIC_SHORTFALL"
    EXPLICIT_NON_COMPLIANCE = "EXPLICIT_NON_COMPLIANCE"


class FitRecommendation(StrEnum):
    APPLY = "APPLY"
    REVIEW = "REVIEW"
    NO_APPLY = "NO_APPLY"


class EvidenceTier(StrEnum):
    PRIMARY = "PRIMARY"
    SUPPORTING = "SUPPORTING"

class CriterionType(StrEnum):
    CONTEXT = "CONTEXT"
    ROLE_CAPABILITY = "ROLE_CAPABILITY"
    ESSENTIAL = "ESSENTIAL"
    DESIRABLE = "DESIRABLE"
    UNCLASSIFIED = "UNCLASSIFIED"
    PRACTICAL_CONDITION = "PRACTICAL_CONDITION"
