from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Literal

from . import PIPELINE_SCHEMA_VERSION, PIPELINE_VERSION

SpeakerStatus = Literal["confirmed", "probable", "ambiguous", "unknown"]
ReviewStatus = Literal["pending", "approved", "rejected"]

_NORMALIZE_PATTERN = re.compile(r"[\s·.…，,。！？!?：:；;、“”‘’『』「」【】()（）\-—~～]")
_CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def format_timestamp(milliseconds: int) -> str:
    total_seconds = max(0, milliseconds // 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def normalized_text(text: str) -> str:
    return _NORMALIZE_PATTERN.sub("", text).casefold()


def contains_cjk(text: str) -> bool:
    return bool(_CJK_PATTERN.search(text))


def useful_dialogue_text(text: str) -> bool:
    return contains_cjk(text) and len(normalized_text(text)) >= 2


def text_similarity(left: str, right: str) -> float:
    left_value = normalized_text(left)
    right_value = normalized_text(right)
    if not left_value or not right_value:
        return 0.0
    if left_value in right_value or right_value in left_value:
        return min(len(left_value), len(right_value)) / max(len(left_value), len(right_value))
    return SequenceMatcher(None, left_value, right_value).ratio()


def same_utterance(left: str, right: str) -> bool:
    left_value = normalized_text(left)
    right_value = normalized_text(right)
    if not left_value or not right_value:
        return False
    if left_value in right_value or right_value in left_value:
        shorter = min(len(left_value), len(right_value))
        longer = max(len(left_value), len(right_value))
        return shorter >= 4 and shorter / longer >= 0.35
    if SequenceMatcher(None, left_value, right_value).ratio() >= 0.78:
        return True
    left_counts = Counter(left_value)
    right_counts = Counter(right_value)
    overlap = sum((left_counts & right_counts).values())
    return overlap / max(len(left_value), len(right_value)) >= 0.78


def choose_preferred_text(left: str, right: str) -> str:
    left_value = normalized_text(left)
    right_value = normalized_text(right)
    if len(right_value) > len(left_value):
        return right
    if len(right_value) == len(left_value) and right.count("…") < left.count("…"):
        return right
    return left


def load_character_names(catalog_path: Path) -> dict[str, str]:
    catalog = read_json(catalog_path)
    names: dict[str, str] = {}
    for row in catalog:
        character_id = row["character_id"]
        for value in row.get("names", {}).values():
            if isinstance(value, str) and value.strip():
                names[normalized_text(value)] = character_id
    return names


def resolve_character_id(label: str | None, character_names: dict[str, str]) -> str | None:
    if not label:
        return None
    return character_names.get(normalized_text(label))


@dataclass(frozen=True)
class RecognizedLine:
    text: str
    score: float
    box: tuple[int, int, int, int]

    @property
    def top(self) -> int:
        return self.box[1]


def interpret_recognized_lines(
    lines: list[RecognizedLine],
    character_names: dict[str, str],
    repeated_labels: set[str] | None = None,
) -> dict | None:
    usable = [line for line in lines if useful_dialogue_text(line.text) and line.score >= 0.45]
    if not usable:
        return None
    usable.sort(key=lambda item: (item.top, item.box[0]))
    if len(usable) == 1:
        only_key = normalized_text(usable[0].text)
        if only_key in character_names or only_key in (repeated_labels or set()):
            return None

    speaker_line: RecognizedLine | None = None
    dialogue_lines = usable
    if len(usable) >= 2:
        first = usable[0]
        remaining = usable[1:]
        first_key = normalized_text(first.text)
        known_name = first_key in character_names
        repeated_label = first_key in (repeated_labels or set())
        if known_name or repeated_label:
            speaker_line = first
            dialogue_lines = remaining

    text = " ".join(line.text.strip() for line in dialogue_lines if line.text.strip())
    if not useful_dialogue_text(text):
        return None
    speaker_label = speaker_line.text.strip() if speaker_line else None
    character_id = resolve_character_id(speaker_label, character_names)
    speaker_status = "confirmed" if character_id or speaker_line else "unknown"
    if character_id:
        attribution_evidence = ["explicit_known_character_label"]
    elif speaker_line:
        attribution_evidence = ["explicit_repeated_screen_label"]
    else:
        attribution_evidence = []
    return {
        "text": text,
        "confidence": round(
            sum(line.score for line in dialogue_lines) / len(dialogue_lines), 4
        ),
        "speaker_label": speaker_label,
        "speaker_id": character_id,
        "speaker_status": speaker_status,
        "attribution_evidence": attribution_evidence,
    }


def merge_ocr_samples(samples: list[dict], max_gap_ms: int = 3500) -> list[dict]:
    ordered = sorted(samples, key=lambda item: (item["start_ms"], item["end_ms"]))
    merged: list[dict] = []
    for sample in ordered:
        if not useful_dialogue_text(sample["text"]):
            continue
        if merged:
            previous = merged[-1]
            previous_identity = previous.get("speaker_id") or normalized_text(
                previous.get("speaker_label") or ""
            )
            sample_identity = sample.get("speaker_id") or normalized_text(
                sample.get("speaker_label") or ""
            )
            previous_identity = previous_identity or None
            sample_identity = sample_identity or None
            same_speaker = (
                previous_identity == sample_identity
                or previous_identity is None
                or sample_identity is None
            )
            close = sample["start_ms"] - previous["end_ms"] <= max_gap_ms
            left_value = normalized_text(previous["text"])
            right_value = normalized_text(sample["text"])
            labeled_partial = (
                previous_identity is not None
                and sample_identity is not None
                and previous_identity == sample_identity
                and min(len(left_value), len(right_value)) >= 2
                and (left_value in right_value or right_value in left_value)
            )
            if close and same_speaker and (
                same_utterance(previous["text"], sample["text"]) or labeled_partial
            ):
                previous["end_ms"] = max(previous["end_ms"], sample["end_ms"])
                previous["end_timestamp"] = format_timestamp(previous["end_ms"])
                previous["text"] = choose_preferred_text(previous["text"], sample["text"])
                previous["confidence"] = max(previous["confidence"], sample["confidence"])
                previous["source_candidates"].extend(sample["source_candidates"])
                if not previous.get("speaker_label") and sample.get("speaker_label"):
                    previous["speaker_label"] = sample["speaker_label"]
                    previous["speaker_id"] = sample.get("speaker_id")
                    previous["speaker_status"] = sample["speaker_status"]
                    previous["attribution_evidence"] = sample["attribution_evidence"]
                continue

        utterance_number = len(merged) + 1
        merged.append(
            {
                "schema_version": PIPELINE_SCHEMA_VERSION,
                "utterance_id": f"u{utterance_number:05d}",
                "start_ms": sample["start_ms"],
                "end_ms": sample["end_ms"],
                "start_timestamp": format_timestamp(sample["start_ms"]),
                "end_timestamp": format_timestamp(sample["end_ms"]),
                "text": sample["text"],
                "confidence": sample["confidence"],
                "speaker_label": sample.get("speaker_label"),
                "speaker_id": sample.get("speaker_id"),
                "speaker_status": sample.get("speaker_status", "unknown"),
                "speaker_candidates": sample.get("speaker_candidates", []),
                "attribution_evidence": sample.get("attribution_evidence", []),
                "source_candidates": list(sample["source_candidates"]),
                "review_status": "pending",
            }
        )
    return merged


def build_scene_drafts(
    part_id: str,
    utterances: list[dict],
    gap_ms: int = 15000,
    padding_ms: int = 2000,
) -> list[dict]:
    if not utterances:
        return []
    groups: list[list[dict]] = [[utterances[0]]]
    for utterance in utterances[1:]:
        if utterance["start_ms"] - groups[-1][-1]["end_ms"] > gap_ms:
            groups.append([utterance])
        else:
            groups[-1].append(utterance)

    scenes = []
    for index, group in enumerate(groups, start=1):
        participants = sorted(
            {
                item["speaker_id"]
                for item in group
                if item.get("speaker_status") == "confirmed" and item.get("speaker_id")
            }
        )
        start_ms = max(0, group[0]["start_ms"] - padding_ms)
        end_ms = group[-1]["end_ms"] + padding_ms
        scenes.append(
            {
                "schema_version": PIPELINE_SCHEMA_VERSION,
                "scene_draft_id": f"{part_id}-scene-{index:03d}",
                "part_id": part_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "start_timestamp": format_timestamp(start_ms),
                "end_timestamp": format_timestamp(end_ms),
                "utterance_ids": [item["utterance_id"] for item in group],
                "confirmed_participants": participants,
                "summary": "",
                "canon_checkpoint": "",
                "review_status": "pending",
            }
        )
    return scenes


def build_review_queue(utterances: list[dict]) -> list[dict]:
    queue = []
    for utterance in utterances:
        reasons = []
        if utterance["speaker_status"] != "confirmed":
            reasons.append("speaker_unconfirmed")
        elif not utterance.get("speaker_id"):
            reasons.append("speaker_label_unmapped")
        if utterance["confidence"] < 0.9:
            reasons.append("low_ocr_confidence")
        if len(normalized_text(utterance["text"])) < 4:
            reasons.append("short_text")
        if reasons:
            queue.append(
                {
                    "utterance_id": utterance["utterance_id"],
                    "timestamp": utterance["start_timestamp"],
                    "text": utterance["text"],
                    "reasons": reasons,
                    "review_status": utterance["review_status"],
                }
            )
    return queue


def validate_staging_bundle(output_dir: Path) -> dict:
    manifest_path = output_dir / "manifest.json"
    utterances_path = output_dir / "utterances.jsonl"
    scenes_path = output_dir / "scenes.draft.jsonl"
    if not manifest_path.exists():
        raise ValueError("missing manifest.json")
    if not utterances_path.exists():
        raise ValueError("missing utterances.jsonl")
    if not scenes_path.exists():
        raise ValueError("missing scenes.draft.jsonl")

    manifest = read_json(manifest_path)
    if manifest.get("schema_version") != PIPELINE_SCHEMA_VERSION:
        raise ValueError("unsupported manifest schema_version")
    if manifest.get("pipeline_version") != PIPELINE_VERSION:
        raise ValueError("unsupported pipeline_version")

    utterances = read_jsonl(utterances_path)
    scenes = read_jsonl(scenes_path)
    utterance_ids = [row.get("utterance_id") for row in utterances]
    if len(utterance_ids) != len(set(utterance_ids)):
        raise ValueError("duplicate utterance_id")
    known_ids = set(utterance_ids)
    for row in utterances:
        if row.get("schema_version") != PIPELINE_SCHEMA_VERSION:
            raise ValueError("unsupported utterance schema_version")
        if row.get("speaker_status") not in {
            "confirmed",
            "probable",
            "ambiguous",
            "unknown",
        }:
            raise ValueError("invalid speaker_status")
        if row.get("review_status") not in {"pending", "approved", "rejected"}:
            raise ValueError("invalid utterance review_status")
        if not useful_dialogue_text(row.get("text", "")):
            raise ValueError("invalid utterance text")
        if row["start_ms"] > row["end_ms"]:
            raise ValueError("utterance range is reversed")
    for row in scenes:
        if not set(row.get("utterance_ids", [])).issubset(known_ids):
            raise ValueError("scene references unknown utterance")
        if row.get("review_status") not in {"pending", "approved", "rejected"}:
            raise ValueError("invalid scene review_status")

    approved = [row for row in utterances if row["review_status"] == "approved"]
    export_ready = bool(utterances) and len(approved) == len(utterances) and all(
        row["review_status"] == "approved" for row in scenes
    )
    return {
        "utterances": len(utterances),
        "scenes": len(scenes),
        "pending_utterances": sum(row["review_status"] == "pending" for row in utterances),
        "unknown_speakers": sum(row["speaker_status"] == "unknown" for row in utterances),
        "export_ready": export_ready,
    }


def pipeline_config_hash(config: dict) -> str:
    payload = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
