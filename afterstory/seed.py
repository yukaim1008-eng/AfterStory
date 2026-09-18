"""Explicitly imported immutable engineering fixtures; no main-character canon invented."""

import json

from sqlalchemy.dialects.postgresql import insert

from afterstory.character_definition import CharacterDefinition
from afterstory.character_prompt import build_character_system_prompt
from afterstory.config import ROOT, Settings
from afterstory.database import make_sessions
from afterstory.models import Character, CharacterVersion, User


def seed(sessions, user_id: str, companion_file=None):
    fixtures = json.loads((ROOT / "fixtures/characters.json").read_text(encoding="utf-8"))
    if companion_file:
        fixtures.extend(json.loads(companion_file.read_text(encoding="utf-8")))
    with sessions.begin() as session:
        session.execute(insert(User).values(id=user_id).on_conflict_do_nothing())
        for item in fixtures:
            session.execute(
                insert(Character)
                .values(id=item["character_id"], name=item["name"])
                .on_conflict_do_nothing()
            )
            definition_input = item.get("definition")
            supplied_prompt = item.get("system_prompt")
            if definition_input is not None and supplied_prompt is not None:
                raise ValueError("Structured character packages cannot provide system_prompt")
            if definition_input is None and not isinstance(supplied_prompt, str):
                raise ValueError("Character package requires definition or system_prompt")
            definition = (
                CharacterDefinition.model_validate(definition_input)
                if definition_input is not None
                else None
            )
            values = dict(
                id=item["version_id"],
                character_id=item["character_id"],
                checkpoint=item["checkpoint"],
                definition=definition.model_dump() if definition else None,
                system_prompt=(
                    build_character_system_prompt(definition) if definition else supplied_prompt
                ),
            )
            existing = session.get(CharacterVersion, item["version_id"])
            if existing and any(getattr(existing, k) != v for k, v in values.items()):
                raise ValueError("Character version changed: create a new version_id")
            session.execute(insert(CharacterVersion).values(**values).on_conflict_do_nothing())


if __name__ == "__main__":
    cfg = Settings()
    engine, sessions = make_sessions(cfg)
    try:
        seed(sessions, cfg.dev_user_id, ROOT / "fixtures/companions.integration.json")
        print("Engineering characters and local user seeded.")
    finally:
        engine.dispose()
