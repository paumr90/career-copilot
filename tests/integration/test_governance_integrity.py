import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.enums import EvidenceState, SourceType
from app.infrastructure.db.session import engine
from app.modules.governance.models import ProfileFact, Source


def test_profile_fact_requires_existing_source() -> None:
    nonexistent_source_id = uuid.uuid4()

    invalid_fact = ProfileFact(
        fact_type="test_fact",
        subject="governance_test",
        value_json={"value": "test"},
        evidence_state=EvidenceState.CONFIRMED.value,
        source_id=nonexistent_source_id,
    )

    with Session(engine) as session:
        session.add(invalid_fact)

        with pytest.raises(IntegrityError):
            session.flush()

        session.rollback()


def test_profile_fact_with_existing_source_is_valid() -> None:
    source = Source(
        source_type=SourceType.USER.value,
        captured_at=datetime.now(timezone.utc),
        authority_level="CONFIRMED_USER_INPUT",
        metadata_json={},
        immutable=True,
    )

    with Session(engine) as session:
        session.add(source)
        session.flush()

        valid_fact = ProfileFact(
            fact_type="test_fact",
            subject="governance_test",
            value_json={"value": "test"},
            evidence_state=EvidenceState.CONFIRMED.value,
            source_id=source.source_id,
        )

        session.add(valid_fact)
        session.flush()

        assert valid_fact.fact_id is not None
        assert valid_fact.source_id == source.source_id

        session.rollback()