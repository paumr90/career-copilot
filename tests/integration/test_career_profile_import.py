import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.db.session import engine
from app.modules.governance.models import Source
from app.modules.profile.importer import CareerProfileImporter
from app.modules.profile.loader import CareerProfileSeedLoader


SEED_DIR = Path("seeds/career_master")


def test_example_seed_loads_successfully() -> None:
    loader = CareerProfileSeedLoader()

    seed = loader.load(
        SEED_DIR / "manifest.example.json",
        SEED_DIR / "profile.example.json",
    )

    assert seed.manifest.seed_version == "test-0.1"
    assert seed.manifest.source_type.value == "PROFILE"
    assert seed.manifest.content_hash is not None
    assert len(seed.manifest.content_hash) == 64

    assert len(seed.facts) == 2
    assert seed.facts[0].subject == "Example Company"


def test_example_seed_can_be_imported_with_rollback() -> None:
    loader = CareerProfileSeedLoader()
    importer = CareerProfileImporter()

    seed = loader.load(
        SEED_DIR / "manifest.example.json",
        SEED_DIR / "profile.example.json",
    )

    with Session(engine) as session:
        source, facts = importer.import_seed(
            session=session,
            seed=seed,
        )

        assert source.source_id is not None
        assert source.source_type == "PROFILE"
        assert source.authority_level == "CANONICAL_PROFILE"

        assert source.snapshot_hash == seed.manifest.content_hash
        assert source.snapshot_hash is not None
        assert len(source.snapshot_hash) == 64

        assert len(facts) == 2
        assert facts[0].fact_id is not None
        assert facts[0].subject == "Example Company"
        assert facts[0].source_id == source.source_id

        session.rollback()


def test_seed_with_modified_content_is_rejected(
    tmp_path: Path,
) -> None:
    loader = CareerProfileSeedLoader()

    manifest_data = json.loads(
        (SEED_DIR / "manifest.example.json").read_text(
            encoding="utf-8"
        )
    )

    profile_data = json.loads(
        (SEED_DIR / "profile.example.json").read_text(
            encoding="utf-8"
        )
    )

    original_hash = loader.calculate_content_hash(
        manifest_data=manifest_data,
        profile_data=profile_data,
    )

    manifest_data["content_hash"] = original_hash

    manifest_path = tmp_path / "manifest.json"
    profile_path = tmp_path / "profile.json"

    manifest_path.write_text(
        json.dumps(
            manifest_data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    profile_data[0]["value"]["role"] = "Manipulated Role"

    profile_path.write_text(
        json.dumps(
            profile_data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="content hash does not match",
    ):
        loader.load(
            manifest_path,
            profile_path,
        )


def test_duplicate_profile_seed_version_is_rejected() -> None:
    loader = CareerProfileSeedLoader()
    importer = CareerProfileImporter()

    seed = loader.load(
        SEED_DIR / "manifest.example.json",
        SEED_DIR / "profile.example.json",
    )

    with Session(engine) as session:
        importer.import_seed(
            session=session,
            seed=seed,
        )

        with pytest.raises(IntegrityError):
            importer.import_seed(
                session=session,
                seed=seed,
            )

        session.rollback()


def test_non_profile_sources_can_reuse_external_id() -> None:
    shared_external_id = "example-shared-external-id"

    source_a = Source(
        source_type="JD",
        external_id=shared_external_id,
        captured_at=datetime.now(timezone.utc),
        metadata_json={},
        authority_level="TEST",
        immutable=True,
    )

    source_b = Source(
        source_type="JD",
        external_id=shared_external_id,
        captured_at=datetime.now(timezone.utc),
        metadata_json={},
        authority_level="TEST",
        immutable=True,
    )

    with Session(engine) as session:
        session.add_all(
            [
                source_a,
                source_b,
            ]
        )

        session.flush()

        assert source_a.source_id is not None
        assert source_b.source_id is not None
        assert source_a.external_id == source_b.external_id

        session.rollback()