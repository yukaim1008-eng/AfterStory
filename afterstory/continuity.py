import json
from hashlib import sha256

from sqlalchemy import case, func, select

from afterstory.memory_contracts import (
    SUMMARY_BUILDER_VERSION,
    ConservativeTokenCounter,
    SummaryCandidate,
)
from afterstory.models import (
    ContinuityNote,
    Conversation,
    ConversationSegment,
    Message,
    SegmentSummary,
    Turn,
)


class ContinuityService:
    """Creates bounded, replaceable summaries while retaining authoritative messages."""

    def __init__(
        self,
        sessions,
        summary_provider,
        segment_turns=20,
        max_source_tokens=22000,
        token_counter=None,
    ):
        self.sessions = sessions
        self.summary_provider = summary_provider
        self.segment_turns = segment_turns
        self.max_source_tokens = max_source_tokens
        self.token_counter = token_counter or ConservativeTokenCounter()

    def summarize_next(self, instance_id, conversation_id):
        with self.sessions() as session:
            conversation = session.get(Conversation, conversation_id)
            if not conversation or conversation.instance_id != instance_id:
                return None
            covered = (
                session.scalar(
                    select(func.max(ConversationSegment.end_sequence)).where(
                        ConversationSegment.conversation_id == conversation_id,
                        ConversationSegment.status == "published",
                    )
                )
                or 0
            )
            turns = list(
                session.scalars(
                    select(Turn)
                    .where(
                        Turn.conversation_id == conversation_id,
                        Turn.status == "completed",
                        Turn.sequence > covered,
                    )
                    .order_by(Turn.sequence)
                    .limit(self.segment_turns)
                )
            )
            if not turns:
                return None
            messages = list(
                session.scalars(
                    select(Message)
                    .join(Turn)
                    .where(Message.turn_id.in_([turn.id for turn in turns]))
                    .order_by(Turn.sequence, case((Message.role == "user", 0), else_=1))
                )
            )
            by_turn = {
                turn.id: [
                    {
                        "message_id": item.id,
                        "turn_id": item.turn_id,
                        "role": item.role,
                        "text": item.text,
                    }
                    for item in messages
                    if item.turn_id == turn.id
                ]
                for turn in turns
            }
            selected_turns = []
            provider_input = []
            for turn in turns:
                candidate = provider_input + by_turn[turn.id]
                source = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
                if self.token_counter.count(source) > self.max_source_tokens:
                    break
                selected_turns.append(turn)
                provider_input = candidate
            if not selected_turns:
                raise ValueError("summary_source_turn_too_large")
            threshold_reached = len(turns) == self.segment_turns
            budget_reached = len(selected_turns) < len(turns)
            if not threshold_reached and not budget_reached:
                return None
            turns = selected_turns
            digest = sha256(
                json.dumps(provider_input, ensure_ascii=False, sort_keys=True).encode()
            ).hexdigest()

        candidate = SummaryCandidate.model_validate(self.summary_provider.summarize(provider_input))
        expected_turn_ids = [turn.id for turn in turns]
        if candidate.covered_turn_ids != expected_turn_ids:
            raise ValueError("summary_coverage_mismatch")

        payload = candidate.model_dump()
        text = "\n".join(
            f"{topic.topic}：{topic.development}"
            + (f"；结论：{topic.conclusion}" if topic.conclusion else "")
            + (f"；未完：{topic.unresolved}" if topic.unresolved else "")
            for topic in candidate.topics
        )
        with self.sessions.begin() as session:
            existing = session.scalar(
                select(ConversationSegment).where(
                    ConversationSegment.conversation_id == conversation_id,
                    ConversationSegment.start_sequence == turns[0].sequence,
                    ConversationSegment.end_sequence == turns[-1].sequence,
                )
            )
            if existing:
                return existing.id
            segment = ConversationSegment(
                instance_id=instance_id,
                conversation_id=conversation_id,
                start_sequence=turns[0].sequence,
                end_sequence=turns[-1].sequence,
                turn_ids=expected_turn_ids,
                source_hash=digest,
                status="published",
            )
            session.add(segment)
            session.flush()
            session.add(
                SegmentSummary(
                    segment_id=segment.id,
                    revision=1,
                    schema_version="1.0",
                    generator_version=SUMMARY_BUILDER_VERSION,
                    payload=payload,
                    text=text,
                    source_hash=digest,
                    status="active",
                )
            )
            for topic in candidate.topics:
                topic_key = sha256(topic.topic.casefold().encode()).hexdigest()[:40]
                note = session.scalar(
                    select(ContinuityNote).where(
                        ContinuityNote.instance_id == instance_id,
                        ContinuityNote.topic_key == topic_key,
                    )
                )
                if note:
                    note.current_progress = topic.development
                    note.open_question = topic.unresolved or None
                    note.last_turn_id = turns[-1].id
                    note.revision += 1
                elif topic.unresolved:
                    session.add(
                        ContinuityNote(
                            instance_id=instance_id,
                            topic_key=topic_key,
                            status="open",
                            current_progress=topic.development,
                            open_question=topic.unresolved,
                            mention_policy="when_relevant",
                            last_turn_id=turns[-1].id,
                            revision=1,
                        )
                    )
            return segment.id

    def search_raw(self, instance_id, query, limit=20):
        limit = max(1, min(limit, 50))
        with self.sessions() as session:
            rows = session.execute(
                select(Message, Turn, Conversation)
                .join(Turn, Turn.id == Message.turn_id)
                .join(Conversation, Conversation.id == Turn.conversation_id)
                .where(
                    Conversation.instance_id == instance_id,
                    Turn.status == "completed",
                    Message.text.ilike(f"%{query}%"),
                )
                .order_by(Turn.created_at.desc(), Message.id)
                .limit(limit)
            )
            return [
                {
                    "message_id": message.id,
                    "turn_id": turn.id,
                    "conversation_id": conversation.id,
                    "role": message.role,
                    "text": message.text,
                    "recorded_at": message.recorded_at,
                }
                for message, turn, conversation in rows
            ]
