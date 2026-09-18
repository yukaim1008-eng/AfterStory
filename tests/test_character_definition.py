import json

import pytest
from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import select

from afterstory.character_definition import (
    SUPPORTED_CHARACTER_DEFINITION_SCHEMA_VERSION,
    CharacterDefinition,
)
from afterstory.character_prompt import PROMPT_BUILDER_VERSION, build_character_system_prompt
from afterstory.conversation import ConversationService
from afterstory.memory import MemoryService
from afterstory.models import CharacterInstance, CharacterVersion, Conversation, Message
from afterstory.repository import Repository
from afterstory.seed import seed
from afterstory.state import StateService


def definition(**changes):
    value = {
        "schema_version": SUPPORTED_CHARACTER_DEFINITION_SCHEMA_VERSION,
        "identity": "  观星员\n澄  ",
        "personality": "冷静",
        "speaking_style": "简洁",
        "behavior": "保留立场",
        "worldview": "来自异世界",
        "relationship_premise": "初次通信",
    }
    value.update(changes)
    return value


def test_definition_validation_requires_exact_normalized_six_field_schema():
    parsed = CharacterDefinition.model_validate(definition())
    assert parsed.identity == "观星员 澄"
    assert parsed.schema_version == "1.0"
    assert CharacterDefinition.model_validate(
        definition(
            personality="",
            speaking_style="  ",
            behavior="",
            worldview="",
            relationship_premise="",
        )
    ).personality == ""

    invalid = [
        definition(identity="  \t"),
        {key: value for key, value in definition().items() if key != "behavior"},
        definition(unexpected="value"),
        definition(personality=["not", "a", "string"]),
        definition(schema_version="2.0"),
    ]
    for value in invalid:
        with pytest.raises(ValidationError):
            CharacterDefinition.model_validate(value)


def test_prompt_builder_is_stable_ordered_and_only_uses_definition():
    parsed = CharacterDefinition.model_validate(
        definition(personality="", behavior="", relationship_premise="")
    )
    first = build_character_system_prompt(parsed)
    assert first == build_character_system_prompt(parsed)
    assert PROMPT_BUILDER_VERSION == "1.0"
    assert first.index("通用 Character Runtime Rules") < first.index("身份")
    assert first.index("身份") < first.index("说话方式") < first.index("世界观")
    assert "性格：" not in first
    assert "行为：" not in first
    assert "初始关系前提：" not in first
    assert "Memory" not in first and "State" not in first and "Relationship" not in first


def package(version_id, *, structured=True, identity="观星员澄"):
    item = {
        "character_id": "schema-package",
        "name": "结构化包测试角色",
        "version_id": version_id,
        "checkpoint": "baseline",
    }
    if structured:
        item["definition"] = definition(identity=identity)
    else:
        item["system_prompt"] = "legacy prompt"
    return [item]


def write_package(tmp_path, name, contents):
    path = tmp_path / name
    path.write_text(json.dumps(contents, ensure_ascii=False), encoding="utf-8")
    return path


def test_seed_imports_structured_and_legacy_packages_and_preserves_versions(database, tmp_path):
    _, sessions = database
    structured = write_package(tmp_path, "structured.json", package("schema-v1"))
    legacy = write_package(tmp_path, "legacy.json", package("legacy-v1", structured=False))
    seed(sessions, "alice", structured)
    seed(sessions, "alice", legacy)
    seed(sessions, "alice", structured)  # Same frozen version is idempotent.

    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "schema-v1")["instance_id"]
    with sessions() as session:
        imported = session.get(CharacterVersion, "schema-v1")
        assert imported.definition == CharacterDefinition.model_validate(
            definition(identity="观星员澄")
        ).model_dump()
        assert imported.system_prompt == build_character_system_prompt(
            CharacterDefinition.model_validate(definition(identity="观星员澄"))
        )
        assert session.get(CharacterVersion, "legacy-v1").definition is None
        assert session.get(CharacterVersion, "legacy-v1").system_prompt == "legacy prompt"

    changed = write_package(tmp_path, "changed.json", package("schema-v1", identity="不同身份"))
    with pytest.raises(ValueError, match="Character version changed"):
        seed(sessions, "alice", changed)
    new_version = write_package(tmp_path, "new.json", package("schema-v2", identity="不同身份"))
    seed(sessions, "alice", new_version)
    with sessions() as session:
        assert session.get(CharacterInstance, instance_id).version_id == "schema-v1"
        assert session.get(CharacterVersion, "schema-v2")


