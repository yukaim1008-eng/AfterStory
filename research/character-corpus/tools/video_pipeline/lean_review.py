from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .core import (
    normalized_text,
    read_json,
    read_jsonl,
    text_similarity,
    write_json,
    write_jsonl,
)
from .low_cost_review import LOW_COST_REVIEW_INSTRUCTIONS, _risk_reasons

LEAN_REVIEW_PROTOCOL_VERSION = "2.0"
LEAN_REVIEW_PROMPT_VERSION = "2.0"
MAX_TARGETS_PER_PACKET = 100
MAX_RESPONSE_BYTES = 500_000

_TERMINAL_PUNCTUATION = re.compile(r"[。！？!?…）》」』]$")
_PACKET_KEYS = {
    "protocol_version",
    "prompt_version",
    "packet_id",
    "input_sha256",
    "part_id",
    "title",
    "frame_root",
    "targets",
    "utterances",
    "metrics",
}
_RESPONSE_KEYS = {
    "protocol_version",
    "prompt_version",
    "packet_id",
    "input_sha256",
    "reviewer",
    "reviewed_ids",
    "changes",
}
_REVIEWER_KEYS = {"kind", "model"}
_CHANGE_KEYS = {
    "utterance_id",
    "action",
    "reviewed_text",
    "content_kind",
    "speaker_label",
    "speaker_id",
    "speaker_status",
    "reason_codes",
}
_HIGH_REVIEW_KEYS = {
    "utterance_id",
    "decision",
    "content_kind",
    "reviewed_text",
    "speaker_label",
    "speaker_id",
    "speaker_status",
    "confidence",
    "reason_codes",
    "evidence",
    "reviewed_by",
}
_CONTENT_KINDS = {
    "dialogue",
    "entity_voice",
    "system_or_broadcast",
    "world_document_text",
    "gameplay_ui",
    "background_text",
    "unknown",
}
_SPEAKER_STATUSES = {"confirmed", "probable", "ambiguous", "unknown"}
_SAFE_REJECT_REASONS = {
    "partial_duplicate",
    "false_positive_background_text",
    "gameplay_ui",
    "ocr_fragment",
}


LEAN_REVIEW_INSTRUCTIONS = """# 剧情文本稀疏审核协议 2.0

本包只做文本预审，不读取图片。只审核 `targets` 中的 ID；`utterances` 还包含相邻上下文。

默认规则：如果一条 target 是有效剧情内容、原文无需修改、现有说话者信息无需修改，
不要为它生成 change。把所有 target ID 原样放进 `reviewed_ids` 即表示逐条检查完成。

只有以下情况才写入 `changes`：

- `edit`：需要修正文本、内容类型或保守说话者信息；
- `reject`：明确疑似 UI、背景误识别、逐字字幕中间态或无意义 OCR 残片；
- `escalate`：仅凭文本不能可靠决定，需要后续看画面。

文本阶段不得把未确认说话者升级为 `confirmed`。不确定时保持 `unknown` 或 `escalate`。
`reject` 和 `escalate` 会自动进入视觉复核，不能直接污染正式审核稿。

输出一个 JSON 对象，不要 Markdown。顶层必须且只能包含：
`protocol_version`、`prompt_version`、`packet_id`、`input_sha256`、`reviewer`、
`reviewed_ids`、`changes`。

change 必须完整包含：`utterance_id`、`action`、`reviewed_text`、`content_kind`、
`speaker_label`、`speaker_id`、`speaker_status`、`reason_codes`。`action` 只能是
`edit`、`reject`、`escalate`。reject/escalate 的 reviewed_text 必须为 null。
"""

LEAN_VISUAL_REVIEW_INSTRUCTIONS = """# 剧情视觉升级审核协议 2.0

只审核 `visual-queue.jsonl` 中的条目，并按 `frame_path` 查看对应画面。每个条目必须
最终决定 `approve` 或 `reject`，不得继续输出 escalate。输出 JSON 对象，顶层只能有
`reviewer`、`decisions`。reviewer.kind 必须为 `high_capability_model`。

每条 decision 必须完整包含：`utterance_id`、`decision`、`content_kind`、
`reviewed_text`、`speaker_label`、`speaker_id`、`speaker_status`、`confidence`、
`reason_codes`、`evidence`、`reviewed_by`。confidence 必须为 high，evidence 必须包含
frame_inspected。拒绝只限 UI、背景误识别、逐字字幕中间态或 OCR 残片，并令
reviewed_text 为 null。
"""


