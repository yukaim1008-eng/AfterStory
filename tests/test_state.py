from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from afterstory.api import create_app
from afterstory.conversation import ConversationService
from afterstory.domain import DomainError
from afterstory.memory import MemoryService
from afterstory.models import CharacterState, Relationship, StateEvent
from afterstory.repository import Repository
from afterstory.state import StateService


class RecordingProvider:
    def __init__(self):
        self.calls = []

    def generate(self, messages):
        self.calls.append(messages)
        return "回复"


def setup(database):
    _, sessions = database
    repository = Repository(sessions)
    provider = RecordingProvider()
    conversation = ConversationService(repository, provider)
    state = StateService(sessions)
    instance_id = repository.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repository.create_conversation("alice", instance_id)[
        "conversation_id"
    ]
    return sessions, repository, provider, conversation, state, instance_id, conversation_id


def test_internal_state_commit_is_evidenced_idempotent_and_not_public(database):
    sessions, repository, _, conversation, state, instance_id, conversation_id = setup(database)
    source = conversation.send("alice", conversation_id, "source", "今天发生了一件好事")
    values = dict(
        short_term_state="为用户的好消息感到开心",
        familiarity="知道用户愿意分享日常",
        trust="保持已有信任",
        closeness="交流自然",
        reason="用户在本轮主动分享了好消息",
    )
    committed = state.commit(
        "alice", instance_id, "state-1", source.turn_id, 0, **values
    )
    assert committed["revision"] == 1
    assert committed["relationship"]["trust"] == "保持已有信任"
    assert state.commit(
        "alice", instance_id, "state-1", source.turn_id, 0, **values
    ) == committed
    with pytest.raises(DomainError) as changed_request:
        state.commit(
            "alice",
            instance_id,
            "state-1",
            source.turn_id,
            0,
            **{**values, "trust": "不同内容"},
        )
    assert changed_request.value.code == "state_request_conflict"
    with pytest.raises(DomainError) as reused_source:
        state.commit(
            "alice", instance_id, "state-2", source.turn_id, 1, **values
        )
    assert reused_source.value.code == "state_source_already_used"

    other_instance = repository.create_instance("alice", "test-xiao-v1")["instance_id"]
    with pytest.raises(DomainError) as wrong_instance:
        state.commit(
            "alice", other_instance, "wrong", source.turn_id, 0, **values
        )
    assert wrong_instance.value.code == "state_source_not_found"
    with sessions() as session:
        assert session.get(CharacterState, instance_id).description == values[
            "short_term_state"
        ]
        assert session.get(Relationship, instance_id).closeness == values["closeness"]
        assert len(list(session.scalars(select(StateEvent)))) == 1

    # State is an internal service boundary and has no user-facing score or state route.
    cfg, _ = database
    with TestClient(create_app(cfg)) as client:
        paths = client.get("/openapi.json").json()["paths"]
        assert not any("state" in path or "relationship" in path for path in paths)


def test_committed_state_enters_context_but_chat_does_not_invent_updates(database):
    sessions, _, provider, conversation, state, instance_id, conversation_id = setup(database)
    source = conversation.send("alice", conversation_id, "one", "第一轮")
    with sessions() as session:
        assert session.get(CharacterState, instance_id) is None
        assert session.get(Relationship, instance_id) is None

    state.commit(
        "alice",
        instance_id,
        "state",
        source.turn_id,
        0,
        short_term_state="有些高兴，但保持平静",
        familiarity="认识了用户的日常习惯",
        trust="没有新的变化",
        closeness="相处自然",
        reason="测试中的明确内部策略提交",
    )
    conversation.send("alice", conversation_id, "two", "继续聊")
    context = "\n".join(message.content for message in provider.calls[-1])
    assert "内部连续性数据" in context
    assert "有些高兴，但保持平静" in context
    assert "用户可见评分" in context
    with sessions() as session:
        assert len(list(session.scalars(select(StateEvent)))) == 1


def test_memory_correction_clears_state_and_blocks_stale_evidence(database):
    sessions, _, provider, conversation, state, instance_id, conversation_id = setup(database)
    memory_service = MemoryService(sessions)
    memory = memory_service.create("alice", instance_id, "memory", "用户住在旧地址")
    source = conversation.send("alice", conversation_id, "source", "旧地址附近很安静")
    state.commit(
        "alice",
        instance_id,
        "state",
        source.turn_id,
        0,
        short_term_state="正在讨论旧地址",
        familiarity="了解旧地址周边",
        trust=None,
        closeness=None,
        reason="来源轮次提到了旧地址",
    )
    memory_service.update(
        "alice", memory["memory_id"], memory["revision"], "用户已经搬到新地址"
    )
    with sessions() as session:
        assert session.get(CharacterState, instance_id).description is None
        assert session.get(Relationship, instance_id).familiarity is None
        assert session.scalar(select(StateEvent)).status == "excluded"
    with pytest.raises(DomainError) as stale:
        state.commit(
            "alice",
            instance_id,
            "stale-state",
            source.turn_id,
            2,
            short_term_state="重新引入旧地址",
            reason="不应采用",
        )
    assert stale.value.code == "state_source_stale"

    conversation.send("alice", conversation_id, "after", "谈谈别的")
    context = "\n".join(message.content for message in provider.calls[-1])
    assert "正在讨论旧地址" not in context
    assert "了解旧地址周边" not in context


def test_concurrent_state_commits_have_one_winner(database):
    _, _, _, conversation, state, instance_id, conversation_id = setup(database)
    first = conversation.send("alice", conversation_id, "one", "第一条依据")
    second = conversation.send("alice", conversation_id, "two", "第二条依据")

    def commit(source, label):
        try:
            return state.commit(
                "alice",
                instance_id,
                label,
                source.turn_id,
                0,
                short_term_state=label,
                reason=label,
            )
        except DomainError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args: commit(*args), [(first, "a"), (second, "b")]))
    assert sum(isinstance(result, dict) for result in results) == 1
    assert results.count("state_revision_conflict") == 1
