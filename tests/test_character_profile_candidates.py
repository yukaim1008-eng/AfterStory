import json

from afterstory.character_definition import CharacterDefinition
from afterstory.character_prompt import PROMPT_BUILDER_VERSION, build_character_system_prompt
from afterstory.config import ROOT
from afterstory.memory_contracts import ConservativeTokenCounter

CANDIDATE_PATHS = (
    ROOT / "fixtures/companions.profile-v1.candidate.json",
    ROOT / "fixtures/companions.canon-p22.candidate.json",
)


def test_official_character_candidates_are_valid_uncompiled_definitions():
    assert PROMPT_BUILDER_VERSION == "1.0"

    for candidate_path in CANDIDATE_PATHS:
        packages = json.loads(candidate_path.read_text(encoding="utf-8"))
        assert {package["character_id"] for package in packages} == {
            "nanally",
            "iroi",
            "mint",
        }
        assert len({package["version_id"] for package in packages}) == len(packages)

        for package in packages:
            assert "system_prompt" not in package
            assert package["version_id"].endswith("-candidate")
            definition = CharacterDefinition.model_validate(package["definition"])
            prompt = build_character_system_prompt(definition)

            assert prompt == build_character_system_prompt(definition)
            assert prompt.startswith("通用 Character Runtime Rules：")
            assert all(
                f"{label}：" in prompt
                for label in (
                    "身份",
                    "性格",
                    "说话方式",
                    "行为",
                    "世界观",
                    "初始关系前提",
                )
            )
            assert "PersonalMemory" not in prompt
            assert "CharacterState" not in prompt
            assert "Relationship" not in prompt
            assert ConservativeTokenCounter().count(prompt) + 4 <= 2500


def test_p22_mint_candidate_uses_cocoa_as_default_address():
    packages = json.loads(CANDIDATE_PATHS[1].read_text(encoding="utf-8"))
    mint = next(package for package in packages if package["character_id"] == "mint")

    assert "默认称用户为“可可”" in mint["definition"]["speaking_style"]
    assert "强调用户的职业身份或正在讨论鉴定、任务时才称“鉴定师”" in mint[
        "definition"
    ]["speaking_style"]
