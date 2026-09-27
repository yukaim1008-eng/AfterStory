from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from afterstory.conversation import ConversationService
from afterstory.evolution import RelationshipEvolutionService, StateEvolutionService
from afterstory.models import CharacterState, Relationship, RelationshipRevision
from afterstory.repository import Repository


def setup(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]
    chat = ConversationService(repo, type("Provider", (), {"generate": lambda _, __: "好"})())
    return sessions, repo, chat, instance_id, conversation_id


def test_state_proposal_has_duration_and_expired_state_leaves_context(database):
    sessions, repo, chat, instance_id, conversation_id = setup(database)
    source = chat.send("alice", conversation_id, "source", "今天很开心")
    event_id = StateEvolutionService(sessions).apply(
        "alice",
        instance_id,
        "proposal",
        {
            "description": "因用户的分享感到轻松",
            "persistence": "transient",
            "expression_effect": "语气轻快一些",
            "source_turn_ids": [source.turn_id],
        },
    )
    assert event_id
    assert any(
        "因用户的分享感到轻松" in message.content
        for message in repo.prepare_context("alice", conversation_id, "继续").messages
    )
    with sessions.begin() as session:
        state = session.get(CharacterState, instance_id)
        state.valid_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert all(
        "因用户的分享感到轻松" not in message.content
        for message in repo.prepare_context("alice", conversation_id, "继续").messages
    )


def test_relationship_requires_multiple_evidence_and_writes_revision(database):
    sessions, _, chat, instance_id, conversation_id = setup(database)
    first = chat.send("alice", conversation_id, "one", "我愿意认真听你说")
    second = chat.send("alice", conversation_id, "two", "你的想法对我很重要")
    evolution = RelationshipEvolutionService(sessions, minimum_evidence=2)
    evolution.record(
        "alice",
        instance_id,
        first.turn_id,
        "trust",
        "strengthen",
        "持续尊重角色立场",
        "observed_interaction",
    )
    assert (
        evolution.evaluate(
            "alice",
            instance_id,
            0,
            trust="开始形成稳定的相互尊重",
            reason="目前只有单条证据",
        )
        is None
    )
    evolution.record(
        "alice",
        instance_id,
        second.turn_id,
        "trust",
        "strengthen",
        "再次尊重角色意见",
        "observed_interaction",
    )
    revision_id = evolution.evaluate(
        "alice",
        instance_id,
        0,
        familiarity="熟悉彼此的表达方式",
        trust="形成稳定的相互尊重",
        closeness="交流自然但保留边界",
        reason="两个独立成功轮次提供一致证据",
    )
    assert revision_id
    with sessions() as session:
        relationship = session.get(Relationship, instance_id)
        revision = session.scalar(select(RelationshipRevision))
        assert relationship.trust == "形成稳定的相互尊重"
        assert len(revision.evidence_ids) == 2


def test_relationship_requires_evidence_from_distinct_turns(database):
    sessions, _, chat, instance_id, conversation_id = setup(database)
    source = chat.send("alice", conversation_id, "one-source", "我尊重你的想法和边界")
    evolution = RelationshipEvolutionService(sessions, minimum_evidence=2)
    evolution.record(
        "alice",
        instance_id,
        source.turn_id,
        "trust",
        "strengthen",
        "尊重角色想法",
        "observed_interaction",
    )
    evolution.record(
        "alice",
        instance_id,
        source.turn_id,
        "closeness",
        "strengthen",
        "尊重角色边界",
        "observed_interaction",
    )
    assert (
        evolution.evaluate(
            "alice",
            instance_id,
            0,
            trust="开始建立信任",
            closeness="交流更自然",
            reason="仍然只有一个来源轮次",
        )
        is None
    )
