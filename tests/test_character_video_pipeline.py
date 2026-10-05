import json
import sys
from pathlib import Path

import pytest

TOOLS_ROOT = Path(__file__).resolve().parents[1] / "research/character-corpus/tools"
sys.path.insert(0, str(TOOLS_ROOT))

from video_pipeline import PIPELINE_SCHEMA_VERSION, PIPELINE_VERSION  # noqa: E402
from video_pipeline.core import (  # noqa: E402
    RecognizedLine,
    build_review_queue,
    build_scene_drafts,
    interpret_recognized_lines,
    merge_ocr_samples,
    read_jsonl,
    validate_staging_bundle,
    write_json,
    write_jsonl,
)
from video_pipeline.low_cost_review import (  # noqa: E402
    LOW_COST_REVIEW_PROMPT_VERSION,
    LOW_COST_REVIEW_PROTOCOL_VERSION,
    benchmark_low_cost_review,
    build_low_cost_review_packet,
    validate_low_cost_review_response,
)
from video_pipeline.media import CACHE_PREFIX, strip_cache_prefix  # noqa: E402
from video_pipeline.review import REVIEW_SCHEMA_VERSION, validate_review_bundle  # noqa: E402


def test_interpretation_confirms_only_known_explicit_character_label():
    known = {"伊洛伊": "iroi"}
    confirmed = interpret_recognized_lines(
        [
            RecognizedLine("伊洛伊", 0.99, (100, 10, 180, 35)),
            RecognizedLine("这么绝佳的观景点，你是怎么找到的？", 0.98, (300, 70, 900, 110)),
        ],
        known,
    )
    assert confirmed == {
        "text": "这么绝佳的观景点，你是怎么找到的？",
        "confidence": 0.98,
        "speaker_label": "伊洛伊",
        "speaker_id": "iroi",
        "speaker_status": "confirmed",
        "attribution_evidence": ["explicit_known_character_label"],
    }

    cinematic = interpret_recognized_lines(
        [RecognizedLine("终止……干涉……", 0.91, (300, 70, 700, 110))],
        known,
    )
    assert cinematic["speaker_id"] is None
    assert cinematic["speaker_status"] == "unknown"
    assert cinematic["attribution_evidence"] == []

    unmapped_label = interpret_recognized_lines(
        [
            RecognizedLine("监狱", 0.99, (100, 10, 180, 35)),
            RecognizedLine("这里是格赫罗斯岛说唱之王。", 0.98, (300, 70, 900, 110)),
        ],
        known,
    )
    assert unmapped_label["text"] == "监狱 这里是格赫罗斯岛说唱之王。"
    assert unmapped_label["speaker_label"] is None

    repeated_label = interpret_recognized_lines(
        [
            RecognizedLine("艾尔菲德", 0.99, (100, 10, 220, 35)),
            RecognizedLine("之后就交给你了。", 0.98, (300, 70, 900, 110)),
        ],
        known,
        {"艾尔菲德"},
    )
    assert repeated_label["speaker_label"] == "艾尔菲德"
    assert repeated_label["speaker_id"] is None
    assert repeated_label["speaker_status"] == "confirmed"
    assert repeated_label["attribution_evidence"] == ["explicit_repeated_screen_label"]

    label_only = interpret_recognized_lines(
        [RecognizedLine("艾尔菲德", 0.99, (100, 10, 220, 35))],
        known,
        {"艾尔菲德"},
    )
    assert label_only is None