def _strict_keys(value: dict, expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{label} fields mismatch; "
            f"missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}"
        )


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_compact_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _catalog_character_ids(catalog_path: Path) -> list[str]:
    return sorted(row["character_id"] for row in read_json(catalog_path))


def _local_safe(utterance: dict, risks: set[str]) -> bool:
    text = utterance.get("text", "").strip()
    known_speaker = utterance.get("speaker_status") == "confirmed" and bool(
        utterance.get("speaker_id")
    )
    return bool(
        known_speaker
        and utterance.get("confidence", 0) >= 0.95
        and len(normalized_text(text)) >= 6
        and _TERMINAL_PUNCTUATION.search(text)
        and not risks
    )


def _default_decision(utterance: dict, reviewed_by: str) -> dict:
    known_speaker = utterance.get("speaker_status") == "confirmed" and bool(
        utterance.get("speaker_id")
    )
    return {
        "utterance_id": utterance["utterance_id"],
        "decision": "approve",
        "content_kind": "dialogue" if known_speaker else "unknown",
        "reviewed_text": utterance["text"],
        "speaker_label": utterance.get("speaker_label"),
        "speaker_id": utterance.get("speaker_id") if known_speaker else None,
        "speaker_status": "confirmed" if known_speaker else "unknown",
        "confidence": "high",
        "reason_codes": ["unchanged_after_review"],
        "evidence": ["text_sequence_review"],
        "reviewed_by": reviewed_by,
    }


def _compact_utterance(utterance: dict, review_required: bool, risks: list[str]) -> dict:
    return {
        "id": utterance["utterance_id"],
        "time": [utterance["start_ms"], utterance["end_ms"]],
        "text": utterance["text"],
        "ocr": utterance["confidence"],
        "speaker": [
            utterance.get("speaker_label"),
            utterance.get("speaker_id"),
            utterance.get("speaker_status", "unknown"),
        ],
        "risks": risks,
        "review_required": review_required,
    }


def _build_packet(
    output_dir: Path,
    manifest: dict,
    utterances: list[dict],
    target_indices: list[int],
    packet_dir: Path,
) -> dict:
    context_indices = set(target_indices)
    for index in target_indices:
        if index:
            context_indices.add(index - 1)
        if index + 1 < len(utterances):
            context_indices.add(index + 1)
    targets = [utterances[index]["utterance_id"] for index in target_indices]
    target_set = set(targets)
    compact = []
    for index in sorted(context_indices):
        previous = utterances[index - 1] if index else None
        following = utterances[index + 1] if index + 1 < len(utterances) else None
        row = utterances[index]
        compact.append(
            _compact_utterance(
                row,
                row["utterance_id"] in target_set,
                _risk_reasons(row, previous, following),
            )
        )
    source = {
        "protocol_version": LEAN_REVIEW_PROTOCOL_VERSION,
        "prompt_version": LEAN_REVIEW_PROMPT_VERSION,
        "part_id": manifest["part_id"],
        "title": manifest.get("title", ""),
        "frame_root": str((output_dir / "review-full-frames").resolve()),
        "targets": targets,
        "utterances": compact,
    }
    input_sha256 = _canonical_sha256(source)
    packet_id = f"{manifest['part_id']}-lean-{targets[0]}-{targets[-1]}-{input_sha256[:12]}"
    packet = {
        **source,
        "packet_id": packet_id,
        "input_sha256": input_sha256,
        "metrics": {
            "target_count": len(targets),
            "context_count": len(compact) - len(targets),
            "visual_count": 0,
        },
    }
    _strict_keys(packet, _PACKET_KEYS, "lean packet")
    _write_compact_json(packet_dir / "request.json", packet)
    (packet_dir / "instructions.md").write_text(LEAN_REVIEW_INSTRUCTIONS, encoding="utf-8")
    minimum_response = {
        "protocol_version": packet["protocol_version"],
        "prompt_version": packet["prompt_version"],
        "packet_id": packet["packet_id"],
        "input_sha256": packet["input_sha256"],
        "reviewer": {"kind": "low_cost_model", "model": "low-cost-model"},
        "reviewed_ids": targets,
        "changes": [],
    }
    return {
        "packet_dir": str(packet_dir),
        "packet_id": packet_id,
        **packet["metrics"],
        "request_chars": len((packet_dir / "request.json").read_text(encoding="utf-8")),
        "minimum_sparse_response_chars": len(
            json.dumps(minimum_response, ensure_ascii=False, separators=(",", ":"))
        ),
    }


