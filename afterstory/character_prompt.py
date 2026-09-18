from afterstory.character_definition import CharacterDefinition

PROMPT_BUILDER_VERSION = "1.0"

_RUNTIME_RULES = (
    "你是 AfterStory 中与用户持续交流的角色。保持自身身份、立场和表达方式；"
    "用户来自另一个世界，双方通过 AfterStory 通信。不要假装亲身经历用户现实世界的事情，"
    "不要编造未提供的共同经历或原作剧情；未知信息应坦诚说明。"
)

_SECTIONS = (
    ("身份", "identity"),
    ("性格", "personality"),
    ("说话方式", "speaking_style"),
    ("行为", "behavior"),
    ("世界观", "worldview"),
    ("初始关系前提", "relationship_premise"),
)


def build_character_system_prompt(definition: CharacterDefinition) -> str:
    """Compile stable definition material in a deterministic, versioned order."""

    sections = ["通用 Character Runtime Rules：" + _RUNTIME_RULES]
    for label, field in _SECTIONS:
        value = getattr(definition, field)
        if value:
            sections.append(f"{label}：{value}")
    return "\n\n".join(sections)
