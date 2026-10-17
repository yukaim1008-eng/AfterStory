import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from afterstory.auth import PASSWORDS
from afterstory.character.importer import seed
from afterstory.config import Settings
from afterstory.database import make_sessions
from afterstory.models import User


@pytest.fixture
def database(monkeypatch):
    # Isolate each test in a new schema; never truncate the user's tables.
    url = os.getenv("TEST_DATABASE_URL", Settings().database_url.get_secret_value())
    schema = "test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    separator = "&" if "?" in url else "?"
    test_url = url + separator + "options=-csearch_path%3D" + schema
    monkeypatch.setenv("DATABASE_URL", test_url)
    monkeypatch.setenv("LLM_ACTIVE_MODEL", "fake")
    try:
        command.upgrade(Config("alembic.ini"), "head")
        cfg = Settings(_env_file=None, dev_user_id="alice")
        engine, sessions = make_sessions(cfg)
        seed(sessions, "alice")
        seed(sessions, "bob")
        with sessions.begin() as session:
            alice = session.get(User, "alice")
            alice.username = "alice"
            alice.password_hash = PASSWORDS.hash("alice-test-password-123")
        yield cfg, sessions
        engine.dispose()
    finally:
        # schema is generated here, not accepted from user input.
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