def plan_lean_review_packets(
    output_dir: Path,
    catalog_path: Path,
    target_root: Path | None = None,
) -> dict:
    utterances = read_jsonl(output_dir / "utterances.jsonl")
    if not utterances:
        raise ValueError("cannot plan lean review for an empty transcript")
    manifest = read_json(output_dir / "manifest.json")
    target_root = target_root or output_dir / "lean-review"

    local_decisions = []
    model_indices = []
    for index, utterance in enumerate(utterances):
        previous = utterances[index - 1] if index else None
        following = utterances[index + 1] if index + 1 < len(utterances) else None
        risks = set(_risk_reasons(utterance, previous, following))
        if _local_safe(utterance, risks):
            decision = _default_decision(utterance, "local_safe_review_v2")
            decision["reason_codes"] = ["local_safe_ocr"]
            decision["evidence"] = [
                "ocr_confidence",
                *utterance.get("attribution_evidence", []),
            ]
            local_decisions.append(decision)
        else:
            model_indices.append(index)

    packets = []
    for packet_number, start in enumerate(range(0, len(model_indices), MAX_TARGETS_PER_PACKET), 1):
        indices = model_indices[start : start + MAX_TARGETS_PER_PACKET]
        packets.append(
            _build_packet(
                output_dir,
                manifest,
                utterances,
                indices,
                target_root / f"packet-{packet_number:03d}",
            )
        )

    write_jsonl(target_root / "local-decisions.jsonl", local_decisions)
    (target_root / "visual-review-instructions.md").write_text(
        LEAN_VISUAL_REVIEW_INSTRUCTIONS, encoding="utf-8"
    )
    plan = {
        "protocol_version": LEAN_REVIEW_PROTOCOL_VERSION,
        "prompt_version": LEAN_REVIEW_PROMPT_VERSION,
        "source_utterances": len(utterances),
        "local_auto_reviewed": len(local_decisions),
        "model_review_required": len(model_indices),
        "packet_count": len(packets),
        "first_pass_visual_count": 0,
        "request_chars": sum(packet["request_chars"] for packet in packets),
        "estimated_text_input_chars": sum(
            packet["request_chars"] + len(LEAN_REVIEW_INSTRUCTIONS) for packet in packets
        ),
        "minimum_sparse_response_chars": sum(
            packet["minimum_sparse_response_chars"] for packet in packets
        ),
        "character_ids": _catalog_character_ids(catalog_path),
        "packets": packets,
    }
    write_json(target_root / "plan.json", plan)
    return plan


def _validate_packet(packet: dict) -> None:
    _strict_keys(packet, _PACKET_KEYS, "lean packet")
    if packet["protocol_version"] != LEAN_REVIEW_PROTOCOL_VERSION:
        raise ValueError("unsupported lean protocol_version")
    if packet["prompt_version"] != LEAN_REVIEW_PROMPT_VERSION:
        raise ValueError("unsupported lean prompt_version")
    source = {
        "protocol_version": packet["protocol_version"],
        "prompt_version": packet["prompt_version"],
        "part_id": packet["part_id"],
        "title": packet["title"],
        "frame_root": packet["frame_root"],
        "targets": packet["targets"],
        "utterances": packet["utterances"],
    }
    if packet["input_sha256"] != _canonical_sha256(source):
        raise ValueError("lean packet input_sha256 is invalid")
    expected_id = (
        f"{packet['part_id']}-lean-{packet['targets'][0]}-{packet['targets'][-1]}-"
        f"{packet['input_sha256'][:12]}"
    )
    if packet["packet_id"] != expected_id:
        raise ValueError("lean packet_id is invalid")
    target_set = set(packet["targets"])
    if len(target_set) != len(packet["targets"]):
        raise ValueError("lean packet contains duplicate targets")
    row_ids = [row["id"] for row in packet["utterances"]]
    if len(row_ids) != len(set(row_ids)):
        raise ValueError("lean packet contains duplicate context rows")
    rows = {row["id"]: row for row in packet["utterances"]}
    if not target_set.issubset(rows):
        raise ValueError("lean packet target is missing from context")
    if packet["metrics"] != {
        "target_count": len(target_set),
        "context_count": len(rows) - len(target_set),
        "visual_count": 0,
    }:
        raise ValueError("lean packet metrics are invalid")


