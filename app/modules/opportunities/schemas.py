from pydantic import BaseModel, Field, model_validator

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

    @model_validator(mode="after")
    def validate_unique_requirement_keys(
        self,
    ) -> "JobDescriptionInput":
        requirement_keys = [
            requirement.requirement_key
            for requirement in self.requirements
        ]

        if len(requirement_keys) != len(set(requirement_keys)):
            raise ValueError(
                "Duplicate requirement_key values are not allowed "
                "within the same job description."
            )

        return self