from alembic import command
from alembic.config import Config
from sqlalchemy import select, text

from afterstory.conversation import ConversationService
from afterstory.memory import MemoryService
from afterstory.models import CharacterInstance, CharacterVersion, Message, PersonalMemory
from afterstory.repository import Repository


def test_memory_migrations_round_trip_preserve_legacy_authoritative_data(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]
    response = ConversationService(
        repo, type("Provider", (), {"generate": lambda _, __: "旧回复"})()
    ).send("alice", conversation_id, "legacy-turn", "旧消息")
    memory = MemoryService(sessions).create("alice", instance_id, "legacy-memory", "旧记忆")
    with sessions() as session:
        prompt = session.get(CharacterVersion, "test-lan-v1").system_prompt

    migrations = Config("alembic.ini")
    command.downgrade(migrations, "f3a_character_definition")
    with sessions() as session:
        assert (
            session.execute(
                text("SELECT content FROM personal_memories WHERE id=:id"),
                {"id": memory["memory_id"]},
            ).scalar_one()
            == "旧记忆"
        )
        assert (
            session.execute(
                text("SELECT version_id FROM character_instances WHERE id=:id"),
                {"id": instance_id},
            ).scalar_one()
            == "test-lan-v1"
        )
        assert (
            session.execute(
                text("SELECT text FROM messages WHERE id=:id"),
                {"id": response.message_id},
            ).scalar_one()
            == "旧回复"
        )

    command.upgrade(migrations, "head")
    with sessions() as session:
        assert session.get(CharacterVersion, "test-lan-v1").system_prompt == prompt
        assert session.get(CharacterInstance, instance_id).version_id == "test-lan-v1"
        restored = session.get(PersonalMemory, memory["memory_id"])
        assert restored.content == "旧记忆" and restored.memory_type == "fact"
        assert session.get(Message, response.message_id).text == "旧回复"
        assert session.scalar(
            select(PersonalMemory).where(PersonalMemory.id == memory["memory_id"])
        )