def validate_lean_review_response(packet_path: Path, response_path: Path) -> dict:
    if packet_path.parent.resolve() != response_path.parent.resolve():
        raise ValueError("packet and response must be in the same directory")
    if response_path.stat().st_size > MAX_RESPONSE_BYTES:
        raise ValueError("lean response exceeds size limit")
    packet = read_json(packet_path)
    response = read_json(response_path)
    _validate_packet(packet)
    _strict_keys(response, _RESPONSE_KEYS, "lean response")
    for key in ("protocol_version", "prompt_version", "packet_id", "input_sha256"):
        if response[key] != packet[key]:
            raise ValueError(f"lean response {key} mismatch")
    _strict_keys(response["reviewer"], _REVIEWER_KEYS, "lean reviewer")
    if response["reviewer"]["kind"] != "low_cost_model":
        raise ValueError("lean reviewer.kind must be low_cost_model")
    if (
        not isinstance(response["reviewer"]["model"], str)
        or not response["reviewer"]["model"].strip()
    ):
        raise ValueError("lean reviewer.model is required")

    targets = packet["targets"]
    if response["reviewed_ids"] != targets:
        raise ValueError("lean response reviewed_ids must exactly match targets in order")
    if not isinstance(response["changes"], list):
        raise ValueError("lean response changes must be a list")
    source_by_id = {row["id"]: row for row in packet["utterances"]}
    source_positions = {row["id"]: index for index, row in enumerate(packet["utterances"])}
    context_speaker_ids = {
        row["speaker"][1]
        for row in packet["utterances"]
        if row["speaker"][2] == "confirmed" and row["speaker"][1]
    }
    target_set = set(targets)
    changes = {}
    for change in response["changes"]:
        if not isinstance(change, dict):
            raise ValueError("each lean change must be an object")
        _strict_keys(change, _CHANGE_KEYS, f"lean change {change.get('utterance_id')}")
        utterance_id = change["utterance_id"]
        if utterance_id not in target_set:
            raise ValueError(f"lean change references non-target {utterance_id}")
        if utterance_id in changes:
            raise ValueError(f"duplicate lean change {utterance_id}")
        if change["action"] not in {"edit", "reject", "escalate"}:
            raise ValueError(f"invalid lean action for {utterance_id}")
        if change["content_kind"] not in _CONTENT_KINDS:
            raise ValueError(f"invalid lean content_kind for {utterance_id}")
        if change["speaker_status"] not in _SPEAKER_STATUSES:
            raise ValueError(f"invalid lean speaker_status for {utterance_id}")
        if change["speaker_label"] is not None and not isinstance(change["speaker_label"], str):
            raise ValueError(f"invalid lean speaker_label for {utterance_id}")
        if change["speaker_id"] is not None and not isinstance(change["speaker_id"], str):
            raise ValueError(f"invalid lean speaker_id for {utterance_id}")
        if change["speaker_status"] == "unknown" and change["speaker_id"] is not None:
            raise ValueError(f"unknown lean speaker must not have id for {utterance_id}")
        if not isinstance(change["reason_codes"], list) or not all(
            isinstance(item, str) and item and len(item) <= 100 for item in change["reason_codes"]
        ):
            raise ValueError(f"invalid lean reason_codes for {utterance_id}")
        source = source_by_id[utterance_id]
        source_speaker = source["speaker"]
        assigns_context_speaker = (
            change["speaker_id"] in context_speaker_ids
            and change["speaker_status"] in {"probable", "ambiguous"}
            and source_speaker[2] != "confirmed"
        )
        if change["speaker_id"] not in {None, source_speaker[1]} and not assigns_context_speaker:
            raise ValueError(
                f"lean text review cannot assign unsupported speaker for {utterance_id}"
            )
        if change["speaker_status"] == "confirmed" and (
            source_speaker[2] != "confirmed"
            or not source_speaker[1]
            or change["speaker_id"] != source_speaker[1]
        ):
            raise ValueError(f"lean text review cannot confirm speaker for {utterance_id}")
        if change["action"] == "edit":
            if not isinstance(change["reviewed_text"], str) or not normalized_text(
                change["reviewed_text"]
            ):
                raise ValueError(f"lean edited text is empty for {utterance_id}")
        elif change["reviewed_text"] is not None:
            raise ValueError(f"lean non-edit text must be null for {utterance_id}")
        changes[utterance_id] = change

    auto_decisions = []
    visual_queue = []
    model_name = response["reviewer"]["model"]
    for utterance_id in targets:
        source = source_by_id[utterance_id]
        source_row = {
            "utterance_id": utterance_id,
            "text": source["text"],
            "speaker_label": source["speaker"][0],
            "speaker_id": source["speaker"][1],
            "speaker_status": source["speaker"][2],
        }
        change = changes.get(utterance_id)
        if change is None:
            decision = _default_decision(source_row, f"{model_name}_lean_text_review")
            auto_decisions.append(decision)
            continue
        needs_visual = change["action"] in {"reject", "escalate"}
        if (
            change["action"] == "edit"
            and text_similarity(source["text"], change["reviewed_text"]) < 0.65
        ):
            needs_visual = True
        if needs_visual:
            source_index = source_positions[utterance_id]
            visual_queue.append(
                {
                    "utterance_id": utterance_id,
                    "source": source,
                    "text_context": packet["utterances"][
                        max(0, source_index - 2) : source_index + 3
                    ],
                    "frame_path": str(Path(packet["frame_root"]) / f"{utterance_id}.jpg"),
                    "proposed_change": change,
                }
            )
            continue
        auto_decisions.append(
            {
                "utterance_id": utterance_id,
                "decision": "approve",
                "content_kind": change["content_kind"],
                "reviewed_text": change["reviewed_text"],
                "speaker_label": change["speaker_label"],
                "speaker_id": change["speaker_id"],
                "speaker_status": change["speaker_status"],
                "confidence": "high",
                "reason_codes": change["reason_codes"],
                "evidence": ["text_sequence_review"],
                "reviewed_by": f"{model_name}_lean_text_review",
            }
        )

    write_jsonl(packet_path.parent / "auto-review-candidates.jsonl", auto_decisions)
    write_jsonl(packet_path.parent / "visual-queue.jsonl", visual_queue)
    summary = {
        "target_count": len(targets),
        "sparse_changes": len(changes),
        "auto_reviewed": len(auto_decisions),
        "visual_required": len(visual_queue),
        "response_chars": len(response_path.read_text(encoding="utf-8")),
    }
    write_json(packet_path.parent / "validation.json", summary)
    return summary


