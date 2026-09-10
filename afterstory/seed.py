"""Explicitly imported immutable engineering fixtures; no main-character canon invented."""

import json

from sqlalchemy.dialects.postgresql import insert

from afterstory.config import ROOT, Settings
from afterstory.database import make_sessions
from afterstory.models import Character, CharacterVersion, User


def seed(sessions, user_id: str):
    fixtures = json.loads((ROOT / "fixtures/characters.json").read_text(encoding="utf-8"))
    with sessions.begin() as session:
        session.execute(insert(User).values(id=user_id).on_conflict_do_nothing())
        for item in fixtures:
            session.execute(
                insert(Character)
                .values(id=item["character_id"], name=item["name"])
                .on_conflict_do_nothing()
            )
            values = dict(
                id=item["version_id"],
                character_id=item["character_id"],
                checkpoint=item["checkpoint"],
                system_prompt=item["system_prompt"],
            )
            existing = session.get(CharacterVersion, item["version_id"])
            if existing and any(getattr(existing, k) != v for k, v in values.items()):
                raise ValueError("Character version changed: create a new version_id")
            session.execute(insert(CharacterVersion).values(**values).on_conflict_do_nothing())


if __name__ == "__main__":
    cfg = Settings()
    engine, sessions = make_sessions(cfg)
    try:
        seed(sessions, cfg.dev_user_id)
        print("Engineering characters and local user seeded.")
    finally:
        engine.dispose()
