from __future__ import annotations

import html
from pathlib import Path

from .core import read_json, read_jsonl, write_json

REVIEW_SCHEMA_VERSION = "1.0"


def _write_jpeg(path: Path, image, cv2_module) -> None:
    ok, encoded = cv2_module.imencode(
        ".jpg",
        image,
        [int(cv2_module.IMWRITE_JPEG_QUALITY), 92],
    )
    if not ok:
        raise ValueError(f"could not encode review frame {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded.tofile(str(path))


def ensure_review_frames(output_dir: Path, cv2_module) -> int:
    manifest = read_json(output_dir / "manifest.json")
    video_path = Path(manifest["media"]["path"])
    if not video_path.exists():
        raise ValueError(f"review source video does not exist: {video_path}")
    utterances = read_jsonl(output_dir / "utterances.jsonl")
    frames_dir = output_dir / "review-full-frames"
    capture = cv2_module.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"cannot open review source video: {video_path}")
    created = 0
    try:
        for utterance in utterances:
            target = frames_dir / f"{utterance['utterance_id']}.jpg"
            if target.exists():
                continue
            midpoint = (utterance["start_ms"] + utterance["end_ms"]) // 2
            capture.set(cv2_module.CAP_PROP_POS_MSEC, midpoint)
            ok, frame = capture.read()
            if not ok:
                raise ValueError(
                    f"cannot read review frame for {utterance['utterance_id']}"
                )
            frame = cv2_module.resize(
                frame,
                (960, 540),
                interpolation=cv2_module.INTER_AREA,
            )
            _write_jpeg(target, frame, cv2_module)
            created += 1
    finally:
        capture.release()
    return created


def validate_review_bundle(output_dir: Path) -> dict:
    utterances = read_jsonl(output_dir / "utterances.jsonl")
    decisions = read_jsonl(output_dir / "review-decisions.jsonl")
    transcript = read_jsonl(output_dir / "reviewed-transcript.jsonl")
    source_ids = [row["utterance_id"] for row in utterances]
    decision_ids = [row.get("utterance_id") for row in decisions]
    if len(decision_ids) != len(set(decision_ids)):
        raise ValueError("duplicate review decision utterance_id")
    if set(decision_ids) != set(source_ids):
        missing = sorted(set(source_ids) - set(decision_ids))
        extra = sorted(set(decision_ids) - set(source_ids))
        raise ValueError(f"review coverage mismatch; missing={missing}, extra={extra}")
    for row in decisions:
        if row.get("review_schema_version") != REVIEW_SCHEMA_VERSION:
            raise ValueError("unsupported review_schema_version")
        if row.get("decision") not in {"approved", "rejected"}:
            raise ValueError(f"invalid review decision for {row.get('utterance_id')}")

    approved_ids = {
        row["utterance_id"] for row in decisions if row["decision"] == "approved"
    }
    transcript_ids = [row.get("reviewed_utterance_id") for row in transcript]
    if len(transcript_ids) != len(set(transcript_ids)):
        raise ValueError("duplicate reviewed_utterance_id")
    if set(transcript_ids) != approved_ids:
        raise ValueError("reviewed transcript does not match approved decisions")
    for row in transcript:
        if row.get("review_status") != "approved":
            raise ValueError("reviewed transcript contains a non-approved row")
        if not isinstance(row.get("text"), str) or not row["text"].strip():
            raise ValueError("reviewed transcript contains empty text")
        if row.get("speaker_status") not in {
            "confirmed",
            "probable",
            "ambiguous",
            "unknown",
        }:
            raise ValueError("reviewed transcript contains invalid speaker_status")

    result = {
        "source_utterances": len(utterances),
        "approved": len(approved_ids),
        "rejected": len(decisions) - len(approved_ids),
        "confirmed_speakers": sum(
            row["speaker_status"] == "confirmed" for row in transcript
        ),
        "probable_speakers": sum(
            row["speaker_status"] == "probable" for row in transcript
        ),
        "unknown_speakers": sum(
            row["speaker_status"] == "unknown" for row in transcript
        ),
        "review_complete": True,
        "formal_promotion_ready": False,
    }
    write_json(output_dir / "review-validation.json", result)
    return result


