import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.enums import SourceType
from app.modules.governance.models import Source
from app.modules.opportunities.models import JobRequirement, Opportunity
from app.modules.opportunities.schemas import JobDescriptionInput


class OpportunityService:
    @staticmethod
    def calculate_snapshot_hash(raw_text: str) -> str:
        return hashlib.sha256(
            raw_text.encode("utf-8")
        ).hexdigest()

    def create_from_job_description(
        self,
        session: Session,
        job_description: JobDescriptionInput,
        *,
        external_id: str | None = None,
        uri: str | None = None,
        captured_at: datetime | None = None,
    ) -> tuple[Source, Opportunity, list[JobRequirement]]:
        snapshot_hash = self.calculate_snapshot_hash(
            job_description.raw_text
        )

        source = Source(
            source_type=SourceType.JD.value,
            external_id=external_id,
            uri=uri,
            captured_at=captured_at or datetime.now(timezone.utc),
            snapshot_hash=snapshot_hash,
            metadata_json={
                "company": job_description.company,
                "role_title": job_description.role_title,
                "location": job_description.location,
                "requirements_count": len(
                    job_description.requirements
                ),
            },
            authority_level="CANONICAL_JD",
            immutable=True,
        )

        session.add(source)
        session.flush()

        opportunity = Opportunity(
            jd_source_id=source.source_id,
            company=job_description.company,
            role_title=job_description.role_title,
            location=job_description.location,
            raw_text=job_description.raw_text,
        )

        session.add(opportunity)
        session.flush()

        requirements: list[JobRequirement] = []

        for requirement_input in job_description.requirements:
            requirement = JobRequirement(
                opportunity_id=opportunity.opportunity_id,
                requirement_key=requirement_input.requirement_key,
                description=requirement_input.description,
                priority=requirement_input.priority.value,
                category=requirement_input.category.value,
                blocking=requirement_input.blocking,
                evidence_text=requirement_input.evidence_text,
            )

            session.add(requirement)
            requirements.append(requirement)

        session.flush()

        return source, opportunity, requirements