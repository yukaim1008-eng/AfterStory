"""Stable character seed command and import entry point."""

from afterstory.character.importer import main, seed, seed_defaults

__all__ = ["seed", "seed_defaults"]


if __name__ == "__main__":
    main()
