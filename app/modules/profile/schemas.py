from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import (
    EvidenceState,
    ProfileFactType,
    SourceType,
)


class SeedManifest(BaseModel):
    seed_version: str
    schema_version: str
    source_title: str
    source_type: SourceType = SourceType.PROFILE
    exported_at: datetime
    content_hash: str | None = None


class ProfileFactSeed(BaseModel):
    fact_type: ProfileFactType
    subject: str = Field(min_length=1, max_length=255)
    value: dict[str, Any]
    evidence_state: EvidenceState
    valid_from: date | None = None
    valid_to: date | None = None


class CareerProfileSeed(BaseModel):
    manifest: SeedManifest
    facts: list[ProfileFactSeed]