def test_merge_scene_and_review_queue_preserve_unknown_speaker_boundary():
    samples = [
        {
            "start_ms": 1000,
            "end_ms": 2000,
            "text": "监测到「极漩」的泯除速率",
            "confidence": 0.96,
            "speaker_label": None,
            "speaker_id": None,
            "speaker_status": "unknown",
            "attribution_evidence": [],
            "source_candidates": ["c1"],
        },
        {
            "start_ms": 2200,
            "end_ms": 3500,
            "text": "监测到「极漩」的泯除速率突然加快，尽快弄清是什么情况。",
            "confidence": 0.99,
            "speaker_label": None,
            "speaker_id": None,
            "speaker_status": "unknown",
            "attribution_evidence": [],
            "source_candidates": ["c2"],
        },
        {
            "start_ms": 25000,
            "end_ms": 27000,
            "text": "突发状况，新西里安市再次出现未知异象。",
            "confidence": 0.98,
            "speaker_label": "伊洛伊",
            "speaker_id": "iroi",
            "speaker_status": "confirmed",
            "attribution_evidence": ["explicit_known_character_label"],
            "source_candidates": ["c3"],
        },
    ]

    utterances = merge_ocr_samples(samples)
    assert len(utterances) == 2
    assert utterances[0]["text"].endswith("什么情况。")
    assert utterances[0]["source_candidates"] == ["c1", "c2"]
    assert utterances[0]["speaker_status"] == "unknown"
    assert all(row["review_status"] == "pending" for row in utterances)

    scenes = build_scene_drafts("part-1", utterances)
    assert len(scenes) == 2
    assert scenes[0]["confirmed_participants"] == []
    assert scenes[1]["confirmed_participants"] == ["iroi"]
    queue = build_review_queue(utterances)
    assert [row["utterance_id"] for row in queue] == ["u00001"]


def test_staging_validation_never_exports_pending_drafts(tmp_path: Path):
    manifest = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
    }
    utterance = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "utterance_id": "u00001",
        "start_ms": 1000,
        "end_ms": 2000,
        "text": "这是一句可复核的台词。",
        "speaker_status": "unknown",
        "review_status": "pending",
    }
    scene = {
        "scene_draft_id": "part-1-scene-001",
        "utterance_ids": ["u00001"],
        "review_status": "pending",
    }
    write_json(tmp_path / "manifest.json", manifest)
    write_jsonl(tmp_path / "utterances.jsonl", [utterance])
    write_jsonl(tmp_path / "scenes.draft.jsonl", [scene])

    result = validate_staging_bundle(tmp_path)
    assert result["export_ready"] is False
    assert result["pending_utterances"] == 1

    utterance["review_status"] = "approved"
    scene["review_status"] = "approved"
    write_jsonl(tmp_path / "utterances.jsonl", [utterance])
    write_jsonl(tmp_path / "scenes.draft.jsonl", [scene])
    assert validate_staging_bundle(tmp_path)["export_ready"] is True

    scene["utterance_ids"] = ["missing"]
    write_jsonl(tmp_path / "scenes.draft.jsonl", [scene])
    with pytest.raises(ValueError, match="unknown utterance"):
        validate_staging_bundle(tmp_path)


def test_cache_prefix_is_removed_without_touching_standard_media(tmp_path: Path):
    payload = b"\x00\x00\x00\x18ftypisom-media"
    cached = tmp_path / "cached.m4s"
    cached.write_bytes(CACHE_PREFIX + payload)
    cleaned = tmp_path / "cleaned.mp4"
    strip_cache_prefix(cached, cleaned)
    assert cleaned.read_bytes() == payload

    standard = tmp_path / "standard.mp4"
    standard.write_bytes(payload)
    copied = tmp_path / "copied.mp4"
    strip_cache_prefix(standard, copied)
    assert copied.read_bytes() == payload


def test_merge_handles_two_line_ocr_order_changes():
    common = {
        "speaker_label": None,
        "speaker_id": None,
        "speaker_status": "unknown",
        "attribution_evidence": [],
    }
    samples = [
        {
            **common,
            "start_ms": 1000,
            "end_ms": 3000,
            "text": "安静？我就是它命中注定的死敌 安静杀手！沸点魔王！",
            "confidence": 0.98,
            "source_candidates": ["c1"],
        },
        {
            **common,
            "start_ms": 3200,
            "end_ms": 4500,
            "text": "安静杀手！沸点魔王！安静？我就是它命中注定的死敌",
            "confidence": 0.96,
            "source_candidates": ["c2"],
        },
    ]
    result = merge_ocr_samples(samples)
    assert len(result) == 1
    assert result[0]["source_candidates"] == ["c1", "c2"]


