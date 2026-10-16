import os
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from afterstory.config import Settings


def test_auth_upgrade_downgrade_preserves_legacy_rows(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL", Settings().database_url.get_secret_value())
    schema = "test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    test_url = url + ("&" if "?" in url else "?") + "options=-csearch_path%3D" + schema
    monkeypatch.setenv("DATABASE_URL", test_url)
    engine = create_engine(test_url)
    try:
        command.upgrade(Config("alembic.ini"), "m7_state_relationship")
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO users (id) VALUES ('legacy-user')"))
            connection.execute(
                text("INSERT INTO characters (id, name) VALUES ('legacy-character', '角色')")
            )
            connection.execute(
                text(
                    "INSERT INTO character_versions (id, character_id, checkpoint, system_prompt) "
                    "VALUES ('legacy-version', 'legacy-character', 'start', 'legacy prompt')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO character_instances (id, user_id, version_id) "
                    "VALUES ('legacy-instance', 'legacy-user', 'legacy-version')"
                )
            )

        def snapshot():
            with engine.connect() as connection:
                return (
                    connection.execute(
                        text("SELECT id FROM users WHERE id='legacy-user'")
                    ).scalar(),
                    connection.execute(
                        text(
                            "SELECT system_prompt FROM character_versions WHERE id='legacy-version'"
                        )
                    ).scalar(),
                    connection.execute(
                        text(
                            "SELECT user_id, version_id FROM character_instances "
                            "WHERE id='legacy-instance'"
                        )
                    ).one(),
                )

        before = snapshot()
        command.upgrade(Config("alembic.ini"), "head")
        assert snapshot() == before
        assert {"username", "password_hash", "is_active"}.issubset(
            {column["name"] for column in inspect(engine).get_columns("users")}
        )
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT username, password_hash, is_active FROM users WHERE id='legacy-user'")
            ).one() == (None, None, True)
        command.downgrade(Config("alembic.ini"), "m7_state_relationship")
        assert snapshot() == before
        assert "username" not in {column["name"] for column in inspect(engine).get_columns("users")}
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
