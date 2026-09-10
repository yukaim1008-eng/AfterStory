from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select

from afterstory.domain import CharacterResponse, ChatMessage, DomainError
from afterstory.models import (
    Character,
    CharacterInstance,
    CharacterVersion,
    Conversation,
    Message,
    Turn,
)


class Repository:
    def __init__(self, sessions, lease_seconds=120, history_turns=12):
        self.sessions = sessions
        self.lease_seconds = lease_seconds
        self.history_turns = history_turns

    @staticmethod
    def owned_conversation(session, user, conversation_id, lock=False):
        query = (
            select(Conversation)
            .join(CharacterInstance)
            .where(Conversation.id == conversation_id, CharacterInstance.user_id == user)
        )
        if lock:
            query = query.with_for_update(of=Conversation)
        conversation = session.scalar(query)
        if not conversation:
            raise DomainError(404, "conversation_not_found")
        return conversation

    def characters(self):
        with self.sessions() as session:
            return [
                dict(character_id=c.id, name=c.name, version_id=v.id, checkpoint=v.checkpoint)
                for c, v in session.execute(
                    select(Character, CharacterVersion)
                    .join(CharacterVersion)
                    .order_by(Character.id, CharacterVersion.id)
                )
            ]

    def create_instance(self, user, version_id):
        with self.sessions.begin() as session:
            if not session.get(CharacterVersion, version_id):
                raise DomainError(404, "character_version_not_found")
            instance = CharacterInstance(user_id=user, version_id=version_id)
            session.add(instance)
            session.flush()
            return dict(instance_id=instance.id, version_id=instance.version_id)

    def create_conversation(self, user, instance_id):
        with self.sessions.begin() as session:
            instance = session.get(CharacterInstance, instance_id)
            if not instance or instance.user_id != user:
                raise DomainError(404, "instance_not_found")
            conversation = Conversation(instance_id=instance.id)
            session.add(conversation)
            session.flush()
            return dict(conversation_id=conversation.id, instance_id=instance.id)

    @staticmethod
    def response(session, turn):
        message = session.scalar(
            select(Message).where(Message.turn_id == turn.id, Message.role == "assistant")
        )
        return CharacterResponse(message.id, turn.id, message.text)

    def begin_turn(self, user, conversation_id, request_id, text):
        now = datetime.now(timezone.utc)
        with self.sessions.begin() as session:
            conversation = self.owned_conversation(session, user, conversation_id, lock=True)
            turns = list(
                session.scalars(
                    select(Turn)
                    .where(Turn.conversation_id == conversation_id)
                    .order_by(Turn.sequence)
                )
            )
            # The conversation row lock serializes reservations across processes.
            for pending in turns:
                if pending.status == "processing" and pending.lease_until <= now:
                    pending.status = "failed"
                    pending.error_code = "processing_expired"
            turn = next((t for t in turns if t.request_id == request_id), None)
            if turn:
                original = session.scalar(
                    select(Message).where(Message.turn_id == turn.id, Message.role == "user")
                )
                if original.text != text:
                    raise DomainError(409, "request_id_content_conflict")
                if turn.status == "completed":
                    return self.response(session, turn)
            if any(t.status == "processing" for t in turns):
                raise DomainError(409, "conversation_busy")
            if turn and turns[-1].id != turn.id:
                raise DomainError(409, "stale_turn_retry")
            attempt = str(uuid4())
            if not turn:
                turn = Turn(
                    conversation_id=conversation_id,
                    request_id=request_id,
                    sequence=(turns[-1].sequence + 1 if turns else 1),
                    status="processing",
                    attempt=attempt,
                    lease_until=now + timedelta(seconds=self.lease_seconds),
                )
                session.add(turn)
                session.flush()
                session.add(Message(turn_id=turn.id, role="user", text=text))
            turn.status = "processing"
            turn.attempt = attempt
            turn.error_code = None
            turn.lease_until = now + timedelta(seconds=self.lease_seconds)
            instance = session.get(CharacterInstance, conversation.instance_id)
            version = session.get(CharacterVersion, instance.version_id)
            history_ids = [t.id for t in turns if t.status == "completed"][-self.history_turns :]
            history = session.execute(
                select(Message, Turn.sequence)
                .join(Turn)
                .where(Message.turn_id.in_(history_ids))
                .order_by(Turn.sequence, Message.role.desc())
            ).all()
            messages = [ChatMessage("system", version.system_prompt)]
            messages.extend(ChatMessage(m.role, m.text) for m, _ in history)
            messages.append(ChatMessage("user", text))
            return turn.id, attempt, messages

    def finish_turn(self, user, conversation_id, turn_id, attempt, text=None, error=None):
        with self.sessions.begin() as session:
            self.owned_conversation(session, user, conversation_id, lock=True)
            turn = session.get(Turn, turn_id)
            if (
                not turn
                or turn.conversation_id != conversation_id
                or turn.status != "processing"
                or turn.attempt != attempt
            ):
                raise DomainError(409, "turn_attempt_superseded")
            if error:
                turn.status = "failed"
                turn.error_code = error
                return None
            message = Message(turn_id=turn.id, role="assistant", text=text)
            session.add(message)
            turn.status = "completed"
            session.flush()
            return CharacterResponse(message.id, turn.id, message.text)

    def history(self, user, conversation_id, offset, limit):
        with self.sessions() as session:
            self.owned_conversation(session, user, conversation_id)
            total = session.scalar(
                select(func.count())
                .select_from(Turn)
                .where(Turn.conversation_id == conversation_id)
            )
            turns = list(
                session.scalars(
                    select(Turn)
                    .where(Turn.conversation_id == conversation_id)
                    .order_by(Turn.sequence)
                    .offset(offset)
                    .limit(limit)
                )
            )
            messages = list(
                session.scalars(
                    select(Message)
                    .where(Message.turn_id.in_([t.id for t in turns]))
                    .order_by(Message.role.desc())
                )
            )
            return dict(
                total=total,
                offset=offset,
                limit=limit,
                turns=[
                    dict(
                        turn_id=t.id,
                        request_id=t.request_id,
                        sequence=t.sequence,
                        status=t.status,
                        error_code=t.error_code,
                        messages=[
                            dict(message_id=m.id, role=m.role, text=m.text)
                            for m in messages
                            if m.turn_id == t.id
                        ],
                    )
                    for t in turns
                ],
            )
