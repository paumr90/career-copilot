"""Database tests run in a temporary PostgreSQL schema with synthetic data."""

import os
import re
import uuid
from pathlib import Path

import pytest

_state = {}


def pytest_configure(config):
    # Unit-only runs do not need PostgreSQL.
    if all("tests/unit" in arg.replace("\\", "/") for arg in config.args):
        return
    from sqlalchemy import create_engine, text

    from app.config import settings

    admin = create_engine(os.environ.get("TEST_DATABASE_URL", settings.database_url))
    schema = "copilot_test_" + uuid.uuid4().hex
    assert re.fullmatch(r"copilot_test_[a-f0-9]{32}", schema)
    with admin.begin() as connection:
        connection.execute(text("CREATE SCHEMA " + schema))
    _state.update(admin=admin, schema=schema, pgoptions=os.environ.get("PGOPTIONS"))
    os.environ["PGOPTIONS"] = "-csearch_path=" + schema
    # Settings may already be imported, but no application engine is imported yet.
    if os.environ.get("TEST_DATABASE_URL"):
        settings.database_url = os.environ["TEST_DATABASE_URL"]


@pytest.fixture(scope="session", autouse=True)
def isolated_database():
    if not _state:
        yield
        return
    from alembic import command
    from alembic.config import Config
    from sqlalchemy.orm import Session

    from app.infrastructure.db.session import engine
    from app.modules.profile.importer import CareerProfileImporter
    from app.modules.profile.loader import CareerProfileSeedLoader

    command.upgrade(Config("alembic.ini"), "head")
    seed_dir = Path(__file__).parent / "fixtures"
    seed = CareerProfileSeedLoader().load(seed_dir / "manifest.json", seed_dir / "profile.json")
    with Session(engine) as session:
        CareerProfileImporter().import_seed(session, seed)
        session.commit()
    yield
    engine.dispose()


def pytest_unconfigure(config):
    if not _state:
        return
    from sqlalchemy import text

    admin = _state["admin"]
    with admin.begin() as connection:
        connection.execute(text("DROP SCHEMA " + _state["schema"] + " CASCADE"))
    admin.dispose()
    if _state["pgoptions"] is None:
        os.environ.pop("PGOPTIONS", None)
    else:
        os.environ["PGOPTIONS"] = _state["pgoptions"]
    _state.clear()
