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