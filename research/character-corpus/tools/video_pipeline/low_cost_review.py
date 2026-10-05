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

LOW_COST_REVIEW_PROTOCOL_VERSION = "1.0"
LOW_COST_REVIEW_PROMPT_VERSION = "1.2"
MAX_PACKET_UTTERANCES = 40
MAX_PACKET_VISUALS = 20
MAX_RESPONSE_BYTES = 1_000_000

_PACKET_KEYS = {
    "protocol_version",
    "prompt_version",
    "packet_id",
    "input_sha256",
    "part_id",
    "title",
    "range",
    "characters",
    "utterances",
    "metrics",
}
_RESPONSE_KEYS = {
    "protocol_version",
    "prompt_version",
    "packet_id",
    "input_sha256",
    "reviewer",
    "decisions",
}
_REVIEWER_KEYS = {"kind", "model"}
_DECISION_KEYS = {
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
}
_HIGH_REVIEW_DECISION_KEYS = _DECISION_KEYS | {"reviewed_by"}
_DECISIONS = {"approve", "reject", "escalate"}
_CONTENT_KINDS = {
    "dialogue",
    "system_or_broadcast",
    "world_document_text",
    "gameplay_ui",
    "background_text",
    "unknown",
}
_SPEAKER_STATUSES = {"confirmed", "probable", "ambiguous", "unknown"}
_CONFIDENCES = {"high", "medium", "low"}
_SAFE_REJECT_REASONS = {
    "partial_duplicate",
    "false_positive_background_text",
    "gameplay_ui",
    "ocr_fragment",
}


LOW_COST_REVIEW_INSTRUCTIONS = """# 低成本剧情审核协议 1.0

只读取 `request.json` 及其中明确列出的 `frame_path`。不要读取同目录中的
`review-decisions.jsonl`、`reviewed-transcript.jsonl` 或正式 Canon 文件。

逐条输出一个决定：

- `approve`：确定是有效剧情内容；修正 OCR 文本，但不能补写画面和上下文没有的内容。
- `reject`：确定是重复中间态、背景误识别、玩法 UI 或无意义 OCR 残片。
- `escalate`：说话者、文本或内容类型无法可靠判断。低模型宁可升级，不要猜测。

规则：

1. 只检查 `visual_required=true` 的图片；其余条目根据文本、明确姓名框和相邻顺序审核。
2. 原数据已由明确姓名框确认的说话者可以保持 `confirmed`，不得改成另一个 confirmed 人物。
3. 没有明确姓名框时，新推定说话者最高只能是 `probable`；证据不足使用 `unknown` 或升级。
4. `high` 只用于有直接证据且可自动执行的决定；任何犹豫使用 `medium/low` 并升级。
5. 查看图片后在 `evidence` 中加入 `frame_inspected`；使用相邻语境时加入 `context_sequence`。
6. 输出必须是一个 JSON 对象，严格使用响应模板字段，不要 Markdown 或额外说明。

枚举必须严格使用以下值，不得自创近义词：

- `content_kind`：`dialogue`、`system_or_broadcast`、`world_document_text`、
  `gameplay_ui`、`background_text`、`unknown`。内心独白、语气声和普通人物台词都归 `dialogue`。
- `speaker_status`：`confirmed`、`probable`、`ambiguous`、`unknown`。
- `confidence`：`high`、`medium`、`low`。
- 安全拒绝原因：`partial_duplicate`、`false_positive_background_text`、
  `gameplay_ui`、`ocr_fragment`。若不符合这些原因，应使用 `escalate`。

响应顶层字段：`protocol_version`、`prompt_version`、`packet_id`、`input_sha256`、
`reviewer`、`decisions`。每条 decision 必须完整包含 request 中规定的字段，并覆盖所有
utterance_id。复制 request 的版本、packet_id 和 input_sha256。

严格按以下形状输出；不得把字段改名为 action、corrected_text、reason 等近义词：

```json
{
  "protocol_version": "1.0",
  "prompt_version": "1.2",
  "packet_id": "复制 request.packet_id",
  "input_sha256": "复制 request.input_sha256",
  "reviewer": {"kind": "low_cost_model", "model": "实际模型名"},
  "decisions": [
    {
      "utterance_id": "复制 utterance_id",
      "decision": "approve",
      "content_kind": "dialogue",
      "reviewed_text": "审核后的完整文本；reject/escalate 时必须为 null",
      "speaker_label": null,
      "speaker_id": null,
      "speaker_status": "unknown",
      "confidence": "high",
      "reason_codes": ["简短英文原因码"],
      "evidence": ["frame_inspected"]
    }
  ]
}
```

每条 decision 的键必须恰好是示例中的十个键；`reason_codes` 与 `evidence` 必须是字符串
数组。不要输出注释、代码围栏或解释。
"""