def render_review_report(output_dir: Path, cv2_module) -> dict:
    created_frames = ensure_review_frames(output_dir, cv2_module)
    utterances = read_jsonl(output_dir / "utterances.jsonl")
    decisions_path = output_dir / "review-decisions.jsonl"
    decisions = (
        {row["utterance_id"]: row for row in read_jsonl(decisions_path)}
        if decisions_path.exists()
        else {}
    )
    cards = []
    counts = {"approved": 0, "rejected": 0, "pending": 0}
    for utterance in utterances:
        utterance_id = utterance["utterance_id"]
        decision = decisions.get(utterance_id, {})
        status = decision.get("decision", "pending")
        if status not in counts:
            raise ValueError(f"invalid review decision for {utterance_id}")
        counts[status] += 1
        content_kind = decision.get("content_kind", "unreviewed")
        speaker = decision.get("speaker_label") or utterance.get("speaker_label") or "未知"
        speaker_status = decision.get("speaker_status", utterance["speaker_status"])
        reviewed_text = decision.get("reviewed_text") or "—"
        reason = decision.get("reason", "尚未审核")
        timestamp = f"{utterance['start_timestamp']}–{utterance['end_timestamp']}"
        escaped_kind = html.escape(content_kind)
        escaped_speaker = html.escape(speaker)
        escaped_speaker_status = html.escape(speaker_status)
        escaped_original = html.escape(utterance["text"])
        escaped_reviewed = html.escape(reviewed_text).replace(chr(10), "<br>")
        escaped_reason = html.escape(reason)
        cards.append(
            f"""<article class="card {status}" data-decision="{status}">
<img loading="lazy" src="review-full-frames/{utterance_id}.jpg" alt="{utterance_id}">
<div class="body">
<div class="meta"><b>{utterance_id}</b> · {timestamp} · {escaped_kind} · <b>{status}</b></div>
<div><strong>说话者：</strong>{escaped_speaker} <small>({escaped_speaker_status})</small></div>
<div><strong>原 OCR：</strong>{escaped_original}</div>
<div><strong>审核稿：</strong>{escaped_reviewed}</div>
<div class="reason"><strong>依据：</strong>{escaped_reason}</div>
</div></article>"""
        )

    summary = (
        f"源候选 {len(utterances)}　通过 {counts['approved']}　"
        f"剔除 {counts['rejected']}　待审 {counts['pending']}"
    )
    report = f"""<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8">
<title>剧情字幕审核报告</title><style>
body{{font-family:"Microsoft YaHei",sans-serif;background:#101217;color:#eee;margin:0}}
header{{position:sticky;top:0;background:#191d26;padding:16px;z-index:2}}
main{{max-width:1500px;margin:auto;padding:16px}}
button{{margin:8px 8px 0 0;padding:7px 12px}}
.card{{display:grid;grid-template-columns:minmax(360px,640px) 1fr;gap:16px}}
.card{{background:#1a1f29;margin:14px 0;border-left:6px solid #d6a84b}}
.card{{border-radius:8px;overflow:hidden}}
.card.approved{{border-color:#50c878}}
.card.rejected{{border-color:#e05a5a;opacity:.78}}
img{{width:100%;height:auto;display:block}}
.body{{padding:12px 16px 16px 0;line-height:1.65}}
.meta{{color:#ffdc62;margin-bottom:8px}}
small,.reason{{color:#abb3c2}}
@media(max-width:900px){{
  .card{{grid-template-columns:1fr}}
  .body{{padding:12px 16px 16px}}
}}
</style></head><body><header><b>剧情字幕审核报告</b>　{summary}<br>
<button onclick="show('all')">全部</button>
<button onclick="show('approved')">通过</button>
<button onclick="show('rejected')">剔除</button>
<button onclick="show('pending')">待审</button></header>
<main>{''.join(cards)}</main>
<script>
function show(v){{
  document.querySelectorAll('.card').forEach(
    x => x.style.display = (v === 'all' || x.dataset.decision === v) ? 'grid' : 'none'
  )
}}
</script></body></html>"""
    target = output_dir / "review-report.html"
    target.write_text(report, encoding="utf-8")
    return {"report": str(target), "created_frames": created_frames, **counts}