def _validate_high_decision(
    row: dict,
    character_ids: set[str],
) -> None:
    utterance_id = row.get("utterance_id")
    _strict_keys(row, _HIGH_REVIEW_KEYS, f"lean high decision {utterance_id}")
    if row["decision"] not in {"approve", "reject"}:
        raise ValueError(f"lean high review must resolve {utterance_id}")
    if row["content_kind"] not in _CONTENT_KINDS:
        raise ValueError(f"invalid lean high content_kind for {utterance_id}")
    if row["speaker_status"] not in _SPEAKER_STATUSES:
        raise ValueError(f"invalid lean high speaker_status for {utterance_id}")
    if row["speaker_label"] is not None and not isinstance(row["speaker_label"], str):
        raise ValueError(f"invalid lean high speaker_label for {utterance_id}")
    if row["speaker_id"] is not None and row["speaker_id"] not in character_ids:
        raise ValueError(f"unknown lean high speaker_id for {utterance_id}")
    if row["speaker_status"] == "confirmed" and row["speaker_id"] is None:
        raise ValueError(f"confirmed lean high speaker requires id for {utterance_id}")
    if row["speaker_status"] == "unknown" and row["speaker_id"] is not None:
        raise ValueError(f"unknown lean high speaker must not have id for {utterance_id}")
    if row["confidence"] != "high":
        raise ValueError(f"lean high confidence must be high for {utterance_id}")
    if not isinstance(row["reason_codes"], list) or not all(
        isinstance(item, str) and item and len(item) <= 100 for item in row["reason_codes"]
    ):
        raise ValueError(f"invalid lean high reason_codes for {utterance_id}")
    if not isinstance(row["evidence"], list) or "frame_inspected" not in row["evidence"]:
        raise ValueError(f"lean high review must inspect frame for {utterance_id}")
    if not isinstance(row["reviewed_by"], str) or not row["reviewed_by"].strip():
        raise ValueError(f"lean high reviewed_by is required for {utterance_id}")
    if row["decision"] == "approve":
        if not isinstance(row["reviewed_text"], str) or not normalized_text(row["reviewed_text"]):
            raise ValueError(f"lean high approved text is empty for {utterance_id}")
    else:
        if row["reviewed_text"] is not None:
            raise ValueError(f"lean high rejected text must be null for {utterance_id}")
        if not set(row["reason_codes"]).intersection(_SAFE_REJECT_REASONS):
            raise ValueError(f"unsafe lean high rejection for {utterance_id}")