def _strict_keys(value: dict, expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"{label} fields mismatch; missing={missing}, unknown={unknown}")


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_compact_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _catalog_characters(catalog_path: Path) -> list[dict]:
    catalog = read_json(catalog_path)
    result = []
    for row in catalog:
        names = row.get("names", {})
        display_name = names.get("zh") or names.get("en") or row["character_id"]
        result.append({"character_id": row["character_id"], "display_name": display_name})
    return result


def _risk_reasons(utterance: dict, previous: dict | None, following: dict | None) -> list[str]:
    reasons = []
    text = utterance.get("text", "")
    if utterance.get("speaker_status") != "confirmed" or not utterance.get("speaker_id"):
        reasons.append("speaker_unconfirmed")
    if utterance.get("confidence", 0) < 0.95:
        reasons.append("ocr_below_fast_lane")
    if len(normalized_text(text)) < 6:
        reasons.append("short_text")
    tail = re.split(r"[，,：:；;]", text)[-1]
    if len(normalized_text(text)) >= 8 and 0 < len(normalized_text(tail)) <= 2:
        reasons.append("possible_incomplete_clause")
    if re.search(r"[\u3400-\u9fff]\s+[\u3400-\u9fff]", text):
        reasons.append("cjk_internal_whitespace")
    for adjacent in (previous, following):
        if adjacent and text_similarity(utterance["text"], adjacent["text"]) >= 0.5:
            reasons.append("possible_adjacent_duplicate")
            break
    return reasons


def build_low_cost_review_packet(
    output_dir: Path,
    catalog_path: Path,
    start_ms: int,
    end_ms: int,
    target_dir: Path | None = None,
) -> dict:
    if start_ms < 0 or end_ms <= start_ms:
        raise ValueError("review range must satisfy 0 <= start_ms < end_ms")
    manifest = read_json(output_dir / "manifest.json")
    utterances = read_jsonl(output_dir / "utterances.jsonl")
    selected = [
        row
        for row in utterances
        if row["end_ms"] >= start_ms and row["start_ms"] < end_ms
    ]
    if not selected:
        raise ValueError("review range does not contain any utterances")

    compact = []
    visual_count = 0
    for index, utterance in enumerate(selected):
        previous = selected[index - 1] if index else None
        following = selected[index + 1] if index + 1 < len(selected) else None
        risks = _risk_reasons(utterance, previous, following)
        visual_required = bool(risks)
        visual_count += visual_required
        compact.append(
            {
                "utterance_id": utterance["utterance_id"],
                "start_ms": utterance["start_ms"],
                "end_ms": utterance["end_ms"],
                "timestamp": (
                    f"{utterance['start_timestamp']}–{utterance['end_timestamp']}"
                ),
                "text": utterance["text"],
                "ocr_confidence": utterance["confidence"],
                "speaker_label": utterance.get("speaker_label"),
                "speaker_id": utterance.get("speaker_id"),
                "speaker_status": utterance["speaker_status"],
                "attribution_evidence": utterance.get("attribution_evidence", []),
                "risk_reasons": risks,
                "visual_required": visual_required,
                "frame_path": (
                    str(
                        (
                            output_dir
                            / "review-full-frames"
                            / f"{utterance['utterance_id']}.jpg"
                        ).resolve()
                    )
                    if visual_required
                    else None
                ),
            }
        )
    if len(compact) > MAX_PACKET_UTTERANCES:
        raise ValueError(
            f"review packet exceeds {MAX_PACKET_UTTERANCES} utterances; split the time range"
        )
    if visual_count > MAX_PACKET_VISUALS:
        raise ValueError(
            f"review packet exceeds {MAX_PACKET_VISUALS} visual items; split the time range"
        )

    characters = _catalog_characters(catalog_path)
    source = {
        "protocol_version": LOW_COST_REVIEW_PROTOCOL_VERSION,
        "prompt_version": LOW_COST_REVIEW_PROMPT_VERSION,
        "part_id": manifest["part_id"],
        "title": manifest.get("title", ""),
        "range": {"start_ms": start_ms, "end_ms": end_ms},
        "characters": characters,
        "utterances": compact,
    }
    input_sha256 = _canonical_sha256(source)
    packet_id = (
        f"{manifest['part_id']}-{start_ms:08d}-{end_ms:08d}-{input_sha256[:12]}"
    )
    packet = {
        "protocol_version": LOW_COST_REVIEW_PROTOCOL_VERSION,
        "prompt_version": LOW_COST_REVIEW_PROMPT_VERSION,
        "packet_id": packet_id,
        "input_sha256": input_sha256,
        "part_id": manifest["part_id"],
        "title": manifest.get("title", ""),
        "range": {"start_ms": start_ms, "end_ms": end_ms},
        "characters": characters,
        "utterances": compact,
        "metrics": {
            "utterance_count": len(compact),
            "visual_review_count": visual_count,
            "text_only_count": len(compact) - visual_count,
        },
    }
    _strict_keys(packet, _PACKET_KEYS, "packet")
    target_dir = target_dir or output_dir / "low-cost-review" / packet_id
    _write_compact_json(target_dir / "request.json", packet)
    (target_dir / "instructions.md").write_text(
        LOW_COST_REVIEW_INSTRUCTIONS, encoding="utf-8"
    )
    return {"packet_dir": str(target_dir), **packet["metrics"], "packet_id": packet_id}


