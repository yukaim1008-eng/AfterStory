from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select

from afterstory.context import ContextAssembler
from afterstory.domain import CharacterResponse, DomainError
from afterstory.models import (
    Character,
    CharacterInstance,
    CharacterVersion,
    Conversation,
    Message,
    Turn,
    User,
)


class Repository:
    def __init__(self, sessions, lease_seconds=120, history_turns=12, context=None):
        self.sessions = sessions
        self.lease_seconds = lease_seconds
        self.history_turns = history_turns
        self.context = context or ContextAssembler(history_turns=history_turns)

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

    def open_session(self, user, version_id):
        with self.sessions.begin() as session:
            if not session.scalar(select(User).where(User.id == user).with_for_update()):
                raise DomainError(404, "user_not_found")
            if not session.get(CharacterVersion, version_id):
                raise DomainError(404, "character_version_not_found")
            conversation = session.scalar(
                select(Conversation)
                .join(CharacterInstance)
                .where(
                    CharacterInstance.user_id == user,
                    CharacterInstance.version_id == version_id,
                )
                .order_by(Conversation.id)
                .limit(1)
            )
            if not conversation:
                instance = session.scalar(
                    select(CharacterInstance)
                    .where(
                        CharacterInstance.user_id == user,
                        CharacterInstance.version_id == version_id,
                    )
                    .order_by(CharacterInstance.id)
                    .limit(1)
                )
                if not instance:
                    instance = CharacterInstance(user_id=user, version_id=version_id)
                    session.add(instance)
                    session.flush()
                conversation = Conversation(instance_id=instance.id)
                session.add(conversation)
                session.flush()
            return dict(conversation_id=conversation.id, instance_id=conversation.instance_id)

    def conversations(self, user):
        # Compatibility endpoint. New clients use paginated conversation_catalog.
        return self.conversation_catalog(user, 0, None)["items"]

    def conversation_catalog(self, user, offset=0, limit=20, conversation_id=None):
        with self.sessions() as session:
            activity = (
                select(
                    Turn.conversation_id.label("conversation_id"),
                    func.count().label("turns"),
                    func.max(func.coalesce(Turn.updated_at, Turn.created_at)).label(
                        "last_activity_at"
                    ),
                )
                .group_by(Turn.conversation_id)
                .subquery()
            )
            preview = (
                select(Message.text)
                .join(Turn)
                .where(Turn.conversation_id == Conversation.id)
                .order_by(Turn.sequence.desc(), Message.role)
                .limit(1)
                .correlate(Conversation)
                .scalar_subquery()
            )
            last_activity = func.coalesce(activity.c.last_activity_at, Conversation.created_at)
            query = (
                select(
                    Conversation.id.label("conversation_id"),
                    Conversation.instance_id,
                    CharacterVersion.character_id,
                    Character.name,
                    CharacterInstance.version_id,
                    CharacterVersion.checkpoint,
                    Conversation.created_at,
                    last_activity.label("last_activity_at"),
                    func.coalesce(activity.c.turns, 0).label("turns"),
                    preview.label("preview"),
                )
                .join(CharacterInstance, CharacterInstance.id == Conversation.instance_id)
                .join(CharacterVersion, CharacterVersion.id == CharacterInstance.version_id)
                .join(Character, Character.id == CharacterVersion.character_id)
                .outerjoin(activity, activity.c.conversation_id == Conversation.id)
                .where(CharacterInstance.user_id == user)
            )
            if conversation_id is not None:
                query = query.where(Conversation.id == conversation_id)
            else:
                query = query.where(activity.c.turns > 0)
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            rows = session.execute(
                query.order_by(last_activity.desc().nulls_last(), Conversation.id)
                .offset(offset)
                .limit(limit)
            ).mappings()
            items = [dict(row, preview=(row["preview"] or "")[:160]) for row in rows]
            return dict(items=items, total=total, offset=offset, limit=limit)

    def conversation_info(self, user, conversation_id):
        result = self.conversation_catalog(user, conversation_id=conversation_id)
        if not result["items"]:
            raise DomainError(404, "conversation_not_found")
        return result["items"][0]

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
            instance = session.scalar(
                select(CharacterInstance)
                .where(CharacterInstance.id == conversation.instance_id)
                .with_for_update()
            )
            version = session.get(CharacterVersion, instance.version_id)
            attempt = str(uuid4())
            if not turn:
                turn = Turn(
                    conversation_id=conversation_id,
                    request_id=request_id,
                    sequence=(turns[-1].sequence + 1 if turns else 1),
                    status="processing",
                    attempt=attempt,
                    lease_until=now + timedelta(seconds=self.lease_seconds),
                    context_revision=instance.context_revision,
                )
                session.add(turn)
                session.flush()
                session.add(Message(turn_id=turn.id, role="user", text=text))
            turn.status = "processing"
            turn.updated_at = now
            turn.attempt = attempt
            turn.error_code = None
            turn.lease_until = now + timedelta(seconds=self.lease_seconds)
            turn.context_revision = instance.context_revision
            messages = self.context.build(
                session, conversation_id, instance, version.system_prompt, text
            )
            return turn.id, attempt, messages

    def finish_turn(self, user, conversation_id, turn_id, attempt, text=None, error=None):
        context_changed = False
        response = None
        with self.sessions.begin() as session:
            conversation = self.owned_conversation(session, user, conversation_id, lock=True)
            turn = session.get(Turn, turn_id)
            if (
                not turn
                or turn.conversation_id != conversation_id
                or turn.status != "processing"
                or turn.attempt != attempt
            ):
                raise DomainError(409, "turn_attempt_superseded")
            if error:
                turn.updated_at = datetime.now(timezone.utc)
                turn.status = "failed"
                turn.error_code = error
                return None
            instance = session.scalar(
                select(CharacterInstance)
                .where(CharacterInstance.id == conversation.instance_id)
                .with_for_update()
            )
            if turn.context_revision != instance.context_revision:
                turn.updated_at = datetime.now(timezone.utc)
                turn.status = "failed"
                turn.error_code = "context_changed"
                context_changed = True
            else:
                message = Message(turn_id=turn.id, role="assistant", text=text)
                turn.updated_at = datetime.now(timezone.utc)
                session.add(message)
                turn.status = "completed"
                session.flush()
                response = CharacterResponse(message.id, turn.id, message.text)
        if context_changed:
            raise DomainError(409, "context_changed")
        return response

    def history(self, user, conversation_id, offset, limit, around_turn_id=None):
        with self.sessions() as session:
            self.owned_conversation(session, user, conversation_id)
            if around_turn_id:
                source = session.get(Turn, around_turn_id)
                if not source or source.conversation_id != conversation_id:
                    raise DomainError(404, "turn_not_found")
                offset = max(0, source.sequence - 1 - limit // 2)
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
                        created_at=t.created_at,
                        messages=[
                            dict(message_id=m.id, role=m.role, text=m.text)
                            for m in messages
                            if m.turn_id == t.id
                        ],
                    )
                    for t in turns
                ],
            )
