"""Evaluate Response Policy v1 with a real model and synthetic inputs."""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from afterstory.config import ROOT, Settings
from afterstory.context import ContextAssembler
from afterstory.conversation_provider import ConversationDecisionProvider
from afterstory.domain import ChatMessage
from afterstory.providers import ChatCompletionsProvider
from afterstory.response_policy import RESPONSE_POLICY_VERSION


class MeasuredProvider:
    def __init__(self, provider):
        self.provider = provider
        self.calls = []

    def generate(self, messages):
        started = time.perf_counter()
        result = self.provider.generate(messages)
        self.calls.append(
            {
                "mode": "generate",
                "duration_ms": round((time.perf_counter() - started) * 1000),
                "input_messages": len(messages),
                "output_chars": len(result),
            }
        )
        return result

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


def evaluate_result(scenario, reply, effect_actions):
    failures = []
    for fragment in scenario.get("hard_required_all", []):
        if fragment not in reply:
            failures.append(f"missing:{fragment}")
    required_any = scenario.get("hard_required_any", [])
    if required_any and not any(fragment in reply for fragment in required_any):
        failures.append("missing_any:" + "|".join(required_any))
    for fragment in scenario.get("forbidden", []):
        if fragment.casefold() in reply.casefold():
            failures.append(f"forbidden:{fragment}")
    for action in scenario.get("expected_effect_actions", []):
        if action not in effect_actions:
            failures.append(f"missing_effect:{action}")
    for internal in ("memory_id", "expected_revision", "intent_labels"):
        if internal in reply:
            failures.append(f"internal_leak:{internal}")
    return failures


def evaluate_quality(scenario, reply):
    warnings = []
    for fragment in scenario.get("required_all", []):
        if fragment not in reply:
            warnings.append(f"missing:{fragment}")
    required_any = scenario.get("required_any", [])
    if required_any and not any(fragment in reply for fragment in required_any):
        warnings.append("missing_any:" + "|".join(required_any))
    question_count = reply.count("?") + reply.count("？")
    if question_count > scenario.get("max_questions", 1):
        warnings.append(f"questions:{question_count}")
    return warnings


def build_messages(character_prompt, scenario):
    messages = [ChatMessage("system", character_prompt)]
    memory_items = scenario.get("memory_items") or []
    if memory_items:
        messages.append(
            ChatMessage(
                "system",
                ContextAssembler.MEMORY_HEADER
                + json.dumps(memory_items, ensure_ascii=False, separators=(",", ":")),
            )
        )
    messages.extend(
        ChatMessage(item["role"], item["content"])
        for item in scenario.get("history", [])
    )
    messages.append(ChatMessage("user", scenario["current"]))
    return messages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="deepseek")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=ROOT / "fixtures" / "response_policy_evaluation.json",
    )
    parser.add_argument("--only", action="append", help="Run one scenario id")
    args = parser.parse_args()

    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    settings = Settings(llm_active_model=args.profile)
    profile = settings.active_model
    if profile.provider == "fake" or not profile.api_key.get_secret_value():
        parser.error("Response policy evaluation requires a configured real model profile")

    measured = MeasuredProvider(ChatCompletionsProvider(settings))
    provider = ConversationDecisionProvider(measured, max_tokens=profile.max_tokens)
    selected = set(args.only or [])
    report = {
        "schema_version": "1.0",
        "response_policy_version": RESPONSE_POLICY_VERSION,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "profile": args.profile,
        "model": profile.model,
        "checks": [],
    }
    for scenario in fixture["scenarios"]:
        if selected and scenario["id"] not in selected:
            continue
        decision = provider.generate_turn(
            build_messages(fixture["character_prompt"], scenario),
            datetime.now(timezone.utc),
            "Asia/Shanghai",
        )
        actions = [item.action for item in decision.memory_commands]
        actions.extend("set_reminder" for _ in decision.reminder_commands)
        failures = evaluate_result(scenario, decision.reply, actions)
        warnings = evaluate_quality(scenario, decision.reply)
        report["checks"].append(
            {
                "id": scenario["id"],
                "passed": not failures,
                "quality_passed": not warnings,
                "failures": failures,
                "warnings": warnings,
                "reply": decision.reply,
                "effect_actions": actions,
            }
        )
    report["provider_calls"] = measured.calls
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    if not report["checks"]:
        parser.error("No evaluation scenarios matched --only")
    passed_count = sum(item["quality_passed"] for item in report["checks"])
    report["quality_pass_rate"] = passed_count / len(report["checks"])
    report["passed"] = all(item["passed"] for item in report["checks"]) and (
        report["quality_pass_rate"] >= 0.8
    )

    output_dir = ROOT / ".local-run"
    output_dir.mkdir(exist_ok=True)
    output = output_dir / "response-policy-evaluation.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in report["checks"]:
        label = "FAIL" if not item["passed"] else ("WARN" if item["warnings"] else "PASS")
        print(label + ": " + item["id"])
        if item["failures"]:
            print("  " + ", ".join(item["failures"]))
        if item["warnings"]:
            print("  " + ", ".join(item["warnings"]))
    print(f"Report: {output}")
    print(f"Provider calls: {len(report['provider_calls'])}")
    print(f"Quality pass rate: {report['quality_pass_rate']:.1%}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