def test_merge_adopts_explicit_label_and_completes_short_partial():
    samples = [
        {
            "start_ms": 1000,
            "end_ms": 1200,
            "text": "等下",
            "confidence": 0.97,
            "speaker_label": "艾尔菲德",
            "speaker_id": None,
            "speaker_status": "confirmed",
            "attribution_evidence": ["explicit_repeated_screen_label"],
            "source_candidates": ["c1"],
        },
        {
            "start_ms": 1300,
            "end_ms": 2500,
            "text": "等下，带上它。之后会用它和你联络。",
            "confidence": 0.99,
            "speaker_label": "艾尔菲德",
            "speaker_id": None,
            "speaker_status": "confirmed",
            "attribution_evidence": ["explicit_repeated_screen_label"],
            "source_candidates": ["c2"],
        },
    ]
    result = merge_ocr_samples(samples)
    assert len(result) == 1
    assert result[0]["speaker_label"] == "艾尔菲德"
    assert result[0]["speaker_status"] == "confirmed"
    assert result[0]["text"].endswith("联络。")


def test_merge_normalizes_speaker_label_punctuation():
    samples = []
    for index, label in enumerate(["浔（咻啪", "浔（咻啪）"]):
        samples.append(
            {
                "start_ms": 1000 + index * 1000,
                "end_ms": 1800 + index * 1000,
                "text": "行事风格果然还是这么死板呢。",
                "confidence": 0.98,
                "speaker_label": label,
                "speaker_id": None,
                "speaker_status": "confirmed",
                "attribution_evidence": ["explicit_repeated_screen_label"],
                "source_candidates": [f"c{index}"],
            }
        )
    result = merge_ocr_samples(samples)
    assert len(result) == 1


def test_preset_is_strict_json():
    preset_path = TOOLS_ROOT / "video_pipeline/presets/ntestation-1080p.json"
    preset = json.loads(preset_path.read_text(encoding="utf-8"))
    assert preset["source_width"] == 1920
    assert preset["source_height"] == 1080
    assert preset["scan_fps"] >= 4


def test_review_validation_requires_complete_decisions_and_matching_transcript(
    tmp_path: Path,
):
    write_jsonl(
        tmp_path / "utterances.jsonl",
        [
            {"utterance_id": "u00001"},
            {"utterance_id": "u00002"},
        ],
    )
    decisions = [
        {
            "review_schema_version": REVIEW_SCHEMA_VERSION,
            "utterance_id": "u00001",
            "decision": "approved",
        },
        {
            "review_schema_version": REVIEW_SCHEMA_VERSION,
            "utterance_id": "u00002",
            "decision": "rejected",
        },
    ]
    transcript = [
        {
            "reviewed_utterance_id": "u00001",
            "review_status": "approved",
            "text": "审核通过的台词。",
            "speaker_status": "unknown",
        }
    ]
    write_jsonl(tmp_path / "review-decisions.jsonl", decisions)
    write_jsonl(tmp_path / "reviewed-transcript.jsonl", transcript)

    result = validate_review_bundle(tmp_path)
    assert result == {
        "source_utterances": 2,
        "approved": 1,
        "rejected": 1,
        "confirmed_speakers": 0,
        "probable_speakers": 0,
        "unknown_speakers": 1,
        "review_complete": True,
        "formal_promotion_ready": False,
    }

    write_jsonl(tmp_path / "review-decisions.jsonl", decisions[:1])
    with pytest.raises(ValueError, match="coverage mismatch"):
        validate_review_bundle(tmp_path)


def _write_low_cost_source(tmp_path: Path) -> tuple[Path, Path]:
    output_dir = tmp_path / "staging"
    output_dir.mkdir()
    write_json(
        output_dir / "manifest.json",
        {"part_id": "part-2", "title": "测试剧情"},
    )
    write_jsonl(
        output_dir / "utterances.jsonl",
        [
            {
                "utterance_id": "u00001",
                "start_ms": 1000,
                "end_ms": 2500,
                "start_timestamp": "00:01",
                "end_timestamp": "00:02",
                "text": "这是明确姓名框下的完整台词。",
                "confidence": 0.99,
                "speaker_label": "薄荷",
                "speaker_id": "mint",
                "speaker_status": "confirmed",
                "attribution_evidence": ["explicit_known_character_label"],
            },
            {
                "utterance_id": "u00002",
                "start_ms": 3000,
                "end_ms": 3200,
                "start_timestamp": "00:03",
                "end_timestamp": "00:03",
                "text": "营业",
                "confidence": 0.82,
                "speaker_label": None,
                "speaker_id": None,
                "speaker_status": "unknown",
                "attribution_evidence": [],
            },
        ],
    )
    catalog = tmp_path / "catalog.json"
    write_json(
        catalog,
        [
            {
                "character_id": "mint",
                "names": {"zh": "薄荷", "en": "Mint"},
            }
        ],
    )
    return output_dir, catalog


