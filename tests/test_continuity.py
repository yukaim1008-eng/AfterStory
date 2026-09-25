from sqlalchemy import select

from afterstory.continuity import ContinuityService
from afterstory.conversation import ConversationService
from afterstory.models import ContinuityNote, Message, SegmentSummary, Turn
from afterstory.repository import Repository


class SummaryProvider:
    def summarize(self, messages):
        turn_ids = list(dict.fromkeys(item["turn_id"] for item in messages))
        return {
            "schema_version": "1.0",
            "topics": [
                {
                    "topic": "旅行计划",
                    "development": "用户准备去看海",
                    "conclusion": "",
                    "unresolved": "下周确认日期",
                    "source_message_ids": [item["message_id"] for item in messages],
                }
            ],
            "covered_turn_ids": turn_ids,
        }


def test_summary_continuity_and_cross_conversation_raw_lookup(database):
    _, sessions = database
    repo = Repository(sessions, history_turns=1)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    first = repo.create_conversation("alice", instance_id)["conversation_id"]
    provider = type("Provider", (), {"generate": lambda _, __: "记得"})()
    chat = ConversationService(repo, provider)
    chat.send("alice", first, "one", "我准备去看海")
    chat.send("alice", first, "two", "下周再确认日期")

    continuity = ContinuityService(sessions, SummaryProvider(), segment_turns=2)
    segment_id = continuity.summarize_next(instance_id, first)
    assert segment_id
    assert continuity.summarize_next(instance_id, first) is None
    assert continuity.search_raw(instance_id, "看海", limit=5)[0]["conversation_id"] == first

    second = repo.create_conversation("alice", instance_id)["conversation_id"]
    prepared = repo.prepare_context("alice", second, "我们上次聊到哪里")
    contents = [message.content for message in prepared.messages]
    assert any("用户准备去看海" in content for content in contents)
    assert any("下周确认日期" in content for content in contents)
    with sessions() as session:
        assert session.scalar(select(SegmentSummary))
        assert session.scalar(select(ContinuityNote))


def test_context_preparation_happens_before_turn_reservation(database):
    _, sessions = database
    repo = Repository(sessions)
    instance_id = repo.create_instance("alice", "test-lan-v1")["instance_id"]
    conversation_id = repo.create_conversation("alice", instance_id)["conversation_id"]
    prepared = repo.prepare_context("alice", conversation_id, "先准备")
    turn_id, _, _ = repo.reserve_turn("alice", conversation_id, "prepared", "先准备", prepared)
    with sessions() as session:
        turn = session.get(Turn, turn_id)
        user_message = session.scalar(
            select(Message).where(Message.turn_id == turn_id, Message.role == "user")
        )
        assert turn.status == "processing"
        assert user_message.text == "先准备"
