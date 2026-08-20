from pydantic import BaseModel, Field

from app.domain.enums import (
    RequirementCategory,
    RequirementPriority,
)


class JobRequirementInput(BaseModel):
    requirement_key: str = Field(
        min_length=1,
        max_length=150,
    )

    description: str = Field(
        min_length=1,
        max_length=2000,
    )

    priority: RequirementPriority

    category: RequirementCategory

    blocking: bool = False

    evidence_text: str | None = Field(
        default=None,
        max_length=4000,
    )


class JobDescriptionInput(BaseModel):
    company: str = Field(
        min_length=1,
        max_length=255,
    )

    role_title: str = Field(
        min_length=1,
        max_length=255,
    )

    location: str | None = Field(
        default=None,
        max_length=255,
    )

    raw_text: str = Field(
        min_length=1,
    )

    requirements: list[JobRequirementInput]