def _low_cost_response(packet: dict) -> dict:
    return {
        "protocol_version": LOW_COST_REVIEW_PROTOCOL_VERSION,
        "prompt_version": LOW_COST_REVIEW_PROMPT_VERSION,
        "packet_id": packet["packet_id"],
        "input_sha256": packet["input_sha256"],
        "reviewer": {"kind": "low_cost_model", "model": "test-small"},
        "decisions": [
            {
                "utterance_id": "u00001",
                "decision": "approve",
                "content_kind": "dialogue",
                "reviewed_text": "这是明确姓名框下的完整台词。",
                "speaker_label": "薄荷",
                "speaker_id": "mint",
                "speaker_status": "confirmed",
                "confidence": "high",
                "reason_codes": ["explicit_speaker_label"],
                "evidence": ["explicit_known_character_label"],
            },
            {
                "utterance_id": "u00002",
                "decision": "reject",
                "content_kind": "background_text",
                "reviewed_text": None,
                "speaker_label": None,
                "speaker_id": None,
                "speaker_status": "unknown",
                "confidence": "high",
                "reason_codes": ["false_positive_background_text"],
                "evidence": ["frame_inspected"],
            },
        ],
    }


def test_low_cost_packet_routes_only_risky_utterances_to_visual_review(tmp_path: Path):
    output_dir, catalog = _write_low_cost_source(tmp_path)
    packet_dir = tmp_path / "packet"

    result = build_low_cost_review_packet(output_dir, catalog, 0, 5000, packet_dir)
    packet = json.loads((packet_dir / "request.json").read_text(encoding="utf-8"))

    assert result["utterance_count"] == 2
    assert result["visual_review_count"] == 1
    assert result["text_only_count"] == 1
    assert packet["utterances"][0]["frame_path"] is None
    assert packet["utterances"][1]["frame_path"].endswith(
        "review-full-frames\\u00002.jpg"
    )
    assert (packet_dir / "instructions.md").exists()


def test_low_cost_packet_refuses_unbounded_model_context(tmp_path: Path):
    output_dir, catalog = _write_low_cost_source(tmp_path)
    source = read_jsonl(output_dir / "utterances.jsonl")
    expanded = []
    for index in range(41):
        row = {**source[0]}
        row["utterance_id"] = f"u{index + 1:05d}"
        row["start_ms"] = index * 1000
        row["end_ms"] = index * 1000 + 500
        expanded.append(row)
    write_jsonl(output_dir / "utterances.jsonl", expanded)

    with pytest.raises(ValueError, match="exceeds 40 utterances"):
        build_low_cost_review_packet(output_dir, catalog, 0, 50_000, tmp_path / "packet")


def test_low_cost_packet_flags_incomplete_and_noisy_ocr_for_visual_review(
    tmp_path: Path,
):
    output_dir, catalog = _write_low_cost_source(tmp_path)
    rows = read_jsonl(output_dir / "utterances.jsonl")
    rows[0]["text"] = "这是一句很长的台词，但是最后只剩，暖"
    rows[1]["text"] = "专有 名词中间出现了异常空格。"
    rows[1]["confidence"] = 0.99
    write_jsonl(output_dir / "utterances.jsonl", rows)
    packet_dir = tmp_path / "packet"

    build_low_cost_review_packet(output_dir, catalog, 0, 5000, packet_dir)
    packet = json.loads((packet_dir / "request.json").read_text(encoding="utf-8"))

    assert "possible_incomplete_clause" in packet["utterances"][0]["risk_reasons"]
    assert "cjk_internal_whitespace" in packet["utterances"][1]["risk_reasons"]
    assert all(row["visual_required"] for row in packet["utterances"])