def test_seed_rejects_two_sources_of_system_prompt(database, tmp_path):
    _, sessions = database
    invalid = package("invalid-v1")[0]
    invalid["system_prompt"] = "manually supplied"
    with pytest.raises(ValueError, match="cannot provide system_prompt"):
        seed(sessions, "alice", write_package(tmp_path, "invalid.json", [invalid]))


def test_structured_definition_reaches_provider_before_runtime_context(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-schema-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]

    class RecordingProvider:
        calls = []

        def generate(self, messages):
            self.calls.append(messages)
            return "回复"

    provider = RecordingProvider()
    ConversationService(repo, provider).send("alice", conversation_id, "schema", "你好")
    assert provider.calls[0][0].content == build_character_system_prompt(
        CharacterDefinition.model_validate(
            {
                "schema_version": "1.0",
                "identity": "原创测试角色澄，是异世界的观星员。",
                "personality": "冷静、好奇，重视准确。",
                "speaking_style": "表达简洁，默认称呼用户为旅人。",
                "behavior": "保留自主立场，不能确定时会说明。",
                "worldview": "知道自己身处异世界，并理解 AfterStory 是与现实世界用户的通信。",
                "relationship_premise": "用户是刚开始通信的异世界朋友。",
            }
        )
    )
    assert provider.calls[0][-1].content == "你好"


def test_structured_prompt_coexists_with_instance_runtime_context(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-schema-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]

    class RecordingProvider:
        def __init__(self):
            self.calls = []

        def generate(self, messages):
            self.calls.append(messages)
            return "回复"

    provider = RecordingProvider()
    conversation = ConversationService(repo, provider)
    MemoryService(sessions).create("alice", instance_id, "memory", "用户喜欢夜空")
    source = conversation.send("alice", conversation_id, "source", "我今天看见了星星")
    StateService(sessions).commit(
        "alice",
        instance_id,
        "state",
        source.turn_id,
        0,
        short_term_state="因分享星空而欣喜",
        familiarity="知道用户喜欢夜空",
        trust="愿意继续倾听",
        closeness="交流自然",
        reason="用户分享了看星星的经历",
    )
    conversation.send("alice", conversation_id, "next", "你还记得吗")

    messages = provider.calls[-1]
    assert "原创测试角色澄" in messages[0].content
    assert "用户喜欢夜空" in messages[1].content
    assert "因分享星空而欣喜" in messages[2].content
    assert "愿意继续倾听" in messages[2].content
    assert [message.content for message in messages[-3:]] == [
        "我今天看见了星星",
        "回复",
        "你还记得吗",
    ]


def test_definition_migration_round_trip_preserves_legacy_version_and_instance(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]
    ConversationService(repo, type("Provider", (), {"generate": lambda _, __: "旧回复"})()).send(
        "alice", conversation_id, "legacy", "保留旧聊天"
    )
    original_prompt = None
    with sessions() as session:
        original_prompt = session.get(CharacterVersion, "test-lan-v1").system_prompt

    migrations = Config("alembic.ini")
    command.downgrade(migrations, "f2d_state_boundary")
    command.upgrade(migrations, "head")
    with sessions() as session:
        version = session.get(CharacterVersion, "test-lan-v1")
        assert version.definition is None
        assert version.system_prompt == original_prompt
        assert session.get(CharacterInstance, instance_id).version_id == "test-lan-v1"
        assert session.get(Conversation, conversation_id)
        assert {message.text for message in session.scalars(select(Message))} == {
            "保留旧聊天",
            "旧回复",
        }