def plan_low_cost_review_packets(
    output_dir: Path,
    catalog_path: Path,
    target_root: Path | None = None,
) -> dict:
    """Split a full staging transcript into bounded low-cost review packets."""
    utterances = read_jsonl(output_dir / "utterances.jsonl")
    if not utterances:
        raise ValueError("cannot plan low-cost review for an empty transcript")

    batches: list[list[dict]] = []
    current: list[dict] = []
    current_visuals = 0
    for index, utterance in enumerate(utterances):
        previous = utterances[index - 1] if index else None
        following = utterances[index + 1] if index + 1 < len(utterances) else None
        visual_required = bool(_risk_reasons(utterance, previous, following))
        would_overflow = current and (
            len(current) + 1 > MAX_PACKET_UTTERANCES
            or current_visuals + int(visual_required) > MAX_PACKET_VISUALS
        )
        if would_overflow:
            batches.append(current)
            current = []
            current_visuals = 0
        current.append(utterance)
        current_visuals += int(visual_required)
    if current:
        batches.append(current)

    target_root = target_root or output_dir / "low-cost-review"
    packets = []
    for index, batch in enumerate(batches):
        start_ms = batch[0]["start_ms"]
        if index + 1 < len(batches):
            end_ms = batches[index + 1][0]["start_ms"]
        else:
            end_ms = batch[-1]["end_ms"] + 1
        packet_dir = target_root / f"packet-{index + 1:03d}"
        packets.append(
            build_low_cost_review_packet(
                output_dir,
                catalog_path,
                start_ms,
                end_ms,
                packet_dir,
            )
        )

    plan = {
        "protocol_version": LOW_COST_REVIEW_PROTOCOL_VERSION,
        "prompt_version": LOW_COST_REVIEW_PROMPT_VERSION,
        "packet_count": len(packets),
        "utterance_count": sum(row["utterance_count"] for row in packets),
        "visual_review_count": sum(row["visual_review_count"] for row in packets),
        "text_only_count": sum(row["text_only_count"] for row in packets),
        "packets": packets,
    }
    write_json(target_root / "plan.json", plan)
    return plan