def finalize_lean_review(output_dir: Path, high_review_paths: list[Path]) -> dict:
    """Merge validated local, sparse-text, and visual decisions into formal review."""
    root = output_dir / "lean-review"
    plan = read_json(root / "plan.json")
    source_rows = read_jsonl(output_dir / "utterances.jsonl")
    source_by_id = {row["utterance_id"]: row for row in source_rows}
    if len(source_by_id) != len(source_rows):
        raise ValueError("duplicate source utterance_id")

    resolved: dict[str, dict] = {}
    origins: dict[str, str] = {}
    local_rows = read_jsonl(root / "local-decisions.jsonl")
    for row in local_rows:
        utterance_id = row["utterance_id"]
        if utterance_id not in source_by_id:
            raise ValueError(f"unknown local lean decision {utterance_id}")
        if utterance_id in resolved:
            raise ValueError(f"duplicate local lean decision {utterance_id}")
        resolved[utterance_id] = row
        origins[utterance_id] = "local_safe_review_v2"

    visual_ids: set[str] = set()
    visual_frame_paths: dict[str, Path] = {}
    packet_target_ids: set[str] = set()
    for packet_summary in plan["packets"]:
        packet_dir = Path(packet_summary["packet_dir"])
        validate_lean_review_response(packet_dir / "request.json", packet_dir / "response.json")
        packet = read_json(packet_dir / "request.json")
        duplicate_targets = packet_target_ids.intersection(packet["targets"])
        if duplicate_targets:
            raise ValueError(f"duplicate lean packet targets {sorted(duplicate_targets)}")
        packet_target_ids.update(packet["targets"])
        for row in read_jsonl(packet_dir / "auto-review-candidates.jsonl"):
            utterance_id = row["utterance_id"]
            if utterance_id in resolved:
                raise ValueError(f"duplicate lean decision {utterance_id}")
            resolved[utterance_id] = row
            origins[utterance_id] = "lean_text_review_v2"
        packet_visual_rows = read_jsonl(packet_dir / "visual-queue.jsonl")
        packet_visual_ids = {row["utterance_id"] for row in packet_visual_rows}
        duplicate_visual = visual_ids.intersection(packet_visual_ids)
        if duplicate_visual:
            raise ValueError(f"duplicate lean visual targets {sorted(duplicate_visual)}")
        visual_ids.update(packet_visual_ids)
        visual_frame_paths.update(
            {row["utterance_id"]: Path(row["frame_path"]) for row in packet_visual_rows}
        )

    high_by_id: dict[str, dict] = {}
    character_ids = set(plan["character_ids"])
    for path in high_review_paths:
        document = read_json(path)
        _strict_keys(document, {"reviewer", "decisions"}, f"lean high review {path}")
        _strict_keys(document["reviewer"], _REVIEWER_KEYS, f"lean high reviewer {path}")
        if document["reviewer"]["kind"] != "high_capability_model":
            raise ValueError("lean high reviewer.kind must be high_capability_model")
        if (
            not isinstance(document["reviewer"]["model"], str)
            or not document["reviewer"]["model"].strip()
        ):
            raise ValueError("lean high reviewer.model is required")
        if not isinstance(document["decisions"], list):
            raise ValueError("lean high decisions must be a list")
        for row in document["decisions"]:
            utterance_id = row.get("utterance_id")
            if utterance_id not in source_by_id:
                raise ValueError(f"unknown lean high utterance {utterance_id}")
            if utterance_id in high_by_id:
                raise ValueError(f"duplicate lean high decision {utterance_id}")
            _validate_high_decision(row, character_ids)
            high_by_id[utterance_id] = row

    if set(high_by_id) != visual_ids:
        missing = sorted(visual_ids - set(high_by_id))
        extra = sorted(set(high_by_id) - visual_ids)
        raise ValueError(f"lean high review coverage mismatch; missing={missing}, extra={extra}")
    for utterance_id, frame_path in visual_frame_paths.items():
        expected_path = (output_dir / "review-full-frames" / f"{utterance_id}.jpg").resolve()
        if frame_path.resolve() != expected_path or not expected_path.is_file():
            raise ValueError(f"lean visual evidence is missing for {utterance_id}")
    for utterance_id, row in high_by_id.items():
        if utterance_id in resolved:
            raise ValueError(f"duplicate final lean decision {utterance_id}")
        resolved[utterance_id] = row
        origins[utterance_id] = "lean_visual_review_v2"

    if set(resolved) != set(source_by_id):
        missing = sorted(set(source_by_id) - set(resolved))
        extra = sorted(set(resolved) - set(source_by_id))
        raise ValueError(f"lean final coverage mismatch; missing={missing}, extra={extra}")

    formal_decisions = []
    transcript = []
    for source in source_rows:
        utterance_id = source["utterance_id"]
        decision = resolved[utterance_id]
        approved = decision["decision"] == "approve"
        formal_decisions.append(
            {
                "review_schema_version": "1.0",
                "utterance_id": utterance_id,
                "decision": "approved" if approved else "rejected",
                "reason": origins[utterance_id],
                "content_kind": decision["content_kind"],
                "original_text": source["text"],
                "reviewed_text": decision["reviewed_text"],
                "speaker_label": decision["speaker_label"],
                "speaker_id": decision["speaker_id"],
                "speaker_status": decision["speaker_status"],
                "attribution_evidence": decision["evidence"],
                "reviewed_by": decision["reviewed_by"],
                "source_candidates": source.get("source_candidates", []),
            }
        )
        if approved:
            transcript.append(
                {
                    "schema_version": "1.0",
                    "reviewed_utterance_id": utterance_id,
                    "source_utterance_ids": [utterance_id],
                    "start_ms": source["start_ms"],
                    "end_ms": source["end_ms"],
                    "start_timestamp": source["start_timestamp"],
                    "end_timestamp": source["end_timestamp"],
                    "content_kind": decision["content_kind"],
                    "text": decision["reviewed_text"],
                    "speaker_label": decision["speaker_label"],
                    "speaker_id": decision["speaker_id"],
                    "speaker_status": decision["speaker_status"],
                    "attribution_evidence": decision["evidence"],
                    "review_status": "approved",
                    "source_candidates": source.get("source_candidates", []),
                }
            )

    write_jsonl(output_dir / "review-decisions.jsonl", formal_decisions)
    write_jsonl(output_dir / "reviewed-transcript.jsonl", transcript)
    local_count = len(local_rows)
    return {
        "source_utterances": len(source_rows),
        "approved": len(transcript),
        "rejected": len(source_rows) - len(transcript),
        "local_reviewed": local_count,
        "text_model_reviewed": len(resolved) - len(high_by_id) - local_count,
        "visual_reviewed": len(high_by_id),
    }


