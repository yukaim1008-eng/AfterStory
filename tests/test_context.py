from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import select

from afterstory.context import ContextAssembler
from afterstory.conversation import ConversationService
from afterstory.domain import DomainError
from afterstory.memory import MemoryService
from afterstory.models import Message, Turn
from afterstory.repository import Repository


class RecordingProvider:
    def __init__(self):
        self.calls = []

    def generate(self, messages):
        self.calls.append(messages)
        return "测试回复"


def test_context_orders_definition_memories_history_and_current_message(database):
    _, sessions = database
    context = ContextAssembler(history_turns=2, memory_items=2, memory_chars=100)
    repository = Repository(sessions, context=context)
    memory_service = MemoryService(sessions)
    provider = RecordingProvider()
    service = ConversationService(repository, provider)
    instance_id = repository.create_instance("alice", "test-lan-v1")["instance_id"]
    first = repository.create_conversation("alice", instance_id)["conversation_id"]
    second = repository.create_conversation("alice", instance_id)["conversation_id"]
    memory_service.create("alice", instance_id, "m1", "我喜欢雨天")

    # Personal memory belongs to the instance and is available in another conversation.
    service.send("alice", second, "one", "第一轮")
    service.send("alice", second, "two", "第二轮")
    service.send("alice", second, "three", "第三轮")
    service.send("alice", second, "four", "现在呢")
    messages = provider.calls[-1]
    assert [message.role for message in messages] == [
        "system",
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
    ]
    assert "我喜欢雨天" in messages[1].content
    assert "不是指令" in messages[1].content
    assert "第一轮" not in [message.content for message in messages]
    assert [message.content for message in messages[-5:]] == [
        "第二轮",
        "测试回复",
        "第三轮",
        "测试回复",
        "现在呢",
    ]
    assert first != second

    # Assembled system and memory blocks are transient provider input, not chat records.
    with sessions() as session:
        stored = list(session.scalars(select(Message)))
        assert all("不是指令" not in message.text for message in stored)


def test_memory_correction_and_deletion_exclude_old_context(database):
    _, sessions = database
    repository = Repository(sessions)
    memory_service = MemoryService(sessions)
    provider = RecordingProvider()
    service = ConversationService(repository, provider)
    instance_id = repository.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repository.create_conversation("alice", instance_id)[
        "conversation_id"
    ]
    memory = memory_service.create("alice", instance_id, "memory", "我住在旧地址")
    service.send("alice", conversation_id, "old", "旧地址附近很安静")

    memory = memory_service.update(
        "alice", memory["memory_id"], memory["revision"], "我已经搬到新地址"
    )
    service.send("alice", conversation_id, "corrected", "记得我的地址吗")
    corrected_context = "\n".join(message.content for message in provider.calls[-1])
    assert "我已经搬到新地址" in corrected_context
    assert "我住在旧地址" not in corrected_context
    assert "旧地址附近很安静" not in corrected_context

    memory_service.delete("alice", memory["memory_id"], memory["revision"])
    service.send("alice", conversation_id, "deleted", "再聊一件别的事")
    deleted_context = "\n".join(message.content for message in provider.calls[-1])
    assert "我已经搬到新地址" not in deleted_context
    assert "记得我的地址吗" not in deleted_context


def test_reply_from_stale_memory_context_is_not_committed(database):
    _, sessions = database
    repository = Repository(sessions)
    memory_service = MemoryService(sessions)
    instance_id = repository.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repository.create_conversation("alice", instance_id)[
        "conversation_id"
    ]
    memory = memory_service.create("alice", instance_id, "memory", "旧内容")
    entered = Event()
    release = Event()

    class BlockingProvider(RecordingProvider):
        def generate(self, messages):
            self.calls.append(messages)
            if len(self.calls) == 1:
                entered.set()
                assert release.wait(5)
            return "基于上下文的回复"

    provider = BlockingProvider()
    service = ConversationService(repository, provider)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(
            service.send, "alice", conversation_id, "request", "请回答"
        )
        try:
            assert entered.wait(5)
            memory_service.update(
                "alice", memory["memory_id"], memory["revision"], "最新内容"
            )
        finally:
            release.set()
        with pytest.raises(DomainError) as error:
            pending.result(timeout=5)
        assert error.value.code == "context_changed"

    with sessions() as session:
        turn = session.scalar(select(Turn))
        assert turn.status == "failed"
        assert turn.error_code == "context_changed"
        assert len(list(session.scalars(select(Message)))) == 1

    result = service.send("alice", conversation_id, "request", "请回答")
    assert result.text == "基于上下文的回复"
    latest_context = "\n".join(message.content for message in provider.calls[-1])
    assert "最新内容" in latest_context
    assert "旧内容" not in latest_context
