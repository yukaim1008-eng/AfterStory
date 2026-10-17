from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from afterstory.character.research import (
    CanonCheckpointRecord,
    CanonEvidenceRecord,
    SceneRecord,
    SourcePartRecord,
    StrictModel,
    read_jsonl,
    validate_corpus,
    write_jsonl,
)

VIDEO_PROMOTION_SCHEMA_VERSION = "1.0"
FORMAL_CORPUS_FILES = (
    "catalog.json",
    "sources.jsonl",
    "source_parts.jsonl",
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
)


class VideoEvidencePlan(StrictModel):
    canon_evidence_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    evidence_kind: Literal["dialogue", "action", "document", "broadcast", "visual"]
    actor_character_ids: list[str] = Field(default_factory=list)
    speaker_character_id: str = ""
    observation: str
    transcript_refs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("video evidence end_ms must be greater than start_ms")
        if not self.observation.strip():
            raise ValueError("video evidence observation cannot be empty")
        return self


class VideoScenePlan(StrictModel):
    scene_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    summary: str
    participants: list[str] = Field(default_factory=list)
    transcript_refs: list[str]
    evidence: list[VideoEvidencePlan] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("video scene end_ms must be greater than start_ms")
        if not self.summary.strip():
            raise ValueError("video scene summary cannot be empty")
        if not self.transcript_refs:
            raise ValueError("video scene must reference reviewed transcript entries")
        return self


class VideoPromotionPlan(StrictModel):
    schema_version: Literal["1.0"] = VIDEO_PROMOTION_SCHEMA_VERSION
    source_id: str
    source_part_id: str
    reviewed_transcript_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint: CanonCheckpointRecord
    scenes: list[VideoScenePlan] = Field(min_length=1)


def _read_jsonl_dicts(path: Path) -> list[dict]:
    if not path.exists():
        raise ValueError(f"missing reviewed staging file: {path}")
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: expected an object")
        rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_reviewed_staging(staging_dir: Path, plan: VideoPromotionPlan) -> dict[str, dict]:
    transcript_path = staging_dir / "reviewed-transcript.jsonl"
    if _sha256(transcript_path) != plan.reviewed_transcript_sha256:
        raise ValueError("reviewed transcript hash does not match promotion plan")

    source_rows = _read_jsonl_dicts(staging_dir / "utterances.jsonl")
    decisions = _read_jsonl_dicts(staging_dir / "review-decisions.jsonl")
    transcript = _read_jsonl_dicts(transcript_path)
    source_ids = [row.get("utterance_id") for row in source_rows]
    decision_ids = [row.get("utterance_id") for row in decisions]
    if len(source_ids) != len(set(source_ids)) or set(source_ids) != set(decision_ids):
        raise ValueError("review decisions must cover every source utterance exactly once")
    if any(row.get("decision") not in {"approved", "rejected"} for row in decisions):
        raise ValueError("review decisions contain an invalid decision")

    approved_ids = {
        row["utterance_id"] for row in decisions if row.get("decision") == "approved"
    }
    reviewed_ids = [row.get("reviewed_utterance_id") for row in transcript]
    if len(reviewed_ids) != len(set(reviewed_ids)) or set(reviewed_ids) != approved_ids:
        raise ValueError("reviewed transcript does not match approved decisions")
    if any(
        row.get("review_status") != "approved"
        or not isinstance(row.get("text"), str)
        or not row["text"].strip()
        for row in transcript
    ):
        raise ValueError("reviewed transcript contains an invalid approved entry")
    return {row["reviewed_utterance_id"]: row for row in transcript}


def _merge_immutable(existing, incoming, id_field: str):
    by_id = {getattr(item, id_field): item for item in existing}
    merged = list(existing)
    for item in incoming:
        item_id = getattr(item, id_field)
        previous = by_id.get(item_id)
        if previous is None:
            by_id[item_id] = item
            merged.append(item)
        elif previous.model_dump(mode="json") != item.model_dump(mode="json"):
            raise ValueError(f"immutable record collision: {id_field}={item_id}")
    return merged


def _validate_plan_coverage(
    plan: VideoPromotionPlan, transcript_by_id: dict[str, dict]
) -> None:
    referenced = [ref for scene in plan.scenes for ref in scene.transcript_refs]
    if len(referenced) != len(set(referenced)):
        raise ValueError("a reviewed transcript entry is assigned to more than one scene")
    if set(referenced) != set(transcript_by_id):
        missing = sorted(set(transcript_by_id) - set(referenced))
        extra = sorted(set(referenced) - set(transcript_by_id))
        raise ValueError(f"promotion scene coverage mismatch; missing={missing}, extra={extra}")

    evidence_ids: list[str] = []
    scene_ids: list[str] = []
    for scene in plan.scenes:
        scene_ids.append(scene.scene_id)
        if len(scene.participants) != len(set(scene.participants)):
            raise ValueError(f"duplicate scene participant: {scene.scene_id}")
        rows = [transcript_by_id[ref] for ref in scene.transcript_refs]
        if min(row["start_ms"] for row in rows) < scene.start_ms or max(
            row["end_ms"] for row in rows
        ) > scene.end_ms:
            raise ValueError(f"reviewed transcript is outside scene range: {scene.scene_id}")
        for evidence in scene.evidence:
            evidence_ids.append(evidence.canon_evidence_id)
            if not set(evidence.transcript_refs) <= set(scene.transcript_refs):
                raise ValueError(
                    f"canon evidence references another scene: {evidence.canon_evidence_id}"
                )
            if evidence.start_ms < scene.start_ms or evidence.end_ms > scene.end_ms:
                raise ValueError(
                    f"canon evidence is outside scene range: {evidence.canon_evidence_id}"
                )
            if not set(evidence.actor_character_ids) <= set(scene.participants) or (
                evidence.speaker_character_id
                and evidence.speaker_character_id not in scene.participants
            ):
                raise ValueError(
                    f"canon evidence actors are outside scene: {evidence.canon_evidence_id}"
                )
    if len(scene_ids) != len(set(scene_ids)):
        raise ValueError("promotion plan contains duplicate scene_id")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("promotion plan contains duplicate canon_evidence_id")


