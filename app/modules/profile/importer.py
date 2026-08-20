from datetime import date, datetime, time, timezone

from sqlalchemy.orm import Session

from app.modules.governance.models import ProfileFact, Source
from app.modules.profile.loader import CareerProfileSeedLoader
from app.modules.profile.schemas import CareerProfileSeed


class CareerProfileImporter:
    def __init__(self) -> None:
        self.loader = CareerProfileSeedLoader()

    def import_seed(
        self,
        session: Session,
        seed: CareerProfileSeed,
    ) -> tuple[Source, list[ProfileFact]]:
        source = Source(
            source_type=seed.manifest.source_type.value,
            external_id=seed.manifest.seed_version,
            uri=f"seed://career_master/{seed.manifest.seed_version}",
            captured_at=seed.manifest.exported_at,
            snapshot_hash=seed.manifest.content_hash,
            metadata_json={
                "source_title": seed.manifest.source_title,
                "seed_version": seed.manifest.seed_version,
                "schema_version": seed.manifest.schema_version,
            },
            authority_level="CANONICAL_PROFILE",
            immutable=True,
        )

        session.add(source)
        session.flush()

        profile_facts: list[ProfileFact] = []

        for fact_seed in seed.facts:
            fact = ProfileFact(
                fact_type=fact_seed.fact_type.value,
                subject=fact_seed.subject,
                value_json=fact_seed.value,
                evidence_state=fact_seed.evidence_state.value,
                source_id=source.source_id,
                valid_from=self._date_to_datetime(
                    fact_seed.valid_from
                ),
                valid_to=self._date_to_datetime(
                    fact_seed.valid_to
                ),
            )

            session.add(fact)
            profile_facts.append(fact)

        session.flush()

        return source, profile_facts

    @staticmethod
    def _date_to_datetime(
        value: date | None,
    ) -> datetime | None:
        if value is None:
            return None

        return datetime.combine(
            value,
            time.min,
            tzinfo=timezone.utc,
        )