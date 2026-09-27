"""Run bounded real-model conversation and memory evaluation in an isolated schema."""

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, select, text

from afterstory.config import ROOT, Settings
from afterstory.continuity import ContinuityService
from afterstory.conversation import ConversationService
from afterstory.database import make_sessions
from afterstory.memory_provider import StructuredMemoryProvider
from afterstory.memory_worker import MemoryRuntimeWorker
from afterstory.models import (
    MemoryJob,
    Message,
    PersonalMemory,
    SegmentSummary,
    Turn,
)
from afterstory.providers import ChatCompletionsProvider
from afterstory.reminders import MatterService
from afterstory.repository import Repository
from afterstory.seed import seed


class MeasuredProvider:
    def __init__(self, provider):
        self.provider = provider
        self.calls = []

    def _call(self, method, messages):
        started = time.perf_counter()
        result = getattr(self.provider, method)(messages)
        self.calls.append(
            {
                "mode": method,
                "duration_ms": round((time.perf_counter() - started) * 1000),
                "input_messages": len(messages),
                "output_chars": len(result),
            }
        )
        return result

    def generate(self, messages):
        return self._call("generate", messages)

    def generate_json(self, messages, max_tokens=None):
        started = time.perf_counter()
        result = self.provider.generate_json(messages, max_tokens=max_tokens)
        self.calls.append(
            {
                "mode": "generate_json",
                "duration_ms": round((time.perf_counter() - started) * 1000),
                "input_messages": len(messages),
                "output_chars": len(result),
                "max_tokens": max_tokens,
            }
        )
        return result


def isolated_url(base_url, schema):
    separator = "&" if "?" in base_url else "?"
    return base_url + separator + "options=-csearch_path%3D" + schema


def contains_all(text_value, fragments):
    return all(fragment in text_value for fragment in fragments)


def add_check(report, check_id, passed, evidence):
    report["checks"].append(
        {"id": check_id, "passed": bool(passed), "evidence": evidence}
    )


def drain_worker(worker, sessions, instance_id=None, max_jobs=100):
    for _ in range(max_jobs):
        if not worker.run_once():
            break
    with sessions() as session:
        query = select(MemoryJob)
        if instance_id:
            query = query.where(MemoryJob.instance_id == instance_id)
        return [
            {
                "job_type": job.job_type,
                "status": job.status,
                "attempts": job.attempts,
                "error_code": job.error_code,
            }
            for job in session.scalars(query.order_by(MemoryJob.created_at))
        ]


def memory_snapshot(sessions, instance_id):
    with sessions() as session:
        rows = session.scalars(
            select(PersonalMemory)
            .where(
                PersonalMemory.instance_id == instance_id,
                PersonalMemory.status == "active",
            )
            .order_by(PersonalMemory.created_at, PersonalMemory.id)
        )
        rows = list(rows)
        return "\n".join(row.content or "" for row in rows), len(rows)