def _write_proposed_corpus(
    target_root: Path,
    source_parts: list[SourcePartRecord],
    checkpoints: list[CanonCheckpointRecord],
    scenes: list[SceneRecord],
    canon_evidence: list[CanonEvidenceRecord],
) -> None:
    write_jsonl(target_root / "source_parts.jsonl", source_parts)
    write_jsonl(target_root / "canon_checkpoints.jsonl", checkpoints)
    write_jsonl(target_root / "scenes.jsonl", scenes)
    write_jsonl(target_root / "canon_evidence.jsonl", canon_evidence)


def promote_reviewed_video(
    corpus_root: Path, staging_dir: Path, plan_path: Path
) -> dict[str, int | str | bool]:
    corpus_root = corpus_root.resolve()
    staging_dir = staging_dir.resolve()
    plan = VideoPromotionPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    transcript_by_id = _validate_reviewed_staging(staging_dir, plan)
    _validate_plan_coverage(plan, transcript_by_id)

    source_parts = read_jsonl(corpus_root / "source_parts.jsonl", SourcePartRecord)
    part_by_id = {item.part_id: item for item in source_parts}
    part = part_by_id.get(plan.source_part_id)
    if part is None or part.source_id != plan.source_id:
        raise ValueError("promotion plan does not match a registered source part")

    incoming_scenes = [
        SceneRecord(
            scene_id=scene.scene_id,
            source_id=plan.source_id,
            source_part_id=plan.source_part_id,
            start_ms=scene.start_ms,
            end_ms=scene.end_ms,
            chapter=plan.checkpoint.chapter or part.title,
            summary=scene.summary,
            participants=scene.participants,
            canon_checkpoint=plan.checkpoint.checkpoint_id,
            review_status="reviewed",
        )
        for scene in plan.scenes
    ]
    incoming_evidence = [
        CanonEvidenceRecord(
            canon_evidence_id=evidence.canon_evidence_id,
            origin_type="scene",
            scene_id=scene.scene_id,
            source_part_id=plan.source_part_id,
            start_ms=evidence.start_ms,
            end_ms=evidence.end_ms,
            evidence_kind=evidence.evidence_kind,
            actor_character_ids=evidence.actor_character_ids,
            speaker_character_id=evidence.speaker_character_id,
            observation=evidence.observation,
            transcript_refs=evidence.transcript_refs,
            review_status="accepted",
            review_notes="由画面字幕逐条复核稿提升；原视频与完整逐字稿保存在本地研究暂存区。",
        )
        for scene in plan.scenes
        for evidence in scene.evidence
    ]

    existing_checkpoints = read_jsonl(
        corpus_root / "canon_checkpoints.jsonl", CanonCheckpointRecord
    )
    existing_scenes = read_jsonl(corpus_root / "scenes.jsonl", SceneRecord)
    existing_canon_evidence = read_jsonl(
        corpus_root / "canon_evidence.jsonl", CanonEvidenceRecord
    )
    already_present = (
        plan.checkpoint.checkpoint_id
        in {item.checkpoint_id for item in existing_checkpoints}
        and {item.scene_id for item in incoming_scenes}
        <= {item.scene_id for item in existing_scenes}
        and {item.canon_evidence_id for item in incoming_evidence}
        <= {item.canon_evidence_id for item in existing_canon_evidence}
        and part.processing_status == "reviewed"
        and part.visual_subtitle_status == "verified_present"
    )
    checkpoints = _merge_immutable(
        existing_checkpoints,
        [plan.checkpoint],
        "checkpoint_id",
    )
    scenes = _merge_immutable(
        existing_scenes,
        incoming_scenes,
        "scene_id",
    )
    canon_evidence = _merge_immutable(
        existing_canon_evidence,
        incoming_evidence,
        "canon_evidence_id",
    )
    updated_parts = [
        item.model_copy(
            update={
                "processing_status": "reviewed",
                "visual_subtitle_status": "verified_present",
            }
        )
        if item.part_id == plan.source_part_id
        else item
        for item in source_parts
    ]

    with tempfile.TemporaryDirectory(prefix="afterstory-canon-promotion-") as temp_name:
        validation_root = Path(temp_name)
        for filename in FORMAL_CORPUS_FILES:
            source = corpus_root / filename
            if source.exists():
                shutil.copy2(source, validation_root / filename)
        _write_proposed_corpus(
            validation_root, updated_parts, checkpoints, scenes, canon_evidence
        )
        validate_corpus(validation_root)

    before = {
        name: (corpus_root / name).read_bytes()
        for name in (
            "source_parts.jsonl",
            "canon_checkpoints.jsonl",
            "scenes.jsonl",
            "canon_evidence.jsonl",
        )
    }
    try:
        _write_proposed_corpus(
            corpus_root, updated_parts, checkpoints, scenes, canon_evidence
        )
        validate_corpus(corpus_root)
    except Exception:
        for name, content in before.items():
            (corpus_root / name).write_bytes(content)
        raise

    return {
        "source_part_id": plan.source_part_id,
        "reviewed_transcript_entries": len(transcript_by_id),
        "promoted_scenes": len(incoming_scenes),
        "promoted_canon_evidence": len(incoming_evidence),
        "idempotent_replay": already_present,
    }
