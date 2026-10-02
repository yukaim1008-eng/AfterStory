from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from . import PIPELINE_SCHEMA_VERSION, PIPELINE_VERSION
from .core import (
    load_character_names,
    pipeline_config_hash,
    read_json,
    validate_staging_bundle,
    write_json,
)
from .media import normalize_bilibili_cache, probe_media, scan_candidates
from .ocr_stage import assemble_staging_bundle, rebuild_ocr_samples, run_ocr
from .review import render_review_report, validate_review_bundle

TOOL_DIR = Path(__file__).resolve().parent
CORPUS_ROOT = TOOL_DIR.parents[1]
DEFAULT_PRESET = TOOL_DIR / "presets/ntestation-1080p.json"
DEFAULT_CATALOG = CORPUS_ROOT / "catalog.json"
DEFAULT_LOCAL_ROOT = CORPUS_ROOT / "local/video-pipeline"


def _import_runtime_dependencies():
    try:
        import cv2
        import numpy as np
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError(
            "missing local OCR dependencies; use run.ps1 so they stay outside project dependencies"
        ) from exc
    return cv2, np, PaddleOCR


def _import_cv2():
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("missing OpenCV; use run.ps1") from exc
    return cv2


def _safe_output_dir(path: Path) -> Path:
    resolved = path.resolve()
    local_root = (CORPUS_ROOT / "local").resolve()
    if resolved != local_root and local_root not in resolved.parents:
        raise ValueError(f"pipeline output must stay under {local_root}")
    return resolved


def _load_manifest(path: Path) -> dict | None:
    if not path.exists():
        return None
    value = read_json(path)
    if not isinstance(value, dict):
        raise ValueError("manifest.json must contain an object")
    return value


def _save_manifest(output_dir: Path, manifest: dict) -> None:
    write_json(output_dir / "manifest.json", manifest)


