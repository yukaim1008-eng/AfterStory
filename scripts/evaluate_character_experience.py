"""Evaluate the imported P22 character definitions with a bounded real-model run."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from afterstory.character.definition import CharacterDefinition
from afterstory.character.prompt import PROMPT_BUILDER_VERSION, build_character_system_prompt
from afterstory.config import ROOT, Settings
from afterstory.conversation.provider import ConversationDecisionProvider
from afterstory.providers import ChatCompletionsProvider
from scripts.evaluate_response_policy import (
    MeasuredProvider,
    build_messages,
    evaluate_quality,
    evaluate_result,
)


def load_scenarios(fixture_path: Path, character_path: Path):
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    if fixture.get("schema_version") != "1.0":
        raise ValueError("unsupported_character_experience_fixture")
    if fixture.get("prompt_builder_version") != PROMPT_BUILDER_VERSION:
        raise ValueError("prompt_builder_version_mismatch")
    packages = json.loads(character_path.read_text(encoding="utf-8"))
    prompts = {
        item["version_id"]: build_character_system_prompt(
            CharacterDefinition.model_validate(item["definition"])
        )
        for item in packages
    }
    scenarios = fixture["scenarios"]
    ids = [item["id"] for item in scenarios]
    if len(ids) != len(set(ids)) or not scenarios:
        raise ValueError("duplicate_or_empty_scenarios")
    if any(item["version_id"] not in prompts for item in scenarios):
        raise ValueError("unknown_character_version")
    if any(not item.get("manual_checks") for item in scenarios):
        raise ValueError("manual_checks_required")
    return scenarios, prompts


def markdown_report(report):
    lines = [
        "# AfterStory 正式角色体验测试 V1",
        "",
        f"运行时间：{report['started_at']}",
        f"模型：{report['model']}；Prompt Builder：{report['prompt_builder_version']}",
        f"场景：{len(report['scenarios'])}；Provider 调用：{len(report['provider_calls'])}",
        "",
        "自动检查只识别明确的禁用词、关键事实和问句数量。角色自然度与人设一致性需人工复核。",
        "",
    ]
    for item in report["scenarios"]:
        lines.extend(
            [
                f"## {item['id']}（{item['version_id']}）",
                "",
                f"用户：{item['current']}",
                "",
                "角色回复：",
                "",
                *(f"> {line}" for line in item["reply"].splitlines()),
                "",
                "自动硬检查：" + ("通过" if not item["failures"] else "失败"),
                "自动提示：" + ("无" if not item["warnings"] else "、".join(item["warnings"])),
                "",
                "人工复核点：",
                "",
                *(f"- [ ] {check}" for check in item["manual_checks"]),
                "",
            ]
        )
        if item["failures"]:
            lines.extend(["硬检查失败项：" + "、".join(item["failures"]), ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="deepseek")
    parser.add_argument(
        "--fixture", type=Path, default=ROOT / "fixtures/character_experience_v1.json"
    )
    parser.add_argument("--only", action="append", help="Run one scenario ID; repeat as needed")
    args = parser.parse_args()
    scenarios, prompts = load_scenarios(
        args.fixture, ROOT / "fixtures/companions.canon-p22.json"
    )
    if args.only:
        selected = set(args.only)
        scenarios = [item for item in scenarios if item["id"] in selected]
        if len(scenarios) != len(selected):
            parser.error("Unknown scenario ID")
    settings = Settings(llm_active_model=args.profile)
    profile = settings.active_model
    if profile.provider == "fake" or not profile.api_key.get_secret_value():
        parser.error("Character experience evaluation requires a real model profile")

    measured = MeasuredProvider(ChatCompletionsProvider(settings))
    provider = ConversationDecisionProvider(measured, max_tokens=profile.max_tokens)
    report = {
        "schema_version": "1.0",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "profile": args.profile,
        "model": profile.model,
        "prompt_builder_version": PROMPT_BUILDER_VERSION,
        "prompt_sha256": {
            version: hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            for version, prompt in prompts.items()
        },
        "scenarios": [],
    }
    for scenario in scenarios:
        decision = provider.generate_turn(
            build_messages(prompts[scenario["version_id"]], scenario),
            datetime.now(timezone.utc),
            "Asia/Shanghai",
        )
        actions = [item.action for item in decision.memory_commands]
        actions.extend("set_reminder" for _ in decision.reminder_commands)
        failures = evaluate_result(scenario, decision.reply, actions)
        warnings = evaluate_quality(scenario, decision.reply)
        report["scenarios"].append(
            {
                "id": scenario["id"],
                "version_id": scenario["version_id"],
                "current": scenario["current"],
                "reply": decision.reply,
                "failures": failures,
                "warnings": warnings,
                "manual_checks": scenario["manual_checks"],
            }
        )
        print(("FAIL" if failures else "WARN" if warnings else "PASS") + ": " + scenario["id"])
    report["provider_calls"] = measured.calls
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["hard_passed"] = all(not item["failures"] for item in report["scenarios"])
    output_dir = ROOT / ".local-run"
    output_dir.mkdir(exist_ok=True)
    json_path = output_dir / "character-experience-v1.json"
    markdown_path = output_dir / "character-experience-v1.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(markdown_report(report), encoding="utf-8")
    print(f"Review report: {markdown_path}")
    print(f"Provider calls: {len(measured.calls)}")
    return 0 if report["hard_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