def benchmark_lean_review_plan(
    output_dir: Path,
    gold_decisions_path: Path,
    target_root: Path | None = None,
) -> dict:
    target_root = target_root or output_dir / "lean-review"
    plan = read_json(target_root / "plan.json")
    local = read_jsonl(target_root / "local-decisions.jsonl")
    source = {row["utterance_id"]: row for row in read_jsonl(output_dir / "utterances.jsonl")}
    gold = {row["utterance_id"]: row for row in read_jsonl(gold_decisions_path)}
    if set(source) != set(gold):
        raise ValueError("lean benchmark gold coverage mismatch")

    local_decision_correct = 0
    local_text_correct = 0
    local_speaker_exact = 0
    for decision in local:
        expected = gold[decision["utterance_id"]]
        approved = expected["decision"] == "approved"
        local_decision_correct += approved
        local_text_correct += (
            approved
            and text_similarity(decision["reviewed_text"], expected.get("reviewed_text") or "")
            >= 0.9
        )
        local_speaker_exact += decision.get("speaker_id") == expected.get(
            "speaker_id"
        ) and decision.get("speaker_status") == expected.get("speaker_status")

    local_ids = {row["utterance_id"] for row in local}
    gold_content_or_speaker_id_changes = 0
    gold_speaker_status_only_changes = 0
    for utterance_id, row in source.items():
        if utterance_id in local_ids:
            continue
        expected = gold[utterance_id]
        content_or_speaker_id_changed = (
            expected["decision"] != "approved"
            or text_similarity(row["text"], expected.get("reviewed_text") or "") < 0.9
            or row.get("speaker_id") != expected.get("speaker_id")
        )
        if content_or_speaker_id_changed:
            gold_content_or_speaker_id_changes += 1
        elif row.get("speaker_status") != expected.get("speaker_status"):
            gold_speaker_status_only_changes += 1

    baseline_path = output_dir / "low-cost-review" / "plan.json"
    baseline = read_json(baseline_path) if baseline_path.exists() else None
    result = {
        "source_utterances": len(source),
        "local_auto_reviewed": len(local),
        "local_decision_precision": round(local_decision_correct / len(local), 4)
        if local
        else None,
        "local_text_accuracy_at_least_0_9": round(local_text_correct / len(local), 4)
        if local
        else None,
        "local_speaker_exact_accuracy": round(local_speaker_exact / len(local), 4)
        if local
        else None,
        "model_review_required": plan["model_review_required"],
        "model_packet_count": plan["packet_count"],
        "first_pass_visual_count": 0,
        "gold_content_or_speaker_id_changes": gold_content_or_speaker_id_changes,
        "gold_speaker_status_only_changes": gold_speaker_status_only_changes,
        "request_chars": plan["request_chars"],
        "estimated_text_input_chars": plan["estimated_text_input_chars"],
        "minimum_sparse_response_chars": plan["minimum_sparse_response_chars"],
        "baseline": (
            {
                "model_review_required": baseline["utterance_count"],
                "packet_count": baseline["packet_count"],
                "visual_count": baseline["visual_review_count"],
                "request_chars": sum(
                    len((Path(packet["packet_dir"]) / "request.json").read_text(encoding="utf-8"))
                    for packet in baseline["packets"]
                ),
                "estimated_text_input_chars": sum(
                    len((Path(packet["packet_dir"]) / "request.json").read_text(encoding="utf-8"))
                    + len(LOW_COST_REVIEW_INSTRUCTIONS)
                    for packet in baseline["packets"]
                ),
                "response_chars": (
                    sum(
                        len(
                            (Path(packet["packet_dir"]) / "response.json").read_text(
                                encoding="utf-8"
                            )
                        )
                        for packet in baseline["packets"]
                    )
                    if all(
                        (Path(packet["packet_dir"]) / "response.json").exists()
                        for packet in baseline["packets"]
                    )
                    else None
                ),
            }
            if baseline
            else None
        ),
    }
    write_json(target_root / "benchmark.json", result)
    return result