def _validate_decision(
    decision: dict,
    source: dict,
    character_ids: set[str],
    *,
    allow_speaker_upgrade: bool = False,
) -> None:
    _strict_keys(decision, _DECISION_KEYS, f"decision {decision.get('utterance_id')}")
    if decision["decision"] not in _DECISIONS:
        raise ValueError(f"invalid decision for {decision['utterance_id']}")
    if decision["content_kind"] not in _CONTENT_KINDS:
        raise ValueError(f"invalid content_kind for {decision['utterance_id']}")
    if decision["speaker_status"] not in _SPEAKER_STATUSES:
        raise ValueError(f"invalid speaker_status for {decision['utterance_id']}")
    if decision["confidence"] not in _CONFIDENCES:
        raise ValueError(f"invalid confidence for {decision['utterance_id']}")
    for field in ("speaker_label", "speaker_id"):
        value = decision[field]
        if value is not None and (not isinstance(value, str) or not value or len(value) > 100):
            raise ValueError(f"invalid {field} for {decision['utterance_id']}")
    if decision["speaker_id"] is not None and decision["speaker_id"] not in character_ids:
        raise ValueError(f"unknown speaker_id for {decision['utterance_id']}")
    if not isinstance(decision["reason_codes"], list) or not all(
        isinstance(item, str) and item and len(item) <= 100
        for item in decision["reason_codes"]
    ) or len(decision["reason_codes"]) > 8:
        raise ValueError(f"invalid reason_codes for {decision['utterance_id']}")
    if not isinstance(decision["evidence"], list) or not all(
        isinstance(item, str) and item and len(item) <= 100
        for item in decision["evidence"]
    ) or len(decision["evidence"]) > 8:
        raise ValueError(f"invalid evidence for {decision['utterance_id']}")
    if decision["decision"] == "approve":
        if not isinstance(decision["reviewed_text"], str) or not normalized_text(
            decision["reviewed_text"]
        ):
            raise ValueError(f"approved text is empty for {decision['utterance_id']}")
        if len(decision["reviewed_text"]) > 1000:
            raise ValueError(f"approved text is too long for {decision['utterance_id']}")
    elif decision["reviewed_text"] is not None:
        raise ValueError(f"non-approved text must be null for {decision['utterance_id']}")

    source_confirmed = source["speaker_status"] == "confirmed" and source.get("speaker_id")
    if decision["speaker_status"] == "confirmed" and not allow_speaker_upgrade:
        if not source_confirmed:
            raise ValueError(
                f"low-cost reviewer cannot upgrade speaker to confirmed for "
                f"{decision['utterance_id']}"
            )
        if decision.get("speaker_id") != source.get("speaker_id"):
            raise ValueError(
                f"low-cost reviewer cannot replace confirmed speaker for "
                f"{decision['utterance_id']}"
            )


def _auto_eligibility(decision: dict, source: dict) -> tuple[bool, list[str]]:
    blockers = []
    if decision["decision"] == "escalate":
        blockers.append("model_requested_escalation")
    if decision["confidence"] != "high":
        blockers.append("model_confidence_not_high")
    if source["visual_required"] and "frame_inspected" not in decision["evidence"]:
        blockers.append("required_frame_not_inspected")
    if decision["decision"] == "approve":
        if text_similarity(source["text"], decision["reviewed_text"]) < 0.65:
            blockers.append("large_text_rewrite")
        speaker_changed = (
            decision.get("speaker_id") != source.get("speaker_id")
            or decision["speaker_status"] != source["speaker_status"]
        )
        conservative_unresolved_downgrade = (
            source["speaker_status"] == "confirmed"
            and not source.get("speaker_id")
            and decision.get("speaker_id") is None
            and decision.get("speaker_label") == source.get("speaker_label")
            and decision["speaker_status"] == "unknown"
        )
        if speaker_changed and not conservative_unresolved_downgrade and not {
            "frame_inspected",
            "context_sequence",
        }.issubset(decision["evidence"]):
            blockers.append("speaker_change_without_two_sources")
    if decision["decision"] == "reject":
        if not set(decision["reason_codes"]).intersection(_SAFE_REJECT_REASONS):
            blockers.append("unsafe_reject_reason")
        if "frame_inspected" not in decision["evidence"]:
            blockers.append("reject_without_frame")
    return not blockers, blockers