def run_pipeline(args: argparse.Namespace) -> dict:
    cv2, np, paddle_ocr_class = _import_runtime_dependencies()
    output_dir = _safe_output_dir(args.output or DEFAULT_LOCAL_ROOT / args.part_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    preset_path = args.preset.resolve()
    preset = read_json(preset_path)
    if not isinstance(preset, dict):
        raise ValueError("preset must contain an object")

    source = {
        "cache_dir": str(args.cache_dir.resolve()) if args.cache_dir else None,
        "video": str(args.video.resolve()) if args.video else None,
    }
    config = {
        "part_id": args.part_id,
        "title": args.title,
        "source": source,
        "preset": preset,
        "pipeline_version": PIPELINE_VERSION,
    }
    config_hash = pipeline_config_hash(config)
    manifest_path = output_dir / "manifest.json"
    manifest = _load_manifest(manifest_path)
    if manifest and manifest.get("config_hash") != config_hash:
        raise ValueError(
            "existing output was created with different input or settings; use a new output folder"
        )
    if manifest is None:
        manifest = {
            "schema_version": PIPELINE_SCHEMA_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "part_id": args.part_id,
            "title": args.title,
            "config_hash": config_hash,
            "source": source,
            "preset": preset_path.name,
            "stages": {},
            "promotion_status": "staging_only",
        }
        _save_manifest(output_dir, manifest)

    normalized_video = output_dir / "media/source.mp4"
    if args.video:
        video_path = args.video.resolve()
        manifest["stages"]["normalize"] = {"status": "not_needed"}
    else:
        if not args.ffmpeg:
            raise ValueError("--ffmpeg is required with --cache-dir")
        video_path = normalized_video
        if not video_path.exists():
            cache_metadata = normalize_bilibili_cache(
                args.cache_dir.resolve(),
                video_path,
                args.ffmpeg.resolve(),
                output_dir / "work",
            )
            manifest["cache_metadata"] = cache_metadata
        manifest["stages"]["normalize"] = {"status": "completed"}
        _save_manifest(output_dir, manifest)

    media = probe_media(video_path, cv2)
    manifest["media"] = {
        "path": str(video_path),
        "duration_ms": media.duration_ms,
        "width": media.width,
        "height": media.height,
        "fps": round(media.fps, 4),
    }

    candidates_path = output_dir / "candidates.jsonl"
    if not candidates_path.exists():
        candidates = scan_candidates(video_path, output_dir, preset, cv2, np)
    else:
        candidates = [
            json.loads(line)
            for line in candidates_path.read_text(encoding="utf-8").splitlines()
            if line
        ]
    manifest["stages"]["scan"] = {
        "status": "completed",
        "candidates": len(candidates),
    }
    _save_manifest(output_dir, manifest)

    ocr_path = output_dir / "ocr.raw.jsonl"
    character_names = load_character_names(args.catalog.resolve())
    if not ocr_path.exists():
        run_ocr(
            output_dir,
            character_names,
            preset,
            cv2,
            paddle_ocr_class,
        )
    samples = rebuild_ocr_samples(output_dir, character_names)
    manifest["stages"]["ocr"] = {"status": "completed", "samples": len(samples)}
    _save_manifest(output_dir, manifest)

    report = assemble_staging_bundle(output_dir, args.part_id)
    validation = validate_staging_bundle(output_dir)
    manifest["stages"]["assemble"] = {"status": "completed", **report}
    manifest["validation"] = validation
    _save_manifest(output_dir, manifest)
    return {"output": str(output_dir), **report, "validation": validation}


def validate_command(args: argparse.Namespace) -> dict:
    return validate_staging_bundle(_safe_output_dir(args.output))


def assemble_command(args: argparse.Namespace) -> dict:
    output_dir = _safe_output_dir(args.output)
    character_names = load_character_names(args.catalog.resolve())
    rebuild_ocr_samples(output_dir, character_names)
    report = assemble_staging_bundle(output_dir, args.part_id)
    validation = validate_staging_bundle(output_dir)
    manifest = _load_manifest(output_dir / "manifest.json")
    if manifest is not None:
        manifest["stages"]["assemble"] = {"status": "completed", **report}
        manifest["validation"] = validation
        _save_manifest(output_dir, manifest)
    return {**report, "validation": validation}


def review_report_command(args: argparse.Namespace) -> dict:
    return render_review_report(_safe_output_dir(args.output), _import_cv2())


def review_validate_command(args: argparse.Namespace) -> dict:
    return validate_review_bundle(_safe_output_dir(args.output))


def main() -> None:
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    parser = argparse.ArgumentParser(
        description=(
            "Extract review-gated visual subtitles into the local character corpus staging area."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--part-id", required=True)
    run_parser.add_argument("--title", default="")
    source = run_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--cache-dir", type=Path)
    source.add_argument("--video", type=Path)
    run_parser.add_argument("--ffmpeg", type=Path)
    run_parser.add_argument("--output", type=Path)
    run_parser.add_argument("--preset", type=Path, default=DEFAULT_PRESET)
    run_parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    run_parser.set_defaults(handler=run_pipeline)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--output", type=Path, required=True)
    validate_parser.set_defaults(handler=validate_command)

    assemble_parser = subparsers.add_parser("assemble")
    assemble_parser.add_argument("--part-id", required=True)
    assemble_parser.add_argument("--output", type=Path, required=True)
    assemble_parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    assemble_parser.set_defaults(handler=assemble_command)

    review_report_parser = subparsers.add_parser("review-report")
    review_report_parser.add_argument("--output", type=Path, required=True)
    review_report_parser.set_defaults(handler=review_report_command)

    review_validate_parser = subparsers.add_parser("review-validate")
    review_validate_parser.add_argument("--output", type=Path, required=True)
    review_validate_parser.set_defaults(handler=review_validate_command)

    args = parser.parse_args()
    result = args.handler(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
