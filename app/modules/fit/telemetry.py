from pydantic import (
    BaseModel,
    Field,
    model_validator,
)

from app.modules.fit.schemas import (
    RequirementAssessmentProposal,
)


class SemanticAssessmentTelemetry(BaseModel):
    provider_name: str = Field(
        min_length=1,
        max_length=100,
    )

    provider_version: str = Field(
        min_length=1,
        max_length=50,
    )

    model_name: str = Field(
        min_length=1,
        max_length=255,
    )

    response_id: str | None = Field(
        default=None,
        max_length=255,
    )

    input_tokens: int | None = Field(
        default=None,
        ge=0,
    )

    output_tokens: int | None = Field(
        default=None,
        ge=0,
    )

    total_tokens: int | None = Field(
        default=None,
        ge=0,
    )

    latency_ms: float = Field(
        ge=0.0,
    )

    @model_validator(mode="after")
    def validate_token_total(
        self,
    ) -> "SemanticAssessmentTelemetry":
        if (
            self.input_tokens is not None
            and self.output_tokens is not None
            and self.total_tokens is not None
            and (
                self.input_tokens
                + self.output_tokens
                != self.total_tokens
            )
        ):
            raise ValueError(
                "Semantic assessment total_tokens "
                "must equal input_tokens + "
                "output_tokens when all values "
                "are available."
            )

        return self


class SemanticAssessmentProviderResult(
    BaseModel
):
    proposal: RequirementAssessmentProposal

    telemetry: SemanticAssessmentTelemetry