from __future__ import annotations

from collections import Counter
from pathlib import Path

from .core import (
    RecognizedLine,
    append_jsonl,
    build_review_queue,
    build_scene_drafts,
    contains_cjk,
    interpret_recognized_lines,
    merge_ocr_samples,
    normalized_text,
    read_jsonl,
    write_json,
    write_jsonl,
)


def run_ocr(
    output_dir: Path,
    character_names: dict[str, str],
    settings: dict,
    cv2_module,
    paddle_ocr_class,
) -> list[dict]:
    import numpy as np

    candidates = read_jsonl(output_dir / "candidates.jsonl")
    checkpoint_path = output_dir / "ocr.checkpoint.jsonl"
    checkpoint_rows = read_jsonl(checkpoint_path)
    checkpoint_by_id = {row["candidate_id"]: row for row in checkpoint_rows}
    engine = paddle_ocr_class(
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,
        device="cpu",
    )
    samples: list[dict] = []
    for index, candidate in enumerate(candidates, start=1):
        checkpoint = checkpoint_by_id.get(candidate["candidate_id"])
        if checkpoint is not None:
            if checkpoint.get("interpreted"):
                samples.append(
                    {
                        "start_ms": checkpoint["start_ms"],
                        "end_ms": checkpoint["end_ms"],
                        **checkpoint["interpreted"],
                        "source_candidates": [checkpoint["candidate_id"]],
                    }
                )
            continue
        image_path = output_dir / candidate["frame_path"]
        image = cv2_module.imdecode(
            np.fromfile(str(image_path), dtype=np.uint8),
            cv2_module.IMREAD_COLOR,
        )
        if image is None:
            raise ValueError(f"cannot read candidate frame {image_path}")
        enlarged = cv2_module.resize(
            image,
            None,
            fx=settings["ocr_scale"],
            fy=settings["ocr_scale"],
            interpolation=cv2_module.INTER_LANCZOS4,
        )
        recognized: list[RecognizedLine] = []
        for result in engine.predict(input=enlarged):
            boxes = result["rec_boxes"].tolist()
            for text, score, box in zip(
                result["rec_texts"], result["rec_scores"], boxes, strict=True
            ):
                recognized.append(
                    RecognizedLine(
                        text=str(text).strip(),
                        score=float(score),
                        box=tuple(int(value) for value in box),
                    )
                )
        interpreted = interpret_recognized_lines(recognized, character_names)
        raw_row = {
            **candidate,
            "recognized_lines": [
                {"text": line.text, "score": round(line.score, 4), "box": list(line.box)}
                for line in recognized
            ],
        }
        if interpreted:
            raw_row["interpreted"] = interpreted
            samples.append(
                {
                    "start_ms": candidate["start_ms"],
                    "end_ms": candidate["end_ms"],
                    **interpreted,
                    "source_candidates": [candidate["candidate_id"]],
                }
            )
        append_jsonl(checkpoint_path, raw_row)
        if index % 25 == 0:
            write_json(
                output_dir / "ocr-progress.json",
                {"processed": index, "total": len(candidates)},
            )
    write_jsonl(output_dir / "ocr.raw.jsonl", samples)
    return samples


def rebuild_ocr_samples(
    output_dir: Path,
    character_names: dict[str, str],
) -> list[dict]:
    checkpoint_rows = read_jsonl(output_dir / "ocr.checkpoint.jsonl")
    label_counts: Counter[str] = Counter()
    for row in checkpoint_rows:
        lines = sorted(
            row.get("recognized_lines", []),
            key=lambda item: (item["box"][1], item["box"][0]),
        )
        if len(lines) < 2:
            continue
        first = lines[0]
        first_value = first["text"].strip()
        first_key = normalized_text(first_value)
        remaining = lines[1:]
        vertical_gap = min(item["box"][1] for item in remaining) - first["box"][1]
        remaining_length = sum(len(normalized_text(item["text"])) for item in remaining)
        if (
            contains_cjk(first_value)
            and first["score"] >= 0.45
            and 2 <= len(first_key) <= 10
            and vertical_gap >= 18
            and remaining_length >= 4
        ):
            label_counts[first_key] += 1
    repeated_labels = {label for label, count in label_counts.items() if count >= 4}
    samples = []
    for row in checkpoint_rows:
        recognized = [
            RecognizedLine(
                text=item["text"],
                score=float(item["score"]),
                box=tuple(int(value) for value in item["box"]),
            )
            for item in row.get("recognized_lines", [])
        ]
        interpreted = interpret_recognized_lines(
            recognized,
            character_names,
            repeated_labels,
        )
        if interpreted:
            samples.append(
                {
                    "start_ms": row["start_ms"],
                    "end_ms": row["end_ms"],
                    **interpreted,
                    "source_candidates": [row["candidate_id"]],
                }
            )
    write_jsonl(output_dir / "ocr.raw.jsonl", samples)
    return samples


def assemble_staging_bundle(output_dir: Path, part_id: str) -> dict:
    samples = read_jsonl(output_dir / "ocr.raw.jsonl")
    utterances = merge_ocr_samples(samples)
    scenes = build_scene_drafts(part_id, utterances)
    review_queue = build_review_queue(utterances)
    write_jsonl(output_dir / "utterances.jsonl", utterances)
    write_jsonl(output_dir / "scenes.draft.jsonl", scenes)
    write_jsonl(output_dir / "review-queue.jsonl", review_queue)
    report = {
        "ocr_samples": len(samples),
        "utterances": len(utterances),
        "scene_drafts": len(scenes),
        "confirmed_speakers": sum(
            row["speaker_status"] == "confirmed" for row in utterances
        ),
        "unknown_speakers": sum(row["speaker_status"] == "unknown" for row in utterances),
        "review_queue": len(review_queue),
        "export_ready": False,
    }
    write_json(output_dir / "report.json", report)
    return report
