import argparse
import json

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from afterstory.config import Settings


def diagnose(settings=None, profile=None):
    try:
        settings = settings or (Settings(llm_active_model=profile) if profile else Settings())
        profile = settings.active_model
    except Exception:
        return {
            "ok": False,
            "configuration": {"valid": False},
            "database": {"reachable": False},
            "migration": {"current": False},
        }

    model_ready = bool(
        profile.provider == "fake"
        or (
            profile.base_url
            and profile.model
            and profile.api_key.get_secret_value()
        )
    )
    result = {
        "ok": False,
        "configuration": {
            "valid": True,
            "active_model": settings.llm_active_model,
            "provider": profile.provider,
            "model": profile.model,
            "model_credentials_configured": model_ready,
        },
        "database": {"reachable": False},
        "migration": {"current": False},
    }
    database_url = make_url(settings.database_url.get_secret_value()).update_query_dict(
        {"connect_timeout": "3"}
    )
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            current = set(MigrationContext.configure(connection).get_current_heads())
            expected = set(ScriptDirectory.from_config(Config("alembic.ini")).get_heads())
            result["database"] = {"reachable": True}
            result["migration"] = {
                "current": current == expected,
                "current_revision_count": len(current),
                "expected_revision_count": len(expected),
            }
    except Exception:
        # Diagnostics deliberately omit driver errors because they may include connection data.
        pass
    finally:
        engine.dispose()
    result["ok"] = bool(
        model_ready
        and result["database"]["reachable"]
        and result["migration"]["current"]
    )
    return result


def main():
    parser = argparse.ArgumentParser(description="Run redacted local diagnostics.")
    parser.add_argument("--profile", help="Temporarily select a configured model profile.")
    args = parser.parse_args()
    result = diagnose(profile=args.profile)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