def run_memory_scenario(data, sessions, measured, report):
    user = data["user_id"]
    seed(sessions, user)
    repo = Repository(sessions)
    service = ConversationService(repo, measured)
    structured = StructuredMemoryProvider(measured)
    worker = MemoryRuntimeWorker(sessions, structured, structured)
    instance_id = repo.create_instance(user, data["version_id"])["instance_id"]
    conversation_id = repo.create_conversation(user, instance_id)["conversation_id"]
    replies = []
    for index, statement in enumerate(data["statements"]):
        reply = service.send(
            user,
            conversation_id,
            f"{data['id']}-statement-{index}",
            statement,
            timezone_name=data["timezone"],
            timezone_source="client_reported",
        )
        replies.append(reply.text)
        jobs = drain_worker(worker, sessions, instance_id)

    memories, memory_count = memory_snapshot(sessions, instance_id)
    add_check(
        report,
        f"{data['id']}:memory-expected",
        contains_all(memories, data["expected_memory_contains"]),
        {"required": data["expected_memory_contains"], "memories": memories},
    )
    forbidden = [item for item in data["forbidden_memory_contains"] if item in memories]
    add_check(
        report,
        f"{data['id']}:memory-forbidden",
        not forbidden,
        {"forbidden_found": forbidden},
    )
    if "expected_memory_count" in data:
        add_check(
            report,
            f"{data['id']}:memory-count",
            memory_count == data["expected_memory_count"],
            {"expected": data["expected_memory_count"], "actual": memory_count},
        )
    add_check(
        report,
        f"{data['id']}:jobs",
        all(item["status"] == "completed" for item in jobs),
        jobs,
    )

    recalled = repo.create_conversation(user, instance_id)["conversation_id"]
    prepared = repo.prepare_context(user, recalled, data["recall_question"])
    context_text = "\n".join(message.content for message in prepared.messages)
    add_check(
        report,
        f"{data['id']}:runtime-context",
        contains_all(context_text, data["expected_memory_contains"]),
        {
            "selected_memory_ids": repo.retrieval.prepare(
                instance_id, data["recall_question"]
            ).selected_ids
        },
    )
    recall = service.send(
        user,
        recalled,
        f"{data['id']}-recall",
        data["recall_question"],
        timezone_name=data["timezone"],
        timezone_source="client_reported",
    ).text
    add_check(
        report,
        f"{data['id']}:response",
        contains_all(recall, data["response_contains"])
        and not any(item in recall for item in data.get("response_forbidden", [])),
        {"required": data["response_contains"], "reply": recall},
    )
    report["scenarios"].append(
        {"id": data["id"], "instance_id": instance_id, "replies": replies, "recall": recall}
    )


def run_isolation(data, sessions, measured, report):
    for user in (data["source_user_id"], data["other_user_id"]):
        seed(sessions, user)
    repo = Repository(sessions)
    service = ConversationService(repo, measured)
    structured = StructuredMemoryProvider(measured)
    worker = MemoryRuntimeWorker(sessions, structured, structured)
    source = repo.create_instance(data["source_user_id"], data["version_id"])["instance_id"]
    source_conversation = repo.create_conversation(data["source_user_id"], source)[
        "conversation_id"
    ]
    service.send(
        data["source_user_id"],
        source_conversation,
        "isolation-source",
        data["private_statement"],
    )
    drain_worker(worker, sessions, source)
    other = repo.create_instance(data["other_user_id"], data["version_id"])["instance_id"]
    other_conversation = repo.create_conversation(data["other_user_id"], other)["conversation_id"]
    prepared = repo.prepare_context(
        data["other_user_id"], other_conversation, data["probe_question"]
    )
    context_text = "\n".join(item.content for item in prepared.messages)
    add_check(
        report,
        "cross-user-isolation",
        data["forbidden_context"] not in context_text,
        {
            "other_selected_memory_ids": repo.retrieval.prepare(
                other, data["probe_question"]
            ).selected_ids
        },
    )


def insert_long_conversation(sessions, conversation_id, turns):
    now = datetime.now(timezone.utc)
    with sessions.begin() as session:
        for sequence, (user_text, assistant_text) in enumerate(turns, start=1):
            turn = Turn(
                conversation_id=conversation_id,
                request_id=f"long-{sequence}",
                sequence=sequence,
                status="completed",
                attempt=str(uuid4()),
                lease_until=now,
                context_revision=0,
            )
            session.add(turn)
            session.flush()
            session.add_all(
                [
                    Message(
                        turn_id=turn.id,
                        role="user",
                        text=user_text,
                        recorded_at=now + timedelta(minutes=sequence * 2),
                        timezone_name="Asia/Shanghai",
                        timezone_source="client_reported",
                    ),
                    Message(
                        turn_id=turn.id,
                        role="assistant",
                        text=assistant_text,
                        recorded_at=now + timedelta(minutes=sequence * 2 + 1),
                        timezone_name="UTC",
                        timezone_source="server",
                    ),
                ]
            )


