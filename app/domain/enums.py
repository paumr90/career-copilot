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