import json

from afterstory.character.definition import CharacterDefinition
from afterstory.character.prompt import PROMPT_BUILDER_VERSION, build_character_system_prompt
from afterstory.config import ROOT
from afterstory.memory.contracts import ConservativeTokenCounter

PACKAGE_PATHS = (
    ROOT / "fixtures/companions.profile-v1.candidate.json",
    ROOT / "fixtures/companions.canon-p22.json",
)


def test_official_character_candidates_are_valid_uncompiled_definitions():
    assert PROMPT_BUILDER_VERSION == "1.0"

    for package_path in PACKAGE_PATHS:
        packages = json.loads(package_path.read_text(encoding="utf-8"))
        assert {package["character_id"] for package in packages} == {
            "nanally",
            "iroi",
            "mint",
        }
        assert len({package["version_id"] for package in packages}) == len(packages)

        for package in packages:
            assert "system_prompt" not in package
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


def test_p22_mint_definition_uses_cocoa_as_default_address():
    packages = json.loads(PACKAGE_PATHS[1].read_text(encoding="utf-8"))
    mint = next(package for package in packages if package["character_id"] == "mint")

    assert mint["version_id"] == "mint-canon-p22-v1"
    assert "默认称用户为“可可”" in mint["definition"]["speaking_style"]
    assert "强调用户的职业身份或正在讨论鉴定、任务时才称“鉴定师”" in mint[
        "definition"
    ]["speaking_style"]


def test_p22_package_has_final_immutable_version_ids_and_checkpoint():
    packages = json.loads(PACKAGE_PATHS[1].read_text(encoding="utf-8"))

    assert {package["version_id"] for package in packages} == {
        "nanally-canon-p22-v1",
        "iroi-canon-p22-v1",
        "mint-canon-p22-v1",
    }
    assert {package["checkpoint"] for package in packages} == {"nt-bv1kqoabievz-p22"}