def run_long_conversation(data, sessions, measured, report):
    user = data["user_id"]
    seed(sessions, user)
    repo = Repository(sessions)
    instance_id = repo.create_instance(user, data["version_id"])["instance_id"]
    original = repo.create_conversation(user, instance_id)["conversation_id"]
    insert_long_conversation(sessions, original, data["turns"])
    structured = StructuredMemoryProvider(measured)
    segment_id = ContinuityService(sessions, structured).summarize_next(instance_id, original)
    with sessions() as session:
        summary = session.scalar(
            select(SegmentSummary).where(SegmentSummary.segment_id == segment_id)
        )
        summary_text = summary.text if summary else ""
    add_check(
        report,
        "long-conversation:summary",
        bool(summary_text) and data["topic_token"] in summary_text,
        {"summary": summary_text},
    )
    resumed = repo.create_conversation(user, instance_id)["conversation_id"]
    prepared = repo.prepare_context(user, resumed, data["resume_question"])
    context_text = "\n".join(item.content for item in prepared.messages)
    add_check(
        report,
        "long-conversation:context",
        data["topic_token"] in context_text,
        {"context_has_summary": data["topic_token"] in context_text},
    )
    reply = ConversationService(repo, measured).send(
        user, resumed, "long-resume", data["resume_question"]
    ).text
    add_check(
        report,
        "long-conversation:response",
        contains_all(reply, data["response_contains"]),
        {"required": data["response_contains"], "reply": reply},
    )
    report["scenarios"].append(
        {"id": "long-conversation", "instance_id": instance_id, "recall": reply}
    )


def run_reminder(sessions, report):
    user = "eval-reminder"
    seed(sessions, user)
    repo = Repository(sessions)
    instance_id = repo.create_instance(user, "test-schema-v1")["instance_id"]
    reminders = MatterService(sessions)
    due = datetime.now(timezone.utc) - timedelta(minutes=1)
    matter = reminders.create(
        user,
        instance_id,
        "runtime-eval-reminder",
        "带上社区阅读角的钥匙",
        scheduled_at=due,
        time_precision="instant",
        timezone_name="Asia/Shanghai",
    )
    claim = reminders.claim_due(user, instance_id)
    result = reminders.acknowledge(
        user, claim["delivery_id"], claim["lease_token"], True
    )
    add_check(
        report,
        "in-app-reminder",
        claim["matter_id"] == matter["matter_id"] and result["status"] == "delivered",
        {"content": claim["content"], "status": result["status"]},
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="deepseek")
    parser.add_argument(
        "--fixture", type=Path, default=ROOT / "fixtures" / "runtime_evaluation.json"
    )
    parser.add_argument(
        "--only",
        action="append",
        help="Run one scenario id; repeat for multiple ids. Also accepts isolation/long/reminder.",
    )
    parser.add_argument("--keep-schema", action="store_true")
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    base = Settings()
    if args.profile == "fake":
        parser.error("Runtime evaluation requires a real model profile")
    profile = base.llm_models.get(args.profile)
    if not profile or not profile.api_key.get_secret_value():
        parser.error("Selected real model profile is missing its API key")

    schema = "eval_" + uuid4().hex
    base_url = base.database_url.get_secret_value()
    admin = create_engine(base_url)
    report = {
        "schema_version": "1.0",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "profile": args.profile,
        "model": profile.model,
        "checks": [],
        "scenarios": [],
    }
    previous_url = os.environ.get("DATABASE_URL")
    engine = None
    try:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        test_url = isolated_url(base_url, schema)
        os.environ["DATABASE_URL"] = test_url
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        settings = Settings(database_url=test_url, llm_active_model=args.profile)
        engine, sessions = make_sessions(settings)
        measured = MeasuredProvider(ChatCompletionsProvider(settings))
        selected = set(args.only or [])
        for scenario in fixture["memory_scenarios"]:
            if not selected or scenario["id"] in selected:
                run_memory_scenario(scenario, sessions, measured, report)
        if not selected or "isolation" in selected:
            run_isolation(fixture["isolation"], sessions, measured, report)
        if not selected or "long" in selected:
            run_long_conversation(fixture["long_conversation"], sessions, measured, report)
        if not selected or "reminder" in selected:
            run_reminder(sessions, report)
        report["provider_calls"] = measured.calls
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["passed"] = all(item["passed"] for item in report["checks"])
    finally:
        if engine:
            engine.dispose()
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url
        if not args.keep_schema:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()

    output_dir = ROOT / ".local-run"
    output_dir.mkdir(exist_ok=True)
    output = output_dir / "runtime-evaluation.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in report["checks"]:
        print(("PASS" if item["passed"] else "FAIL") + ": " + item["id"])
    print(f"Report: {output}")
    print(f"Provider calls: {len(report['provider_calls'])}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