def test_low_cost_response_is_strict_and_never_overwrites_formal_review(tmp_path: Path):
    output_dir, catalog = _write_low_cost_source(tmp_path)
    packet_dir = tmp_path / "packet"
    build_low_cost_review_packet(output_dir, catalog, 0, 5000, packet_dir)
    packet = json.loads((packet_dir / "request.json").read_text(encoding="utf-8"))
    response_path = packet_dir / "response.json"
    write_json(response_path, _low_cost_response(packet))

    result = validate_low_cost_review_response(packet_dir / "request.json", response_path)

    assert result["auto_eligible"] == 2
    assert result["formal_review_files_unchanged"] is True
    assert not (output_dir / "review-decisions.jsonl").exists()
    assert len(read_jsonl(packet_dir / "auto-review-candidates.jsonl")) == 2
    assert read_jsonl(packet_dir / "escalation-queue.jsonl") == []

    invalid = _low_cost_response(packet)
    invalid["decisions"][0]["unexpected"] = True
    write_json(response_path, invalid)
    with pytest.raises(ValueError, match="fields mismatch"):
        validate_low_cost_review_response(packet_dir / "request.json", response_path)


def test_low_cost_reviewer_cannot_upgrade_or_replace_confirmed_speaker(tmp_path: Path):
    output_dir, catalog = _write_low_cost_source(tmp_path)
    packet_dir = tmp_path / "packet"
    build_low_cost_review_packet(output_dir, catalog, 0, 5000, packet_dir)
    packet = json.loads((packet_dir / "request.json").read_text(encoding="utf-8"))
    response = _low_cost_response(packet)
    response["decisions"][1].update(
        {
            "decision": "approve",
            "content_kind": "dialogue",
            "reviewed_text": "营业",
            "speaker_label": "薄荷",
            "speaker_id": "mint",
            "speaker_status": "confirmed",
        }
    )
    response_path = packet_dir / "response.json"
    write_json(response_path, response)

    with pytest.raises(ValueError, match="cannot upgrade speaker to confirmed"):
        validate_low_cost_review_response(packet_dir / "request.json", response_path)


def test_low_cost_packet_hash_covers_character_context(tmp_path: Path):
    output_dir, catalog = _write_low_cost_source(tmp_path)
    packet_dir = tmp_path / "packet"
    build_low_cost_review_packet(output_dir, catalog, 0, 5000, packet_dir)
    packet_path = packet_dir / "request.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    response_path = packet_dir / "response.json"
    write_json(response_path, _low_cost_response(packet))
    packet["characters"][0]["display_name"] = "被篡改的名字"
    write_json(packet_path, packet)

    with pytest.raises(ValueError, match="input_sha256 is invalid"):
        validate_low_cost_review_response(packet_path, response_path)


def test_low_cost_benchmark_compares_safe_candidates_with_gold(tmp_path: Path):
    output_dir, catalog = _write_low_cost_source(tmp_path)
    packet_dir = tmp_path / "packet"
    build_low_cost_review_packet(output_dir, catalog, 0, 5000, packet_dir)
    packet = json.loads((packet_dir / "request.json").read_text(encoding="utf-8"))
    response_path = packet_dir / "response.json"
    write_json(response_path, _low_cost_response(packet))
    gold_path = tmp_path / "gold.jsonl"
    write_jsonl(
        gold_path,
        [
            {
                "utterance_id": "u00001",
                "decision": "approved",
                "reviewed_text": "这是明确姓名框下的完整台词。",
                "speaker_id": "mint",
                "speaker_status": "confirmed",
            },
            {
                "utterance_id": "u00002",
                "decision": "rejected",
                "reviewed_text": None,
                "speaker_id": None,
                "speaker_status": "unknown",
            },
        ],
    )

    result = benchmark_low_cost_review(
        packet_dir / "request.json", response_path, gold_path
    )

    assert result["resolved_decision_accuracy"] == 1.0
    assert result["auto_decision_precision"] == 1.0
    assert result["approved_speaker_accuracy"] == 1.0
    assert result["approved_text_similarity_at_least_0_9"] == 1.0
    assert result["auto_approved_speaker_accuracy"] == 1.0
    assert result["auto_approved_text_similarity_at_least_0_9"] == 1.0
