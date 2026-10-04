from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from afterstory.character_research import (
    CharacterCatalogEntry,
    LocalizedNames,
    SourcePartRecord,
    SourceRecord,
    write_catalog,
    write_jsonl,
)
from afterstory.video_promotion import promote_reviewed_video


def write_jsonl_dicts(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def make_corpus(root: Path) -> None:
    root.mkdir(parents=True)
    write_catalog(
        root,
        [
            CharacterCatalogEntry(
                character_id="hero",
                names=LocalizedNames(zh="主角"),
                research_status="discovered",
            )
        ],
    )
    write_jsonl(
        root / "sources.jsonl",
        [
            SourceRecord(
                source_id="video-source",
                source_type="story_video",
                provenance="in_game_footage",
                platform="example",
                title="剧情合集",
                url="https://example.com/video",
                retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                status="indexed",
            )
        ],
    )
    write_jsonl(
        root / "source_parts.jsonl",
        [
            SourcePartRecord(
                part_id="video-p01",
                source_id="video-source",
                external_part_id="1",
                position=1,
                title="序章",
                duration_ms=20_000,
                content_type="main_story",
                subtitle_mode="no_platform_subtitles",
                visual_subtitle_status="user_confirmed_present",
            )
        ],
    )
    for filename in (
        "profiles.jsonl",
        "canon_checkpoints.jsonl",
        "scenes.jsonl",
        "canon_evidence.jsonl",
        "world_entities.jsonl",
        "character_facts.jsonl",
        "world_facts.jsonl",
        "character_relations.jsonl",
        "evidence.jsonl",
        "traits.jsonl",
    ):
        (root / filename).write_text("", encoding="utf-8")


def make_staging(staging: Path) -> Path:
    transcript = [
        {
            "reviewed_utterance_id": "u00001",
            "start_ms": 1_000,
            "end_ms": 2_000,
            "text": "第一句",
            "review_status": "approved",
        },
        {
            "reviewed_utterance_id": "u00002",
            "start_ms": 3_000,
            "end_ms": 4_000,
            "text": "第二句",
            "review_status": "approved",
        },
    ]
    write_jsonl_dicts(
        staging / "utterances.jsonl",
        [{"utterance_id": "u00001"}, {"utterance_id": "u00002"}],
    )
    write_jsonl_dicts(
        staging / "review-decisions.jsonl",
        [
            {"utterance_id": "u00001", "decision": "approved"},
            {"utterance_id": "u00002", "decision": "approved"},
        ],
    )
    transcript_path = staging / "reviewed-transcript.jsonl"
    write_jsonl_dicts(transcript_path, transcript)
    return transcript_path


def make_plan(path: Path, transcript_path: Path, *, summary: str = "主角完成对话。") -> None:
    value = {
        "schema_version": "1.0",
        "source_id": "video-source",
        "source_part_id": "video-p01",
        "reviewed_transcript_sha256": hashlib.sha256(transcript_path.read_bytes()).hexdigest(),
        "checkpoint": {
            "schema_version": "1.0",
            "checkpoint_id": "checkpoint-p01",
            "source_work": "异环",
            "display_name": "序章",
            "sequence": 1,
            "content_track": "main_story",
            "game_version": "",
            "chapter": "序章",
            "predecessor_id": "",
            "spoiler_scope": "序章",
        },
        "scenes": [
            {
                "scene_id": "scene-p01-001",
                "start_ms": 1_000,
                "end_ms": 4_000,
                "summary": summary,
                "participants": ["hero"],
                "transcript_refs": ["u00001", "u00002"],
                "evidence": [
                    {
                        "canon_evidence_id": "evidence-p01-001",
                        "start_ms": 1_000,
                        "end_ms": 4_000,
                        "evidence_kind": "dialogue",
                        "actor_character_ids": ["hero"],
                        "speaker_character_id": "hero",
                        "observation": "主角连续说出两句话。",
                        "transcript_refs": ["u00001", "u00002"],
                    }
                ],
            }
        ],
    }
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_promote_reviewed_video_is_validated_and_idempotent(tmp_path: Path):
    root = tmp_path / "corpus"
    staging = tmp_path / "staging"
    plan = tmp_path / "plan.json"
    make_corpus(root)
    transcript_path = make_staging(staging)
    make_plan(plan, transcript_path)

    first = promote_reviewed_video(root, staging, plan)
    second = promote_reviewed_video(root, staging, plan)

    assert first["reviewed_transcript_entries"] == 2
    assert first["promoted_scenes"] == 1
    assert first["promoted_canon_evidence"] == 1
    assert first["idempotent_replay"] is False
    assert second["idempotent_replay"] is True
    assert len((root / "canon_checkpoints.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert len((root / "scenes.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    assert len((root / "canon_evidence.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    part = json.loads((root / "source_parts.jsonl").read_text(encoding="utf-8"))
    assert part["processing_status"] == "reviewed"
    assert part["visual_subtitle_status"] == "verified_present"


def test_promote_reviewed_video_rejects_immutable_collision_without_writes(tmp_path: Path):
    root = tmp_path / "corpus"
    staging = tmp_path / "staging"
    plan = tmp_path / "plan.json"
    make_corpus(root)
    transcript_path = make_staging(staging)
    make_plan(plan, transcript_path)
    promote_reviewed_video(root, staging, plan)
    before = {path.name: path.read_bytes() for path in root.glob("*.jsonl")}

    make_plan(plan, transcript_path, summary="试图覆盖已经入库的场景。")
    with pytest.raises(ValueError, match="immutable record collision"):
        promote_reviewed_video(root, staging, plan)

    assert {path.name: path.read_bytes() for path in root.glob("*.jsonl")} == before


def test_promote_reviewed_video_requires_complete_review_coverage(tmp_path: Path):
    root = tmp_path / "corpus"
    staging = tmp_path / "staging"
    plan = tmp_path / "plan.json"
    make_corpus(root)
    transcript_path = make_staging(staging)
    make_plan(plan, transcript_path)
    decisions = staging / "review-decisions.jsonl"
    decisions.write_text(
        json.dumps({"utterance_id": "u00001", "decision": "approved"}) + "\n",
        encoding="utf-8",
    )
    before = {path.name: path.read_bytes() for path in root.glob("*.jsonl")}

    with pytest.raises(ValueError, match="cover every source utterance"):
        promote_reviewed_video(root, staging, plan)

    assert {path.name: path.read_bytes() for path in root.glob("*.jsonl")} == before