def validate_low_cost_review_response(packet_path: Path, response_path: Path) -> dict:
    if packet_path.parent.resolve() != response_path.parent.resolve():
        raise ValueError("packet and response must be in the same directory")
    if response_path.stat().st_size > MAX_RESPONSE_BYTES:
        raise ValueError("low-cost response exceeds size limit")
    packet = read_json(packet_path)
    response = read_json(response_path)
    if not isinstance(packet, dict) or not isinstance(response, dict):
        raise ValueError("packet and response must contain JSON objects")
    _strict_keys(packet, _PACKET_KEYS, "packet")
    source = {
        "protocol_version": packet["protocol_version"],
        "prompt_version": packet["prompt_version"],
        "part_id": packet["part_id"],
        "title": packet["title"],
        "range": packet["range"],
        "characters": packet["characters"],
        "utterances": packet["utterances"],
    }
    if packet["input_sha256"] != _canonical_sha256(source):
        raise ValueError("packet input_sha256 is invalid")
    expected_packet_id = (
        f"{packet['part_id']}-{packet['range']['start_ms']:08d}-"
        f"{packet['range']['end_ms']:08d}-{packet['input_sha256'][:12]}"
    )
    if packet["packet_id"] != expected_packet_id:
        raise ValueError("packet_id is invalid")
    utterance_count = len(packet["utterances"])
    visual_count = sum(bool(row["visual_required"]) for row in packet["utterances"])
    if packet["metrics"] != {
        "utterance_count": utterance_count,
        "visual_review_count": visual_count,
        "text_only_count": utterance_count - visual_count,
    }:
        raise ValueError("packet metrics are invalid")
    _strict_keys(response, _RESPONSE_KEYS, "response")
    for key in ("protocol_version", "prompt_version", "packet_id", "input_sha256"):
        if response[key] != packet[key]:
            raise ValueError(f"response {key} does not match packet")
    _strict_keys(response["reviewer"], _REVIEWER_KEYS, "reviewer")
    if response["reviewer"]["kind"] != "low_cost_model":
        raise ValueError("reviewer.kind must be low_cost_model")
    if not isinstance(response["reviewer"]["model"], str) or not response["reviewer"][
        "model"
    ].strip():
        raise ValueError("reviewer.model must be non-empty")

    if not isinstance(response["decisions"], list):
        raise ValueError("response.decisions must be a list")
    if not all(isinstance(row, dict) for row in response["decisions"]):
        raise ValueError("each low-cost decision must be an object")
    source_by_id = {row["utterance_id"]: row for row in packet["utterances"]}
    character_ids = {row["character_id"] for row in packet["characters"]}
    decision_ids = [row.get("utterance_id") for row in response["decisions"]]
    if len(decision_ids) != len(set(decision_ids)):
        raise ValueError("duplicate low-cost decision utterance_id")
    if set(decision_ids) != set(source_by_id):
        missing = sorted(set(source_by_id) - set(decision_ids))
        extra = sorted(set(decision_ids) - set(source_by_id))
        raise ValueError(f"low-cost coverage mismatch; missing={missing}, extra={extra}")

    auto_rows = []
    escalations = []
    for decision in response["decisions"]:
        source = source_by_id[decision["utterance_id"]]
        _validate_decision(decision, source, character_ids)
        eligible, blockers = _auto_eligibility(decision, source)
        enriched = {**decision, "auto_eligible": eligible, "guard_blockers": blockers}
        if eligible:
            auto_rows.append(enriched)
        else:
            escalations.append(enriched)

    target_dir = response_path.parent
    write_jsonl(target_dir / "auto-review-candidates.jsonl", auto_rows)
    write_jsonl(target_dir / "escalation-queue.jsonl", escalations)
    summary = {
        "packet_id": packet["packet_id"],
        "utterances": len(source_by_id),
        "auto_eligible": len(auto_rows),
        "escalated": len(escalations),
        "auto_coverage": round(len(auto_rows) / len(source_by_id), 4),
        "visual_review_count": packet["metrics"]["visual_review_count"],
        "formal_review_files_unchanged": True,
    }
    write_json(target_dir / "validation.json", summary)
    return summary


