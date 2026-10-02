from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .core import write_json, write_jsonl

CACHE_PREFIX = b"000000000"


@dataclass(frozen=True)
class MediaInfo:
    duration_ms: int
    width: int
    height: int
    fps: float


def _run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture,
    )


def find_cache_tracks(cache_dir: Path) -> tuple[Path, Path, dict]:
    info_path = cache_dir / "videoInfo.json"
    if not info_path.exists():
        info_path = cache_dir / ".videoInfo"
    if not info_path.exists():
        raise ValueError(f"missing videoInfo.json in {cache_dir}")
    info = json.loads(info_path.read_text(encoding="utf-8"))
    cid = str(info["cid"])
    candidates = sorted(cache_dir.glob(f"{cid}-*.m4s"), key=lambda path: path.stat().st_size)
    if len(candidates) < 2:
        raise ValueError(f"expected separate video and audio tracks in {cache_dir}")
    audio = candidates[0]
    video = candidates[-1]
    if video.stat().st_size <= audio.stat().st_size:
        raise ValueError("could not distinguish video and audio tracks")
    return video, audio, info


def strip_cache_prefix(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader:
        prefix = reader.read(len(CACHE_PREFIX))
        reader.seek(0)
        if prefix == CACHE_PREFIX:
            reader.seek(len(CACHE_PREFIX))
        with target.open("wb") as writer:
            shutil.copyfileobj(reader, writer, length=16 * 1024 * 1024)


def normalize_bilibili_cache(
    cache_dir: Path,
    output_video: Path,
    ffmpeg: Path,
    work_dir: Path,
) -> dict:
    video, audio, info = find_cache_tracks(cache_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    clean_video = work_dir / "video-clean.mp4"
    clean_audio = work_dir / "audio-clean.m4a"
    strip_cache_prefix(video, clean_video)
    strip_cache_prefix(audio, clean_audio)
    output_video.parent.mkdir(parents=True, exist_ok=True)
    try:
        _run(
            [
                str(ffmpeg),
                "-hide_banner",
                "-loglevel",
                "warning",
                "-y",
                "-i",
                str(clean_video),
                "-i",
                str(clean_audio),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(output_video),
            ]
        )
    finally:
        clean_video.unlink(missing_ok=True)
        clean_audio.unlink(missing_ok=True)
    return {
        "title": info.get("title", ""),
        "group_title": info.get("groupTitle", ""),
        "bvid": info.get("bvid", ""),
        "cid": str(info.get("cid", "")),
        "duration_seconds": info.get("duration"),
        "video_cache_file": video.name,
        "audio_cache_file": audio.name,
    }


def probe_media(video_path: Path, cv2_module) -> MediaInfo:
    capture = cv2_module.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"cannot open video {video_path}")
    fps = float(capture.get(cv2_module.CAP_PROP_FPS))
    frames = int(capture.get(cv2_module.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2_module.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2_module.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    if fps <= 0 or frames <= 0 or width <= 0 or height <= 0:
        raise ValueError(f"invalid media metadata for {video_path}")
    return MediaInfo(
        duration_ms=round(frames / fps * 1000),
        width=width,
        height=height,
        fps=fps,
    )


def _text_mask(image, cv2_module, np_module, settings: dict):
    gray = cv2_module.cvtColor(image, cv2_module.COLOR_BGR2GRAY)
    spread = image.max(axis=2).astype("int16") - image.min(axis=2).astype("int16")
    binary = (
        (gray >= settings["white_value_threshold"])
        & (spread <= settings["white_channel_spread"])
    ).astype("uint8") * 255
    binary = cv2_module.morphologyEx(
        binary,
        cv2_module.MORPH_CLOSE,
        cv2_module.getStructuringElement(cv2_module.MORPH_RECT, (2, 2)),
    )
    count, labels, stats, _ = cv2_module.connectedComponentsWithStats(binary, 8)
    glyph_components = []
    for index in range(1, count):
        x, y, width, height, area = [int(value) for value in stats[index]]
        if (
            settings["glyph_min_width"] <= width <= settings["glyph_max_width"]
            and settings["glyph_min_height"] <= height <= settings["glyph_max_height"]
            and settings["glyph_min_area"] <= area <= settings["glyph_max_area"]
        ):
            glyph_components.append(
                {
                    "index": index,
                    "x": x,
                    "right": x + width,
                    "center_y": y + height / 2,
                }
            )

    y_groups: list[list[dict]] = []
    for glyph in sorted(glyph_components, key=lambda item: (item["center_y"], item["x"])):
        matching = next(
            (
                group
                for group in y_groups
                if abs(
                    glyph["center_y"]
                    - sum(item["center_y"] for item in group) / len(group)
                )
                <= settings["line_y_tolerance"]
            ),
            None,
        )
        if matching is None:
            y_groups.append([glyph])
        else:
            matching.append(glyph)

    line_groups: list[list[dict]] = []
    for group in y_groups:
        current: list[dict] = []
        for glyph in sorted(group, key=lambda item: item["x"]):
            if current and glyph["x"] - current[-1]["right"] > settings["line_max_gap"]:
                line_groups.append(current)
                current = []
            current.append(glyph)
        if current:
            line_groups.append(current)

    selected: list[dict] = []
    for group in line_groups:
        span = max(item["right"] for item in group) - min(item["x"] for item in group)
        center_x = (
            min(item["x"] for item in group) + max(item["right"] for item in group)
        ) / 2
        centered_short_line = (
            settings["short_line_center_min"] * image.shape[1]
            <= center_x
            <= settings["short_line_center_max"] * image.shape[1]
        )
        if len(group) >= settings["min_line_glyphs"] and span >= settings["min_line_width"]:
            selected.extend(group)
        elif (
            centered_short_line
            and len(group) >= settings["short_line_min_glyphs"]
            and span >= settings["short_line_min_width"]
        ):
            selected.extend(group)

    filtered = np_module.zeros_like(binary)
    for glyph in selected:
        filtered[labels == glyph["index"]] = 255
    return filtered, len(selected)


def _write_image(path: Path, image, cv2_module, np_module, quality: int) -> None:
    ok, encoded = cv2_module.imencode(
        ".jpg",
        image,
        [int(cv2_module.IMWRITE_JPEG_QUALITY), quality],
    )
    if not ok:
        raise ValueError(f"could not encode candidate frame {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded.tofile(str(path))


def _mask_similarity(left, right, np_module) -> float:
    if left is None or right is None:
        return 0.0
    union = np_module.logical_or(left, right).sum()
    if not union:
        return 1.0
    intersection = np_module.logical_and(left, right).sum()
    return float(intersection / union)


def scan_candidates(
    video_path: Path,
    output_dir: Path,
    settings: dict,
    cv2_module,
    np_module,
) -> list[dict]:
    media = probe_media(video_path, cv2_module)
    if media.width != settings["source_width"] or media.height != settings["source_height"]:
        raise ValueError(
            f"preset expects {settings['source_width']}x{settings['source_height']}, "
            f"got {media.width}x{media.height}"
        )
    frames_dir = output_dir / "candidate_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2_module.VideoCapture(str(video_path))
    sample_step = max(1, round(media.fps / settings["scan_fps"]))
    crop = settings["ocr_crop"]
    detect = settings["detection_crop"]

    candidates: list[dict] = []
    active: dict | None = None
    frame_index = 0
    sample_index = 0

    def save_candidate(episode: dict, reason: str) -> None:
        candidate_id = f"c{len(candidates) + 1:06d}"
        relative = Path("candidate_frames") / f"{candidate_id}.jpg"
        target = output_dir / relative
        _write_image(
            target,
            episode["last_crop"],
            cv2_module,
            np_module,
            settings["jpeg_quality"],
        )
        candidates.append(
            {
                "candidate_id": candidate_id,
                "start_ms": episode["start_ms"],
                "end_ms": episode["last_ms"],
                "sample_ms": episode["last_ms"],
                "frame_path": relative.as_posix(),
                "glyph_count": episode["last_glyphs"],
                "selection_reason": reason,
            }
        )

    while True:
        ok = capture.grab()
        if not ok:
            break
        if frame_index % sample_step:
            frame_index += 1
            continue
        ok, frame = capture.retrieve()
        if not ok:
            break
        timestamp_ms = round(frame_index / media.fps * 1000)
        detection_image = frame[
            detect["y"] : detect["y"] + detect["height"],
            detect["x"] : detect["x"] + detect["width"],
        ]
        mask, glyphs = _text_mask(detection_image, cv2_module, np_module, settings)
        present = glyphs >= settings["min_glyphs"]
        crop_image = frame[
            crop["y"] : crop["y"] + crop["height"],
            crop["x"] : crop["x"] + crop["width"],
        ]

        if not present:
            if active is not None:
                active["missing_samples"] += 1
                if active["missing_samples"] >= settings["end_missing_samples"]:
                    save_candidate(active, "episode_end")
                    active = None
            frame_index += 1
            sample_index += 1
            continue

        if active is None:
            active = {
                "start_ms": timestamp_ms,
                "last_ms": timestamp_ms,
                "last_crop": crop_image.copy(),
                "last_mask": mask.copy(),
                "last_glyphs": glyphs,
                "stable_samples": 1,
                "missing_samples": 0,
            }
        else:
            similarity = _mask_similarity(active["last_mask"] > 0, mask > 0, np_module)
            if similarity < settings["episode_similarity_threshold"]:
                save_candidate(active, "text_change")
                active = {
                    "start_ms": timestamp_ms,
                    "last_ms": timestamp_ms,
                    "last_crop": crop_image.copy(),
                    "last_mask": mask.copy(),
                    "last_glyphs": glyphs,
                    "stable_samples": 1,
                    "missing_samples": 0,
                }
            else:
                active["stable_samples"] = (
                    active["stable_samples"] + 1
                    if similarity >= settings["stable_similarity_threshold"]
                    else 1
                )
                active["last_ms"] = timestamp_ms
                active["last_crop"] = crop_image.copy()
                active["last_mask"] = mask.copy()
                active["last_glyphs"] = glyphs
                active["missing_samples"] = 0

        if sample_index and sample_index % round(settings["scan_fps"] * 60) == 0:
            progress = {
                "processed_ms": timestamp_ms,
                "duration_ms": media.duration_ms,
                "candidate_count": len(candidates),
            }
            write_json(output_dir / "scan-progress.json", progress)
        frame_index += 1
        sample_index += 1

    if active is not None:
        save_candidate(active, "video_end")
    capture.release()
    write_jsonl(output_dir / "candidates.jsonl", candidates)
    write_json(
        output_dir / "scan-report.json",
        {
            "duration_ms": media.duration_ms,
            "scan_fps": settings["scan_fps"],
            "candidate_count": len(candidates),
        },
    )
    return candidates
