import json

from afterstory.character_definition import CharacterDefinition
from afterstory.character_prompt import PROMPT_BUILDER_VERSION, build_character_system_prompt
from afterstory.config import ROOT

CANDIDATE_PATH = ROOT / "fixtures/companions.profile-v1.candidate.json"


def test_official_character_candidates_are_valid_uncompiled_definitions():
    packages = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))

    assert {package["character_id"] for package in packages} == {"nanally", "iroi", "mint"}
    assert len({package["version_id"] for package in packages}) == len(packages)
    assert PROMPT_BUILDER_VERSION == "1.0"

    for package in packages:
        assert "system_prompt" not in package
        assert package["version_id"].endswith("-candidate")
        definition = CharacterDefinition.model_validate(package["definition"])
        prompt = build_character_system_prompt(definition)

        assert prompt == build_character_system_prompt(definition)
        assert prompt.startswith("通用 Character Runtime Rules：")
        assert all(
            f"{label}：" in prompt
            for label in ("身份", "性格", "说话方式", "行为", "世界观", "初始关系前提")
        )
        assert "PersonalMemory" not in prompt
        assert "CharacterState" not in prompt
        assert "Relationship" not in prompt
