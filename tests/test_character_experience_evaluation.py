import json

import pytest

from afterstory.config import ROOT
from scripts.evaluate_character_experience import load_scenarios, markdown_report
from scripts.evaluate_response_policy import evaluate_result


def test_character_experience_scenarios_reference_frozen_p22_versions():
    scenarios, prompts = load_scenarios(
        ROOT / "fixtures/character_experience_v1.json",
        ROOT / "fixtures/companions.canon-p22.json",
    )
    assert len(scenarios) == 10
    assert {item["version_id"] for item in scenarios} == set(prompts)
    assert all("通用 Character Runtime Rules" in prompt for prompt in prompts.values())


def test_character_experience_rejects_unknown_version(tmp_path):
    source = json.loads(
        (ROOT / "fixtures/character_experience_v1.json").read_text(encoding="utf-8")
    )
    source["scenarios"][0]["version_id"] = "missing-version"
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown_character_version"):
        load_scenarios(fixture, ROOT / "fixtures/companions.canon-p22.json")


def test_character_experience_report_is_readable_for_manual_review():
    report = {
        "started_at": "2026-10-21T00:00:00Z",
        "model": "test-model",
        "prompt_builder_version": "1.0",
        "provider_calls": [{}],
        "scenarios": [
            {
                "id": "example",
                "version_id": "nanally-canon-p22-v1",
                "current": "你好",
                "reply": "你好，鉴定师。",
                "failures": [],
                "warnings": [],
                "manual_checks": ["角色语气自然"],
            }
        ],
    }
    markdown = markdown_report(report)
    assert "你好，鉴定师。" in markdown
    assert "- [ ] 角色语气自然" in markdown


def test_iroi_fixture_flags_the_observed_invented_outing():
    scenarios, _ = load_scenarios(
        ROOT / "fixtures/character_experience_v1.json",
        ROOT / "fixtures/companions.canon-p22.json",
    )
    scenario = next(item for item in scenarios if item["id"] == "iroi-daily-voice")
    failures = evaluate_result(
        scenario,
        "橘子呀，我陪福利院的孩子出门时也见过大人这样挑。",
        [],
    )
    assert any("陪福利院的孩子出门" in failure for failure in failures)
