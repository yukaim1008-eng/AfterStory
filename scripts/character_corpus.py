import argparse
import json
from pathlib import Path

from afterstory.character_research import (
    build_sqlite,
    sync_bilibili,
    sync_ntestation,
    validate_corpus,
)
from afterstory.config import ROOT
from afterstory.video_promotion import promote_reviewed_video

DEFAULT_ROOT = ROOT / "research/character-corpus"


def main():
    parser = argparse.ArgumentParser(description="Manage the local character research corpus.")
    parser.add_argument(
        "command",
        choices=("sync-ntestation", "sync-bilibili", "promote-video", "validate", "build"),
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--bvid")
    parser.add_argument("--staging", type=Path)
    parser.add_argument("--plan", type=Path)
    args = parser.parse_args()

    if args.command == "sync-ntestation":
        stats = sync_ntestation(args.root)
    elif args.command == "sync-bilibili":
        if not args.bvid:
            parser.error("sync-bilibili requires --bvid")
        stats = sync_bilibili(args.root, args.bvid)
    elif args.command == "validate":
        stats = validate_corpus(args.root)
    elif args.command == "promote-video":
        if not args.staging or not args.plan:
            parser.error("promote-video requires --staging and --plan")
        stats = promote_reviewed_video(args.root, args.staging, args.plan)
    else:
        database = args.database or args.root / "local/corpus.sqlite3"
        stats = build_sqlite(args.root, database)
        stats["database"] = str(database.resolve())
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
