import os
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from afterstory.config import Settings


def test_invite_upgrade_downgrade_preserves_existing_accounts_and_characters(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL", Settings().database_url.get_secret_value())
    schema = "test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    test_url = url + ("&" if "?" in url else "?") + "options=-csearch_path%3D" + schema
    monkeypatch.setenv("DATABASE_URL", test_url)
    engine = create_engine(test_url)
    try:
        command.upgrade(Config("alembic.ini"), "a1_authentication")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, username, password_hash) "
                    "VALUES ('existing', 'owner', 'hash')"
                )
            )
            connection.execute(
                text("INSERT INTO characters (id, name) VALUES ('existing-character', '角色')")
            )
            connection.execute(
                text(
                    "INSERT INTO character_versions (id, character_id, checkpoint, system_prompt) "
                    "VALUES ('existing-version', 'existing-character', 'start', 'original prompt')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO character_instances (id, user_id, version_id) "
                    "VALUES ('existing-instance', 'existing', 'existing-version')"
                )
            )

        def snapshot():
            with engine.connect() as connection:
                return (
                    connection.execute(
                        text("SELECT id, username, password_hash FROM users WHERE id='existing'")
                    ).one(),
                    connection.execute(
                        text(
                            "SELECT system_prompt FROM character_versions "
                            "WHERE id='existing-version'"
                        )
                    ).scalar(),
                    connection.execute(
                        text(
                            "SELECT user_id, version_id FROM character_instances "
                            "WHERE id='existing-instance'"
                        )
                    ).one(),
                )

        before = snapshot()
        command.upgrade(Config("alembic.ini"), "head")
        assert "registration_invites" in inspect(engine).get_table_names()
        assert snapshot() == before
        command.downgrade(Config("alembic.ini"), "a1_authentication")
        assert "registration_invites" not in inspect(engine).get_table_names()
        assert snapshot() == before
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