def finalize_low_cost_review(
    output_dir: Path,
    high_review_paths: list[Path],
) -> dict:
    """Combine validated automatic decisions and bounded escalation reviews."""
    plan = read_json(output_dir / "low-cost-review" / "plan.json")
    source_rows = read_jsonl(output_dir / "utterances.jsonl")
    source_by_id = {row["utterance_id"]: row for row in source_rows}
    auto_by_id: dict[str, dict] = {}
    escalation_ids: set[str] = set()
    packet_model_by_id: dict[str, str] = {}
    character_ids: set[str] = set()

    for packet_summary in plan["packets"]:
        packet_dir = Path(packet_summary["packet_dir"])
        packet_path = packet_dir / "request.json"
        response_path = packet_dir / "response.json"
        validate_low_cost_review_response(packet_path, response_path)
        packet = read_json(packet_path)
        character_ids.update(row["character_id"] for row in packet["characters"])
        response = read_json(response_path)
        model = response["reviewer"]["model"]
        for row in read_jsonl(packet_dir / "auto-review-candidates.jsonl"):
            auto_by_id[row["utterance_id"]] = row
            packet_model_by_id[row["utterance_id"]] = model
        escalation_ids.update(
            row["utterance_id"]
            for row in read_jsonl(packet_dir / "escalation-queue.jsonl")
        )

    high_by_id: dict[str, dict] = {}
    for path in high_review_paths:
        document = read_json(path)
        _strict_keys(document, {"reviewer", "decisions"}, f"high review {path}")
        _strict_keys(document["reviewer"], _REVIEWER_KEYS, f"high reviewer {path}")
        if document["reviewer"]["kind"] != "high_capability_model":
            raise ValueError("high reviewer.kind must be high_capability_model")
        if not isinstance(document["decisions"], list):
            raise ValueError("high review decisions must be a list")
        for row in document["decisions"]:
            _strict_keys(
                row,
                _HIGH_REVIEW_DECISION_KEYS,
                f"high decision {row.get('utterance_id')}",
            )
            utterance_id = row["utterance_id"]
            if utterance_id in high_by_id:
                raise ValueError(f"duplicate high review decision {utterance_id}")
            if utterance_id not in source_by_id:
                raise ValueError(f"unknown high review utterance {utterance_id}")
            if row["decision"] not in {"approve", "reject"}:
                raise ValueError(f"high review must resolve {utterance_id}")
            if not isinstance(row["reviewed_by"], str) or not row["reviewed_by"].strip():
                raise ValueError(f"high review reviewed_by is required for {utterance_id}")
            _validate_decision(
                {key: row[key] for key in _DECISION_KEYS},
                source_by_id[utterance_id],
                character_ids,
                allow_speaker_upgrade=True,
            )
            if row["confidence"] != "high":
                raise ValueError(f"high review confidence must be high for {utterance_id}")
            high_by_id[utterance_id] = row

    if set(high_by_id) != escalation_ids:
        missing = sorted(escalation_ids - set(high_by_id))
        extra = sorted(set(high_by_id) - escalation_ids)
        raise ValueError(f"high review coverage mismatch; missing={missing}, extra={extra}")

    formal_decisions = []
    transcript = []
    for source in source_rows:
        utterance_id = source["utterance_id"]
        is_high_review = utterance_id in high_by_id
        decision = high_by_id.get(utterance_id) or auto_by_id.get(utterance_id)
        if decision is None:
            raise ValueError(f"missing final review decision for {utterance_id}")
        approved = decision["decision"] == "approve"
        reviewed_by = (
            decision["reviewed_by"]
            if is_high_review
            else f"{packet_model_by_id[utterance_id]}_low_cost_review"
        )
        formal_decisions.append(
            {
                "review_schema_version": "1.0",
                "utterance_id": utterance_id,
                "decision": "approved" if approved else "rejected",
                "reason": (
                    "high_capability_escalation_review"
                    if is_high_review
                    else "low_cost_review_auto"
                ),
                "content_kind": decision["content_kind"],
                "original_text": source["text"],
                "reviewed_text": decision["reviewed_text"],
                "speaker_label": decision["speaker_label"],
                "speaker_id": decision["speaker_id"],
                "speaker_status": decision["speaker_status"],
                "attribution_evidence": decision["evidence"],
                "reviewed_by": reviewed_by,
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
    return {
        "source_utterances": len(source_rows),
        "approved": len(transcript),
        "rejected": len(source_rows) - len(transcript),
        "auto_reviewed": len(auto_by_id),
        "high_reviewed": len(high_by_id),
    }


def _ratio(matches: int, total: int) -> float | None:
    return round(matches / total, 4) if total else None


def benchmark_low_cost_review(
    packet_path: Path,
    response_path: Path,
    gold_decisions_path: Path,
) -> dict:
    validation = validate_low_cost_review_response(packet_path, response_path)
    packet = read_json(packet_path)
    response = read_json(response_path)
    gold_by_id = {
        row["utterance_id"]: row for row in read_jsonl(gold_decisions_path)
    }
    source_by_id = {row["utterance_id"]: row for row in packet["utterances"]}
    decisions = response["decisions"]
    missing_gold = sorted(set(source_by_id) - set(gold_by_id))
    if missing_gold:
        raise ValueError(f"gold decisions missing packet utterances: {missing_gold}")

    resolved = [row for row in decisions if row["decision"] != "escalate"]
    decision_matches = sum(
        row["decision"]
        == ("approve" if gold_by_id[row["utterance_id"]]["decision"] == "approved" else "reject")
        for row in resolved
    )
    auto_rows = read_jsonl(response_path.parent / "auto-review-candidates.jsonl")
    auto_matches = sum(
        row["decision"]
        == ("approve" if gold_by_id[row["utterance_id"]]["decision"] == "approved" else "reject")
        for row in auto_rows
    )
    approved_matches = [
        row
        for row in resolved
        if row["decision"] == "approve"
        and gold_by_id[row["utterance_id"]]["decision"] == "approved"
    ]
    speaker_matches = sum(
        row.get("speaker_id") == gold_by_id[row["utterance_id"]].get("speaker_id")
        and row["speaker_status"]
        == gold_by_id[row["utterance_id"]].get("speaker_status")
        for row in approved_matches
    )
    text_matches = sum(
        text_similarity(
            row["reviewed_text"],
            gold_by_id[row["utterance_id"]].get("reviewed_text") or "",
        )
        >= 0.9
        for row in approved_matches
    )
    auto_approved_matches = [
        row
        for row in auto_rows
        if row["decision"] == "approve"
        and gold_by_id[row["utterance_id"]]["decision"] == "approved"
    ]
    auto_speaker_matches = sum(
        row.get("speaker_id") == gold_by_id[row["utterance_id"]].get("speaker_id")
        and row["speaker_status"]
        == gold_by_id[row["utterance_id"]].get("speaker_status")
        for row in auto_approved_matches
    )
    auto_text_matches = sum(
        text_similarity(
            row["reviewed_text"],
            gold_by_id[row["utterance_id"]].get("reviewed_text") or "",
        )
        >= 0.9
        for row in auto_approved_matches
    )
    packet_chars = len(packet_path.read_text(encoding="utf-8"))
    result = {
        **validation,
        "resolved": len(resolved),
        "resolved_decision_accuracy": _ratio(decision_matches, len(resolved)),
        "auto_decision_precision": _ratio(auto_matches, len(auto_rows)),
        "approved_speaker_accuracy": _ratio(speaker_matches, len(approved_matches)),
        "approved_text_similarity_at_least_0_9": _ratio(
            text_matches, len(approved_matches)
        ),
        "auto_approved_speaker_accuracy": _ratio(
            auto_speaker_matches, len(auto_approved_matches)
        ),
        "auto_approved_text_similarity_at_least_0_9": _ratio(
            auto_text_matches, len(auto_approved_matches)
        ),
        "packet_characters": packet_chars,
        "visual_fraction": round(
            packet["metrics"]["visual_review_count"] / len(source_by_id), 4
        ),
    }
    write_json(response_path.parent / "benchmark.json", result)
    return result

