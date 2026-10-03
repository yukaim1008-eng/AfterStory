from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator

CHARACTER_RESEARCH_SCHEMA_VERSION = "1.0"
NTESTATION_API = "https://www.ntestation.com/api.php"
NTESTATION_BASE = "https://www.ntestation.com/"

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
CanonConfidence = Literal["direct", "supported", "provisional"]
CanonReviewStatus = Literal["candidate", "accepted", "rejected", "superseded"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocalizedNames(StrictModel):
    zh: str
    ja: str = ""
    ko: str = ""
    en: str = ""


class CharacterCatalogEntry(StrictModel):
    schema_version: Literal["1.0"] = CHARACTER_RESEARCH_SCHEMA_VERSION
    character_id: str
    names: LocalizedNames
    source_work: str = "异环"
    role_scope: Literal["named_character"] = "named_character"
    research_status: Literal[
        "discovered",
        "profile_collected",
        "evidence_collected",
        "profile_draft",
        "reviewed",
        "runtime_ready",
    ]


class SourceRecord(StrictModel):
    schema_version: Literal["1.0"] = CHARACTER_RESEARCH_SCHEMA_VERSION
    source_id: str
    source_type: Literal["profile_archive_mirror", "story_video"]
    provenance: Literal["in_game_archive_mirror", "in_game_footage"]
    platform: str
    title: str
    url: HttpUrl
    page_title: str = ""
    revision_id: int | None = None
    revision_timestamp: datetime | None = None
    retrieved_at: datetime
    content_hash: str = ""
    raw_cache_path: str = ""
    status: Literal["available", "missing", "indexed"]
    external_id: str = ""
    creator: str = ""
    published_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    part_count: int | None = Field(default=None, ge=0)
    content_checkpoint: str = ""
    subtitle_mode: Literal["unknown", "platform_subtitles", "no_platform_subtitles"] = "unknown"
    visual_subtitle_status: Literal[
        "unknown", "user_confirmed_present", "verified_present", "absent"
    ] = "unknown"
    notes: str = ""


class SourcePartRecord(StrictModel):
    schema_version: Literal["1.0"] = CHARACTER_RESEARCH_SCHEMA_VERSION
    part_id: str
    source_id: str
    external_part_id: str
    position: int = Field(ge=1)
    title: str
    duration_ms: int = Field(gt=0)
    content_type: Literal["main_story", "side_story", "unknown"]
    subtitle_mode: Literal["unknown", "platform_subtitles", "no_platform_subtitles"]
    visual_subtitle_status: Literal[
        "unknown", "user_confirmed_present", "verified_present", "absent"
    ] = "unknown"
    processing_status: Literal[
        "indexed", "subtitle_extracted", "scenes_segmented", "evidence_extracted", "reviewed"
    ] = "indexed"


class ProfileIndexRecord(StrictModel):
    schema_version: Literal["1.0"] = CHARACTER_RESEARCH_SCHEMA_VERSION
    profile_id: str
    character_id: str
    source_id: str
    source_revision_id: int
    content_hash: str
    fields: dict[str, str]
    has_character_introduction: bool
    has_encounter_profile: bool
    archive_entry_titles: list[str]
    voice_category_counts: dict[str, int]


class SceneRecord(StrictModel):
    schema_version: Literal["1.0"] = CHARACTER_RESEARCH_SCHEMA_VERSION
    scene_id: NonEmptyStr
    source_id: NonEmptyStr
    source_part_id: NonEmptyStr
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    chapter: NonEmptyStr
    summary: NonEmptyStr
    participants: list[str]
    canon_checkpoint: NonEmptyStr
    review_status: Literal["draft", "reviewed"] = "draft"


class EvidenceRecord(StrictModel):
    schema_version: Literal["1.0"] = CHARACTER_RESEARCH_SCHEMA_VERSION
    evidence_id: str
    scene_id: str
    character_id: str
    observation: str
    interpretation: str
    confidence: Literal["direct", "supported", "provisional"]
    limitations: str
    affected_fields: list[
        Literal[
            "identity",
            "personality",
            "speaking_style",
            "behavior",
            "worldview",
            "relationship_premise",
        ]
    ]


class TraitRecord(StrictModel):
    schema_version: Literal["1.0"] = CHARACTER_RESEARCH_SCHEMA_VERSION
    trait_id: str
    character_id: str
    name: str
    importance: Literal["core", "supporting", "conditional"]
    frequency: Literal["constant", "common", "occasional", "rare"]
    review_status: Literal["draft", "user_confirmed", "evidence_confirmed"]
    triggers: list[str]
    expressions: list[str]
    boundaries: list[str]
    evidence_ids: list[str]
    prompt_summary: str


class CanonCheckpointRecord(StrictModel):
    schema_version: Literal["1.0"] = CHARACTER_RESEARCH_SCHEMA_VERSION
    checkpoint_id: NonEmptyStr
    source_work: NonEmptyStr
    display_name: NonEmptyStr
    sequence: int = Field(ge=0)
    game_version: str = ""
    chapter: str = ""
    predecessor_id: str = ""
    spoiler_scope: NonEmptyStr


class CanonEvidenceRecord(StrictModel):
    schema_version: Literal["1.0"] = CHARACTER_RESEARCH_SCHEMA_VERSION
    canon_evidence_id: NonEmptyStr
    origin_type: Literal["scene", "profile"]
    scene_id: str = ""
    profile_id: str = ""
    source_part_id: str = ""
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, gt=0)
    profile_locator: str = ""
    evidence_kind: Literal[
        "dialogue", "action", "document", "broadcast", "visual", "profile_field"
    ]
    actor_character_ids: list[str] = Field(default_factory=list)
    speaker_character_id: str = ""
    observation: NonEmptyStr
    transcript_refs: list[str] = Field(default_factory=list)
    review_status: Literal["candidate", "accepted", "rejected"] = "candidate"
    review_notes: str = ""

    @model_validator(mode="after")
    def validate_origin(self):
        scene_fields = (
            self.scene_id.strip(),
            self.source_part_id.strip(),
            self.start_ms,
            self.end_ms,
        )
        if self.origin_type == "scene":
            if not all(value is not None and value != "" for value in scene_fields):
                raise ValueError("scene evidence requires scene, source part, and time range")
            if self.profile_id.strip() or self.profile_locator.strip():
                raise ValueError("scene evidence cannot include profile locator")
            if self.evidence_kind == "profile_field":
                raise ValueError("scene evidence cannot use profile_field kind")
        else:
            if not self.profile_id.strip() or not self.profile_locator.strip():
                raise ValueError("profile evidence requires profile_id and profile_locator")
            if any(value is not None and value != "" for value in scene_fields):
                raise ValueError("profile evidence cannot include scene locator")
            if self.evidence_kind != "profile_field":
                raise ValueError("profile evidence requires profile_field kind")
        self.scene_id = self.scene_id.strip()
        self.profile_id = self.profile_id.strip()
        self.source_part_id = self.source_part_id.strip()
        self.profile_locator = self.profile_locator.strip()
        return self


class WorldEntityRecord(StrictModel):
    schema_version: Literal["1.0"] = CHARACTER_RESEARCH_SCHEMA_VERSION
    world_entity_id: NonEmptyStr
    source_work: NonEmptyStr
    entity_type: Literal[
        "organization",
        "location",
        "concept",
        "phenomenon",
        "object",
        "event",
        "species",
    ]
    names: LocalizedNames
    aliases: list[str] = Field(default_factory=list)
    summary: NonEmptyStr
    first_checkpoint: NonEmptyStr
    review_status: CanonReviewStatus = "candidate"
    evidence_ids: list[str] = Field(default_factory=list)


class CharacterFactRecord(StrictModel):
    schema_version: Literal["1.0"] = CHARACTER_RESEARCH_SCHEMA_VERSION
    fact_id: NonEmptyStr
    character_id: NonEmptyStr
    fact_type: Literal[
        "identity", "occupation", "affiliation", "ability", "background", "status", "other"
    ]
    value_text: str = ""
    value_entity_id: str = ""
    canon_checkpoint: NonEmptyStr
    valid_from_checkpoint: str = ""
    valid_to_checkpoint: str = ""
    confidence: CanonConfidence
    review_status: CanonReviewStatus = "candidate"
    evidence_ids: list[str]
    supersedes_id: str = ""

    @model_validator(mode="after")
    def validate_value(self):
        if bool(self.value_text.strip()) == bool(self.value_entity_id.strip()):
            raise ValueError("exactly one of value_text or value_entity_id is required")
        self.value_text = self.value_text.strip()
        self.value_entity_id = self.value_entity_id.strip()
        return self


class WorldFactRecord(StrictModel):
    schema_version: Literal["1.0"] = CHARACTER_RESEARCH_SCHEMA_VERSION
    fact_id: NonEmptyStr
    subject_entity_id: NonEmptyStr
    predicate: NonEmptyStr
    object_entity_id: str = ""
    object_text: str = ""
    fact_scope: Literal["objective", "character_belief", "reported_claim"]
    perspective_character_id: str = ""
    canon_checkpoint: NonEmptyStr
    valid_from_checkpoint: str = ""
    valid_to_checkpoint: str = ""
    confidence: CanonConfidence
    review_status: CanonReviewStatus = "candidate"
    evidence_ids: list[str]
    supersedes_id: str = ""

    @model_validator(mode="after")
    def validate_object_and_perspective(self):
        if bool(self.object_text.strip()) == bool(self.object_entity_id.strip()):
            raise ValueError("exactly one of object_text or object_entity_id is required")
        if self.fact_scope == "character_belief" and not self.perspective_character_id.strip():
            raise ValueError("character_belief requires perspective_character_id")
        if self.fact_scope == "objective" and self.perspective_character_id.strip():
            raise ValueError("objective fact cannot have perspective_character_id")
        self.object_text = self.object_text.strip()
        self.object_entity_id = self.object_entity_id.strip()
        self.perspective_character_id = self.perspective_character_id.strip()
        return self


class CharacterRelationRecord(StrictModel):
    schema_version: Literal["1.0"] = CHARACTER_RESEARCH_SCHEMA_VERSION
    relation_id: NonEmptyStr
    source_character_id: NonEmptyStr
    target_character_id: NonEmptyStr
    category: Literal[
        "family",
        "organizational",
        "cooperative",
        "social",
        "protective",
        "adversarial",
        "romantic",
        "other",
    ]
    label: NonEmptyStr
    directionality: Literal["directed", "symmetric"]
    summary: NonEmptyStr
    canon_checkpoint: NonEmptyStr
    valid_from_checkpoint: str = ""
    valid_to_checkpoint: str = ""
    confidence: CanonConfidence
    review_status: CanonReviewStatus = "candidate"
    evidence_ids: list[str]
    supersedes_id: str = ""

    @model_validator(mode="after")
    def validate_characters(self):
        if self.source_character_id == self.target_character_id:
            raise ValueError("character relation cannot reference the same character twice")
        return self


def read_jsonl(path: Path, model):
    if not path.exists():
        return []
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(model.model_validate_json(line))
        except Exception as exc:
            raise ValueError(f"{path}:{line_number}: {exc}") from exc
    return records


def write_jsonl(path: Path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n"
        for record in records
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def load_catalog(root: Path) -> list[CharacterCatalogEntry]:
    data = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    for item in data:
        if "profile_status" in item and "research_status" not in item:
            item["research_status"] = item.pop("profile_status")
    return [CharacterCatalogEntry.model_validate(item) for item in data]


def write_catalog(root: Path, records: list[CharacterCatalogEntry]) -> None:
    data = [record.model_dump(mode="json") for record in records]
    (root / "catalog.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def _wiki_text(page: dict) -> str:
    revisions = page.get("revisions") or []
    if not revisions:
        return ""
    return revisions[0].get("slots", {}).get("main", {}).get("content", "")


def _query_pages(client: httpx.Client, titles: list[str]) -> list[dict]:
    response = client.get(
        NTESTATION_API,
        params={
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "prop": "revisions",
            "rvprop": "ids|timestamp|content",
            "rvslots": "main",
            "redirects": "1",
            "titles": "|".join(titles),
        },
    )
    response.raise_for_status()
    return response.json()["query"]["pages"]


def _strip_markup(value: str) -> str:
    value = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    value = re.sub(r"<br\s*/?>", " / ", value, flags=re.IGNORECASE)
    value = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"\[\[([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"'{2,}", "", value)
    return re.sub(r"\s+", " ", value).strip(" |\u3000")


def _slug(english_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", english_name.lower()).strip("-")
    if not slug:
        raise ValueError(f"Cannot create character id from {english_name!r}")
    return slug


def parse_name_table(wikitext: str) -> list[CharacterCatalogEntry]:
    records = []
    for line in wikitext.splitlines():
        if not line.startswith("| '''[["):
            continue
        cells = [cell.strip(" '\u3000") for cell in line[1:].split("||")]
        match = re.search(r"\[\[([^\]|]+)", cells[0])
        if not match or len(cells) < 4:
            continue
        zh = match.group(1).strip()
        en = cells[3].strip()
        records.append(
            CharacterCatalogEntry(
                character_id=_slug(en),
                names=LocalizedNames(zh=zh, ja=cells[1], ko=cells[2], en=en),
                research_status="discovered",
            )
        )
    if not records:
        raise ValueError("No characters found in NTE Station name table")
    return records


def _section(wikitext: str, headings: list[str]) -> str:
    for heading in headings:
        marker = re.search(heading, wikitext)
        if not marker:
            continue
        remainder = wikitext[marker.end() :]
        next_heading = re.search(r"(?m)^={1,3}[^=].*?={1,3}\s*$", remainder)
        return remainder[: next_heading.start() if next_heading else None].strip()
    return ""


def parse_profile(wikitext: str) -> tuple[dict, list[tuple[str, str]], list[tuple[str, str, str]]]:
    fields: dict[str, str] = {}
    info = re.search(r"\{\{角色信息\s*(.*?)\n\}\}", wikitext, flags=re.DOTALL)
    if info:
        for line in info.group(1).splitlines():
            if line.startswith("|") and "=" in line:
                key, value = line[1:].split("=", 1)
                if key.strip() not in {"图片1", "标签1"}:
                    fields[key.strip()] = _strip_markup(value)

    introduction = _section(wikitext, [r"(?m)^='''角色介绍'''=\s*$", r"(?m)^=角色介绍=\s*$"])
    encounter = _section(wikitext, [r"(?m)^='''羁遇资料'''=\s*$", r"(?m)^=羁遇资料=\s*$"])
    fields["角色介绍"] = _strip_markup(introduction)
    fields["羁遇资料"] = _strip_markup(encounter)

    archive_entries = []
    archive = re.search(r"\{\{角色档案\s*(.*?)\n\}\}", wikitext, flags=re.DOTALL)
    if archive:
        pattern = re.compile(
            r"\|按钮(\d+)\s*=\s*(.*?)\n\|内容\1\s*=\s*<nowiki>(.*?)</nowiki>",
            flags=re.DOTALL,
        )
        for _, title, content in pattern.findall(archive.group(0)):
            archive_entries.append((_strip_markup(title), content.strip()))

    voice_lines: list[tuple[str, str, str]] = []
    voice_start = re.search(r"(?m)^==语音记录（文本）==\s*$", wikitext)
    if voice_start:
        voice_text = wikitext[voice_start.end() :]
        end = re.search(r"(?m)^='''[^']+'''=\s*$", voice_text)
        voice_text = voice_text[: end.start() if end else None]
        category = "未分类"
        for line in voice_text.splitlines():
            category_match = re.match(r"^===([^=]+)===$", line.strip())
            if category_match:
                category = _strip_markup(category_match.group(1))
                continue
            if line.startswith("|") and "||" in line:
                label, text = line[1:].split("||", 1)
                label, text = _strip_markup(label), _strip_markup(text)
                if label and text:
                    voice_lines.append((category, label, text))
    return fields, archive_entries, voice_lines


def sync_ntestation(root: Path) -> dict[str, int]:
    root.mkdir(parents=True, exist_ok=True)
    cache = root / ".cache" / "ntestation"
    cache.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc)
    headers = {"User-Agent": "AfterStory-character-research/0.1 (local research corpus)"}
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
        name_page = _query_pages(client, ["角色名称表"])[0]
        name_text = _wiki_text(name_page)
        (cache / "character-name-table.wiki").write_text(
            name_text, encoding="utf-8", newline="\n"
        )
        catalog = parse_name_table(name_text)
        existing_catalog = (
            {item.character_id: item for item in load_catalog(root)}
            if (root / "catalog.json").exists()
            else {}
        )
        for entry in catalog:
            existing = existing_catalog.get(entry.character_id)
            if existing and existing.research_status not in {"discovered", "profile_collected"}:
                entry.research_status = existing.research_status
        known_character_ids = {item.character_id for item in catalog}
        catalog.extend(
            entry for key, entry in existing_catalog.items() if key not in known_character_ids
        )
        pages: dict[str, dict] = {}
        titles = [entry.names.zh for entry in catalog]
        for start in range(0, len(titles), 10):
            for page in _query_pages(client, titles[start : start + 10]):
                pages[page["title"]] = page

    existing_sources = read_jsonl(root / "sources.jsonl", SourceRecord)
    existing_sources_by_id = {source.source_id: source for source in existing_sources}
    sources = [
        source
        for source in existing_sources
        if source.platform != "ntestation"
    ]
    profiles = [
        profile
        for profile in read_jsonl(root / "profiles.jsonl", ProfileIndexRecord)
        if not profile.source_id.startswith("ntestation-")
    ]
    collected = 0
    for entry in catalog:
        page = pages.get(entry.names.zh, {"title": entry.names.zh, "missing": True})
        text = _wiki_text(page)
        source_id = f"ntestation-{entry.character_id}"
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""
        cache_path = f".cache/ntestation/{entry.character_id}.wiki" if text else ""
        revision = (page.get("revisions") or [{}])[0]
        previous_source = existing_sources_by_id.get(source_id)
        source_retrieved_at = retrieved_at
        if (
            previous_source
            and previous_source.revision_id == revision.get("revid")
            and previous_source.content_hash == content_hash
        ):
            source_retrieved_at = previous_source.retrieved_at
        sources.append(
            SourceRecord(
                source_id=source_id,
                source_type="profile_archive_mirror",
                provenance="in_game_archive_mirror",
                platform="ntestation",
                title=f"{entry.names.zh}角色个人档案",
                url=NTESTATION_BASE + quote(entry.names.zh),
                page_title=entry.names.zh,
                revision_id=revision.get("revid"),
                revision_timestamp=revision.get("timestamp"),
                retrieved_at=source_retrieved_at,
                content_hash=content_hash,
                raw_cache_path=cache_path,
                status="available" if text else "missing",
            )
        )
        if not text:
            continue
        (root / cache_path).write_text(text, encoding="utf-8", newline="\n")
        fields, archive_entries, voice_lines = parse_profile(text)
        counts: dict[str, int] = {}
        for category, _, _ in voice_lines:
            counts[category] = counts.get(category, 0) + 1
        profiles.append(
            ProfileIndexRecord(
                profile_id=f"{entry.character_id}-ntestation-r{revision['revid']}",
                character_id=entry.character_id,
                source_id=source_id,
                source_revision_id=revision["revid"],
                content_hash=content_hash,
                fields={
                    key: value
                    for key, value in fields.items()
                    if value and key not in {"角色介绍", "羁遇资料"}
                },
                has_character_introduction=bool(fields.get("角色介绍")),
                has_encounter_profile=bool(fields.get("羁遇资料")),
                archive_entry_titles=[title for title, _ in archive_entries],
                voice_category_counts=counts,
            )
        )
        if entry.research_status == "discovered":
            entry.research_status = "profile_collected"
        collected += 1

    write_catalog(root, catalog)
    write_jsonl(root / "sources.jsonl", sources)
    write_jsonl(root / "profiles.jsonl", profiles)
    for filename in (
        "scenes.jsonl",
        "evidence.jsonl",
        "traits.jsonl",
        "canon_checkpoints.jsonl",
        "canon_evidence.jsonl",
        "world_entities.jsonl",
        "character_facts.jsonl",
        "world_facts.jsonl",
        "character_relations.jsonl",
    ):
        path = root / filename
        if not path.exists():
            path.write_text("", encoding="utf-8")
    validate_corpus(root)
    return {
        "characters": len(catalog),
        "profiles": collected,
        "missing_profiles": len(catalog) - collected,
    }


def _story_content_type(title: str) -> Literal["main_story", "side_story", "unknown"]:
    if title.startswith("番外"):
        return "side_story"
    if title.startswith("第"):
        return "main_story"
    return "unknown"


def sync_bilibili(root: Path, bvid: str) -> dict[str, int | str]:
    if not re.fullmatch(r"BV[0-9A-Za-z]+", bvid):
        raise ValueError("Invalid Bilibili BV id")
    root.mkdir(parents=True, exist_ok=True)
    url = f"https://www.bilibili.com/video/{bvid}/"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": url}
    existing_parts = read_jsonl(root / "source_parts.jsonl", SourcePartRecord)
    existing_parts_by_id = {item.part_id: item for item in existing_parts}
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as client:
        response = client.get(
            "https://api.bilibili.com/x/web-interface/view", params={"bvid": bvid}
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise ValueError(f"Bilibili metadata error: {payload.get('message')}")
        data = payload["data"]
        parts = []
        platform_subtitle_parts = 0
        for page in data.get("pages", []):
            player = client.get(
                "https://api.bilibili.com/x/player/v2",
                params={"bvid": bvid, "cid": page["cid"]},
            )
            player.raise_for_status()
            player_data = player.json().get("data") or {}
            subtitles = (player_data.get("subtitle") or {}).get("subtitles") or []
            subtitle_mode = "platform_subtitles" if subtitles else "no_platform_subtitles"
            platform_subtitle_parts += int(bool(subtitles))
            part_id = f"bilibili-{bvid}-p{page['page']:02}"
            previous_part = existing_parts_by_id.get(part_id)
            processing_status = "indexed"
            if (
                previous_part
                and previous_part.external_part_id == str(page["cid"])
                and previous_part.duration_ms == page["duration"] * 1000
            ):
                processing_status = previous_part.processing_status
            parts.append(
                SourcePartRecord(
                    part_id=part_id,
                    source_id=f"bilibili-{bvid}",
                    external_part_id=str(page["cid"]),
                    position=page["page"],
                    title=page["part"],
                    duration_ms=page["duration"] * 1000,
                    content_type=_story_content_type(page["part"]),
                    subtitle_mode=subtitle_mode,
                    visual_subtitle_status=(
                        previous_part.visual_subtitle_status if previous_part else "unknown"
                    ),
                    processing_status=processing_status,
                )
            )

    sources = read_jsonl(root / "sources.jsonl", SourceRecord)
    existing_source = next((item for item in sources if item.source_id == f"bilibili-{bvid}"), None)
    retrieved_at = datetime.now(timezone.utc)
    published_at = datetime.fromtimestamp(data["pubdate"], timezone.utc)
    source = SourceRecord(
        source_id=f"bilibili-{bvid}",
        source_type="story_video",
        provenance="in_game_footage",
        platform="bilibili",
        title=data["title"],
        url=url,
        retrieved_at=existing_source.retrieved_at if existing_source else retrieved_at,
        status="indexed",
        external_id=bvid,
        creator=(data.get("owner") or {}).get("name", ""),
        published_at=published_at,
        duration_ms=data["duration"] * 1000,
        part_count=data["videos"],
        content_checkpoint="through-1.4" if "1.4" in data["title"] else "",
        subtitle_mode=(
            "platform_subtitles"
            if platform_subtitle_parts == len(parts) and parts
            else "no_platform_subtitles"
        ),
        visual_subtitle_status=(
            existing_source.visual_subtitle_status if existing_source else "unknown"
        ),
        notes=data.get("desc", ""),
    )
    sources = [item for item in sources if item.source_id != source.source_id] + [source]
    all_parts = [item for item in existing_parts if item.source_id != source.source_id] + parts
    write_jsonl(root / "sources.jsonl", sources)
    write_jsonl(root / "source_parts.jsonl", all_parts)
    stats = validate_corpus(root)
    return {
        "source_id": source.source_id,
        "parts": len(parts),
        "duration_ms": data["duration"] * 1000,
        "platform_subtitle_parts": platform_subtitle_parts,
        "total_sources": stats["sources"],
    }


def validate_corpus(root: Path) -> dict[str, int]:
    catalog = load_catalog(root)
    sources = read_jsonl(root / "sources.jsonl", SourceRecord)
    source_parts = read_jsonl(root / "source_parts.jsonl", SourcePartRecord)
    profiles = read_jsonl(root / "profiles.jsonl", ProfileIndexRecord)
    scenes = read_jsonl(root / "scenes.jsonl", SceneRecord)
    evidence = read_jsonl(root / "evidence.jsonl", EvidenceRecord)
    traits = read_jsonl(root / "traits.jsonl", TraitRecord)
    checkpoints = read_jsonl(root / "canon_checkpoints.jsonl", CanonCheckpointRecord)
    canon_evidence = read_jsonl(root / "canon_evidence.jsonl", CanonEvidenceRecord)
    world_entities = read_jsonl(root / "world_entities.jsonl", WorldEntityRecord)
    character_facts = read_jsonl(root / "character_facts.jsonl", CharacterFactRecord)
    world_facts = read_jsonl(root / "world_facts.jsonl", WorldFactRecord)
    character_relations = read_jsonl(
        root / "character_relations.jsonl", CharacterRelationRecord
    )

    def unique(records, field):
        values = [getattr(record, field) for record in records]
        if len(values) != len(set(values)):
            raise ValueError(f"Duplicate {field}")
        return set(values)

    characters = unique(catalog, "character_id")
    source_ids = unique(sources, "source_id")
    source_part_ids = unique(source_parts, "part_id")
    profile_ids = unique(profiles, "profile_id")
    scene_ids = unique(scenes, "scene_id")
    evidence_ids = unique(evidence, "evidence_id")
    unique(traits, "trait_id")
    checkpoint_ids = unique(checkpoints, "checkpoint_id")
    canon_evidence_ids = unique(canon_evidence, "canon_evidence_id")
    world_entity_ids = unique(world_entities, "world_entity_id")
    character_fact_ids = unique(character_facts, "fact_id")
    world_fact_ids = unique(world_facts, "fact_id")
    relation_ids = unique(character_relations, "relation_id")

    character_by_id = {item.character_id: item for item in catalog}
    part_by_id = {item.part_id: item for item in source_parts}
    profile_by_id = {item.profile_id: item for item in profiles}
    scene_by_id = {item.scene_id: item for item in scenes}
    checkpoint_by_id = {item.checkpoint_id: item for item in checkpoints}
    canon_evidence_by_id = {item.canon_evidence_id: item for item in canon_evidence}
    world_entity_by_id = {item.world_entity_id: item for item in world_entities}

    def reject_duplicates(values, label):
        if len(values) != len(set(values)):
            raise ValueError(f"Duplicate {label}")

    reject_duplicates(
        [(item.source_work, item.sequence) for item in checkpoints], "checkpoint sequence"
    )

    def require_checkpoint(checkpoint_id, label, *, allow_empty=False):
        if not checkpoint_id and allow_empty:
            return
        if checkpoint_id not in checkpoint_ids:
            raise ValueError(f"Broken checkpoint reference: {label}")

    def validate_checkpoint_range(record_id, observed, valid_from, valid_to):
        require_checkpoint(observed, record_id)
        require_checkpoint(valid_from, record_id, allow_empty=True)
        require_checkpoint(valid_to, record_id, allow_empty=True)
        observed_checkpoint = checkpoint_by_id[observed]
        for checkpoint_id in (valid_from, valid_to):
            if (
                checkpoint_id
                and checkpoint_by_id[checkpoint_id].source_work
                != observed_checkpoint.source_work
            ):
                raise ValueError(f"Invalid checkpoint range: {record_id}")
        if valid_from and valid_to:
            start = checkpoint_by_id[valid_from]
            end = checkpoint_by_id[valid_to]
            if start.source_work != end.source_work or start.sequence > end.sequence:
                raise ValueError(f"Invalid checkpoint range: {record_id}")

    def canon_evidence_source_work(evidence_id):
        item = canon_evidence_by_id[evidence_id]
        if item.origin_type == "scene":
            scene = scene_by_id[item.scene_id]
            return checkpoint_by_id[scene.canon_checkpoint].source_work
        profile = profile_by_id[item.profile_id]
        return character_by_id[profile.character_id].source_work

    def validate_evidence_links(record_id, linked_ids, review_status, source_work):
        reject_duplicates(linked_ids, f"evidence reference: {record_id}")
        if not set(linked_ids) <= canon_evidence_ids:
            raise ValueError(f"Broken canon evidence reference: {record_id}")
        if any(canon_evidence_source_work(item) != source_work for item in linked_ids):
            raise ValueError(f"Canon evidence work mismatch: {record_id}")
        if review_status == "accepted":
            if not linked_ids:
                raise ValueError(f"Accepted record requires evidence: {record_id}")
            if any(canon_evidence_by_id[item].review_status != "accepted" for item in linked_ids):
                raise ValueError(f"Accepted record requires accepted evidence: {record_id}")

    def reject_reference_cycles(records, id_field, parent_field, label):
        parents = {
            getattr(record, id_field): getattr(record, parent_field)
            for record in records
            if getattr(record, parent_field)
        }
        for start in parents:
            seen = set()
            current = start
            while current in parents:
                if current in seen:
                    raise ValueError(f"Cyclic {label}: {start}")
                seen.add(current)
                current = parents[current]

    for profile in profiles:
        if profile.character_id not in characters or profile.source_id not in source_ids:
            raise ValueError(f"Broken profile reference: {profile.profile_id}")
    reject_duplicates(
        [(part.source_id, part.position) for part in source_parts], "source part position"
    )
    for part in source_parts:
        if part.source_id not in source_ids:
            raise ValueError(f"Broken source part reference: {part.part_id}")
    for checkpoint in checkpoints:
        if checkpoint.predecessor_id:
            predecessor = checkpoint_by_id.get(checkpoint.predecessor_id)
            if (
                predecessor is None
                or predecessor.source_work != checkpoint.source_work
                or predecessor.sequence >= checkpoint.sequence
            ):
                raise ValueError(f"Broken checkpoint predecessor: {checkpoint.checkpoint_id}")
    reject_reference_cycles(checkpoints, "checkpoint_id", "predecessor_id", "checkpoint chain")
    for scene in scenes:
        part = part_by_id.get(scene.source_part_id)
        if (
            scene.source_id not in source_ids
            or scene.source_part_id not in source_part_ids
            or part is None
            or part.source_id != scene.source_id
            or not set(scene.participants) <= characters
        ):
            raise ValueError(f"Broken scene reference: {scene.scene_id}")
        reject_duplicates(scene.participants, f"scene participant: {scene.scene_id}")
        require_checkpoint(scene.canon_checkpoint, scene.scene_id)
        if scene.end_ms <= scene.start_ms or scene.end_ms > part.duration_ms:
            raise ValueError(f"Invalid scene range: {scene.scene_id}")
    for item in evidence:
        if item.scene_id not in scene_ids or item.character_id not in characters:
            raise ValueError(f"Broken evidence reference: {item.evidence_id}")
    for trait in traits:
        if trait.character_id not in characters or not set(trait.evidence_ids) <= evidence_ids:
            raise ValueError(f"Broken trait reference: {trait.trait_id}")
    for item in canon_evidence:
        if not set(item.actor_character_ids) <= characters or (
            item.speaker_character_id and item.speaker_character_id not in characters
        ):
            raise ValueError(f"Broken canon evidence reference: {item.canon_evidence_id}")
        reject_duplicates(
            item.actor_character_ids, f"canon evidence actor: {item.canon_evidence_id}"
        )
        reject_duplicates(item.transcript_refs, f"transcript reference: {item.canon_evidence_id}")
        if item.origin_type == "scene":
            scene = scene_by_id.get(item.scene_id)
            if scene is None or item.source_part_id != scene.source_part_id:
                raise ValueError(f"Broken canon evidence reference: {item.canon_evidence_id}")
            if not set(item.actor_character_ids) <= set(scene.participants) or (
                item.speaker_character_id
                and item.speaker_character_id not in scene.participants
            ):
                raise ValueError(f"Canon evidence scene mismatch: {item.canon_evidence_id}")
            if (
                item.start_ms is None
                or item.end_ms is None
                or item.start_ms < scene.start_ms
                or item.end_ms > scene.end_ms
                or item.end_ms <= item.start_ms
            ):
                raise ValueError(f"Invalid canon evidence range: {item.canon_evidence_id}")
            if item.review_status == "accepted" and scene.review_status != "reviewed":
                raise ValueError(
                    f"Accepted canon evidence requires reviewed scene: {item.canon_evidence_id}"
                )
        else:
            profile = profile_by_id.get(item.profile_id)
            if profile is None:
                raise ValueError(f"Broken canon evidence reference: {item.canon_evidence_id}")
            if item.actor_character_ids and set(item.actor_character_ids) != {
                profile.character_id
            }:
                raise ValueError(f"Profile evidence character mismatch: {item.canon_evidence_id}")
            if (
                item.speaker_character_id
                and item.speaker_character_id != profile.character_id
            ):
                raise ValueError(f"Profile evidence character mismatch: {item.canon_evidence_id}")
    for entity in world_entities:
        require_checkpoint(entity.first_checkpoint, entity.world_entity_id)
        if checkpoint_by_id[entity.first_checkpoint].source_work != entity.source_work:
            raise ValueError(f"World entity checkpoint mismatch: {entity.world_entity_id}")
        reject_duplicates(entity.aliases, f"world entity alias: {entity.world_entity_id}")
        validate_evidence_links(
            entity.world_entity_id,
            entity.evidence_ids,
            entity.review_status,
            entity.source_work,
        )
    character_fact_by_id = {item.fact_id: item for item in character_facts}
    for fact in character_facts:
        if fact.character_id not in characters or (
            fact.value_entity_id and fact.value_entity_id not in world_entity_ids
        ):
            raise ValueError(f"Broken character fact reference: {fact.fact_id}")
        validate_checkpoint_range(
            fact.fact_id,
            fact.canon_checkpoint,
            fact.valid_from_checkpoint,
            fact.valid_to_checkpoint,
        )
        if checkpoint_by_id[fact.canon_checkpoint].source_work != character_by_id[
            fact.character_id
        ].source_work:
            raise ValueError(f"Character fact checkpoint mismatch: {fact.fact_id}")
        if (
            fact.value_entity_id
            and world_entity_by_id[fact.value_entity_id].source_work
            != character_by_id[fact.character_id].source_work
        ):
            raise ValueError(f"Character fact work mismatch: {fact.fact_id}")
        validate_evidence_links(
            fact.fact_id,
            fact.evidence_ids,
            fact.review_status,
            character_by_id[fact.character_id].source_work,
        )
        if fact.supersedes_id:
            previous = character_fact_by_id.get(fact.supersedes_id)
            if previous is None or previous.character_id != fact.character_id:
                raise ValueError(f"Broken character fact supersedes reference: {fact.fact_id}")
    reject_reference_cycles(character_facts, "fact_id", "supersedes_id", "character fact chain")
    world_fact_by_id = {item.fact_id: item for item in world_facts}
    for fact in world_facts:
        if (
            fact.subject_entity_id not in world_entity_ids
            or (fact.object_entity_id and fact.object_entity_id not in world_entity_ids)
            or (
                fact.perspective_character_id
                and fact.perspective_character_id not in characters
            )
        ):
            raise ValueError(f"Broken world fact reference: {fact.fact_id}")
        validate_checkpoint_range(
            fact.fact_id,
            fact.canon_checkpoint,
            fact.valid_from_checkpoint,
            fact.valid_to_checkpoint,
        )
        subject = world_entity_by_id[fact.subject_entity_id]
        if checkpoint_by_id[fact.canon_checkpoint].source_work != subject.source_work:
            raise ValueError(f"World fact checkpoint mismatch: {fact.fact_id}")
        if (
            fact.object_entity_id
            and world_entity_by_id[fact.object_entity_id].source_work != subject.source_work
        ) or (
            fact.perspective_character_id
            and character_by_id[fact.perspective_character_id].source_work != subject.source_work
        ):
            raise ValueError(f"World fact work mismatch: {fact.fact_id}")
        validate_evidence_links(
            fact.fact_id, fact.evidence_ids, fact.review_status, subject.source_work
        )
        if fact.supersedes_id:
            previous = world_fact_by_id.get(fact.supersedes_id)
            if previous is None or previous.subject_entity_id != fact.subject_entity_id:
                raise ValueError(f"Broken world fact supersedes reference: {fact.fact_id}")
    reject_reference_cycles(world_facts, "fact_id", "supersedes_id", "world fact chain")
    relation_by_id = {item.relation_id: item for item in character_relations}
    for relation in character_relations:
        if (
            relation.source_character_id not in characters
            or relation.target_character_id not in characters
        ):
            raise ValueError(f"Broken character relation reference: {relation.relation_id}")
        validate_checkpoint_range(
            relation.relation_id,
            relation.canon_checkpoint,
            relation.valid_from_checkpoint,
            relation.valid_to_checkpoint,
        )
        source_work = character_by_id[relation.source_character_id].source_work
        if (
            character_by_id[relation.target_character_id].source_work != source_work
            or checkpoint_by_id[relation.canon_checkpoint].source_work != source_work
        ):
            raise ValueError(f"Character relation work mismatch: {relation.relation_id}")
        validate_evidence_links(
            relation.relation_id,
            relation.evidence_ids,
            relation.review_status,
            source_work,
        )
        if relation.supersedes_id:
            previous = relation_by_id.get(relation.supersedes_id)
            if previous is None or {
                previous.source_character_id,
                previous.target_character_id,
            } != {relation.source_character_id, relation.target_character_id}:
                raise ValueError(
                    f"Broken character relation supersedes reference: {relation.relation_id}"
                )
    reject_reference_cycles(
        character_relations, "relation_id", "supersedes_id", "character relation chain"
    )
    return {
        "characters": len(characters),
        "sources": len(source_ids),
        "source_parts": len(source_parts),
        "profiles": len(profile_ids),
        "scenes": len(scene_ids),
        "evidence": len(evidence_ids),
        "traits": len(traits),
        "canon_checkpoints": len(checkpoint_ids),
        "canon_evidence": len(canon_evidence_ids),
        "world_entities": len(world_entity_ids),
        "character_facts": len(character_fact_ids),
        "world_facts": len(world_fact_ids),
        "character_relations": len(relation_ids),
    }


def build_sqlite(root: Path, destination: Path) -> dict[str, int]:
    stats = validate_corpus(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE characters (
                character_id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
                names_json TEXT NOT NULL, source_work TEXT NOT NULL, research_status TEXT NOT NULL
            );
            CREATE TABLE sources (
                source_id TEXT PRIMARY KEY, source_type TEXT NOT NULL, provenance TEXT NOT NULL,
                platform TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL,
                page_title TEXT, revision_id INTEGER, revision_timestamp TEXT,
                retrieved_at TEXT NOT NULL, content_hash TEXT, status TEXT NOT NULL,
                raw_wikitext TEXT, external_id TEXT, creator TEXT, published_at TEXT,
                duration_ms INTEGER, part_count INTEGER, content_checkpoint TEXT,
                subtitle_mode TEXT NOT NULL, visual_subtitle_status TEXT NOT NULL,
                notes TEXT NOT NULL
            );
            CREATE TABLE source_parts (
                part_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources,
                external_part_id TEXT NOT NULL, position INTEGER NOT NULL, title TEXT NOT NULL,
                duration_ms INTEGER NOT NULL, content_type TEXT NOT NULL,
                subtitle_mode TEXT NOT NULL, visual_subtitle_status TEXT NOT NULL,
                processing_status TEXT NOT NULL,
                UNIQUE (source_id, position)
            );
            CREATE TABLE profiles (
                profile_id TEXT PRIMARY KEY, character_id TEXT NOT NULL REFERENCES characters,
                source_id TEXT NOT NULL REFERENCES sources, source_revision_id INTEGER NOT NULL,
                content_hash TEXT NOT NULL, fields_json TEXT NOT NULL
            );
            CREATE TABLE profile_archive_entries (
                profile_id TEXT NOT NULL REFERENCES profiles, position INTEGER NOT NULL,
                title TEXT NOT NULL, content TEXT NOT NULL,
                PRIMARY KEY (profile_id, position)
            );
            CREATE TABLE profile_voice_lines (
                profile_id TEXT NOT NULL REFERENCES profiles, position INTEGER NOT NULL,
                category TEXT NOT NULL, label TEXT NOT NULL, text TEXT NOT NULL,
                PRIMARY KEY (profile_id, position)
            );
            CREATE TABLE canon_checkpoints (
                checkpoint_id TEXT PRIMARY KEY, source_work TEXT NOT NULL,
                display_name TEXT NOT NULL, sequence INTEGER NOT NULL,
                game_version TEXT NOT NULL, chapter TEXT NOT NULL,
                predecessor_id TEXT REFERENCES canon_checkpoints,
                spoiler_scope TEXT NOT NULL,
                UNIQUE (source_work, sequence)
            );
            CREATE TABLE scenes (
                scene_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources,
                source_part_id TEXT NOT NULL REFERENCES source_parts,
                start_ms INTEGER NOT NULL, end_ms INTEGER NOT NULL, chapter TEXT NOT NULL,
                summary TEXT NOT NULL,
                canon_checkpoint TEXT NOT NULL REFERENCES canon_checkpoints,
                review_status TEXT NOT NULL
            );
            CREATE TABLE scene_participants (
                scene_id TEXT NOT NULL REFERENCES scenes,
                character_id TEXT NOT NULL REFERENCES characters,
                PRIMARY KEY (scene_id, character_id)
            );
            CREATE TABLE evidence (
                evidence_id TEXT PRIMARY KEY, scene_id TEXT NOT NULL REFERENCES scenes,
                character_id TEXT NOT NULL REFERENCES characters, observation TEXT NOT NULL,
                interpretation TEXT NOT NULL, confidence TEXT NOT NULL, limitations TEXT NOT NULL,
                affected_fields_json TEXT NOT NULL
            );
            CREATE TABLE traits (
                trait_id TEXT PRIMARY KEY, character_id TEXT NOT NULL REFERENCES characters,
                name TEXT NOT NULL, importance TEXT NOT NULL, frequency TEXT NOT NULL,
                review_status TEXT NOT NULL, triggers_json TEXT NOT NULL,
                expressions_json TEXT NOT NULL, boundaries_json TEXT NOT NULL,
                prompt_summary TEXT NOT NULL
            );
            CREATE TABLE trait_evidence (
                trait_id TEXT NOT NULL REFERENCES traits,
                evidence_id TEXT NOT NULL REFERENCES evidence,
                PRIMARY KEY (trait_id, evidence_id)
            );
            CREATE TABLE canon_evidence (
                canon_evidence_id TEXT PRIMARY KEY, origin_type TEXT NOT NULL,
                scene_id TEXT REFERENCES scenes, profile_id TEXT REFERENCES profiles,
                source_part_id TEXT REFERENCES source_parts,
                start_ms INTEGER, end_ms INTEGER, profile_locator TEXT,
                evidence_kind TEXT NOT NULL,
                speaker_character_id TEXT REFERENCES characters,
                observation TEXT NOT NULL, review_status TEXT NOT NULL,
                review_notes TEXT NOT NULL,
                CHECK (
                    (origin_type = 'scene' AND scene_id IS NOT NULL
                        AND source_part_id IS NOT NULL AND start_ms IS NOT NULL
                        AND end_ms IS NOT NULL AND profile_id IS NULL)
                    OR
                    (origin_type = 'profile' AND profile_id IS NOT NULL
                        AND scene_id IS NULL AND source_part_id IS NULL
                        AND start_ms IS NULL AND end_ms IS NULL)
                )
            );
            CREATE TABLE canon_evidence_actors (
                canon_evidence_id TEXT NOT NULL REFERENCES canon_evidence,
                character_id TEXT NOT NULL REFERENCES characters,
                PRIMARY KEY (canon_evidence_id, character_id)
            );
            CREATE TABLE canon_evidence_transcripts (
                canon_evidence_id TEXT NOT NULL REFERENCES canon_evidence,
                position INTEGER NOT NULL, transcript_ref TEXT NOT NULL,
                PRIMARY KEY (canon_evidence_id, position),
                UNIQUE (canon_evidence_id, transcript_ref)
            );
            CREATE TABLE world_entities (
                world_entity_id TEXT PRIMARY KEY, source_work TEXT NOT NULL,
                entity_type TEXT NOT NULL, names_json TEXT NOT NULL,
                aliases_json TEXT NOT NULL, summary TEXT NOT NULL,
                first_checkpoint TEXT NOT NULL REFERENCES canon_checkpoints,
                review_status TEXT NOT NULL
            );
            CREATE TABLE world_entity_evidence (
                world_entity_id TEXT NOT NULL REFERENCES world_entities,
                canon_evidence_id TEXT NOT NULL REFERENCES canon_evidence,
                PRIMARY KEY (world_entity_id, canon_evidence_id)
            );
            CREATE TABLE character_facts (
                fact_id TEXT PRIMARY KEY, character_id TEXT NOT NULL REFERENCES characters,
                fact_type TEXT NOT NULL, value_text TEXT,
                value_entity_id TEXT REFERENCES world_entities,
                canon_checkpoint TEXT NOT NULL REFERENCES canon_checkpoints,
                valid_from_checkpoint TEXT REFERENCES canon_checkpoints,
                valid_to_checkpoint TEXT REFERENCES canon_checkpoints,
                confidence TEXT NOT NULL, review_status TEXT NOT NULL,
                supersedes_id TEXT REFERENCES character_facts,
                CHECK ((value_text IS NULL) <> (value_entity_id IS NULL))
            );
            CREATE TABLE character_fact_evidence (
                fact_id TEXT NOT NULL REFERENCES character_facts,
                canon_evidence_id TEXT NOT NULL REFERENCES canon_evidence,
                PRIMARY KEY (fact_id, canon_evidence_id)
            );
            CREATE TABLE world_facts (
                fact_id TEXT PRIMARY KEY,
                subject_entity_id TEXT NOT NULL REFERENCES world_entities,
                predicate TEXT NOT NULL, object_entity_id TEXT REFERENCES world_entities,
                object_text TEXT, fact_scope TEXT NOT NULL,
                perspective_character_id TEXT REFERENCES characters,
                canon_checkpoint TEXT NOT NULL REFERENCES canon_checkpoints,
                valid_from_checkpoint TEXT REFERENCES canon_checkpoints,
                valid_to_checkpoint TEXT REFERENCES canon_checkpoints,
                confidence TEXT NOT NULL, review_status TEXT NOT NULL,
                supersedes_id TEXT REFERENCES world_facts,
                CHECK ((object_text IS NULL) <> (object_entity_id IS NULL))
            );
            CREATE TABLE world_fact_evidence (
                fact_id TEXT NOT NULL REFERENCES world_facts,
                canon_evidence_id TEXT NOT NULL REFERENCES canon_evidence,
                PRIMARY KEY (fact_id, canon_evidence_id)
            );
            CREATE TABLE character_relations (
                relation_id TEXT PRIMARY KEY,
                source_character_id TEXT NOT NULL REFERENCES characters,
                target_character_id TEXT NOT NULL REFERENCES characters,
                category TEXT NOT NULL, label TEXT NOT NULL, directionality TEXT NOT NULL,
                summary TEXT NOT NULL,
                canon_checkpoint TEXT NOT NULL REFERENCES canon_checkpoints,
                valid_from_checkpoint TEXT REFERENCES canon_checkpoints,
                valid_to_checkpoint TEXT REFERENCES canon_checkpoints,
                confidence TEXT NOT NULL, review_status TEXT NOT NULL,
                supersedes_id TEXT REFERENCES character_relations,
                CHECK (source_character_id <> target_character_id)
            );
            CREATE TABLE character_relation_evidence (
                relation_id TEXT NOT NULL REFERENCES character_relations,
                canon_evidence_id TEXT NOT NULL REFERENCES canon_evidence,
                PRIMARY KEY (relation_id, canon_evidence_id)
            );
            CREATE INDEX ix_scenes_checkpoint ON scenes (canon_checkpoint);
            CREATE INDEX ix_character_facts_character ON character_facts (character_id);
            CREATE INDEX ix_world_facts_subject ON world_facts (subject_entity_id);
            CREATE INDEX ix_character_relations_source ON character_relations (source_character_id);
            CREATE INDEX ix_character_relations_target ON character_relations (target_character_id);
            """
        )
        connection.execute(
            "INSERT INTO metadata VALUES (?, ?)",
            ("schema_version", CHARACTER_RESEARCH_SCHEMA_VERSION),
        )
        catalog = load_catalog(root)
        sources = read_jsonl(root / "sources.jsonl", SourceRecord)
        profiles = read_jsonl(root / "profiles.jsonl", ProfileIndexRecord)
        checkpoints = read_jsonl(root / "canon_checkpoints.jsonl", CanonCheckpointRecord)
        for character in catalog:
            connection.execute(
                "INSERT INTO characters VALUES (?, ?, ?, ?, ?)",
                (
                    character.character_id,
                    character.names.zh,
                    character.names.model_dump_json(),
                    character.source_work,
                    character.research_status,
                ),
            )
        parsed_by_source = {}
        for source in sources:
            raw = ""
            if source.raw_cache_path:
                path = root / source.raw_cache_path
                if path.exists():
                    raw = path.read_text(encoding="utf-8")
                    parsed_by_source[source.source_id] = parse_profile(raw)
            connection.execute(
                "INSERT INTO sources VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    source.source_id,
                    source.source_type,
                    source.provenance,
                    source.platform,
                    source.title,
                    str(source.url),
                    source.page_title,
                    source.revision_id,
                    source.revision_timestamp.isoformat() if source.revision_timestamp else None,
                    source.retrieved_at.isoformat(),
                    source.content_hash,
                    source.status,
                    raw,
                    source.external_id,
                    source.creator,
                    source.published_at.isoformat() if source.published_at else None,
                    source.duration_ms,
                    source.part_count,
                    source.content_checkpoint,
                    source.subtitle_mode,
                    source.visual_subtitle_status,
                    source.notes,
                ),
            )
        for part in read_jsonl(root / "source_parts.jsonl", SourcePartRecord):
            connection.execute(
                "INSERT INTO source_parts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    part.part_id,
                    part.source_id,
                    part.external_part_id,
                    part.position,
                    part.title,
                    part.duration_ms,
                    part.content_type,
                    part.subtitle_mode,
                    part.visual_subtitle_status,
                    part.processing_status,
                ),
            )
        for profile in profiles:
            parsed = parsed_by_source.get(profile.source_id)
            local_fields = parsed[0] if parsed else profile.fields
            connection.execute(
                "INSERT INTO profiles VALUES (?, ?, ?, ?, ?, ?)",
                (
                    profile.profile_id,
                    profile.character_id,
                    profile.source_id,
                    profile.source_revision_id,
                    profile.content_hash,
                    json.dumps(local_fields, ensure_ascii=False),
                ),
            )
            if parsed:
                _, archives, voice_lines = parsed
                connection.executemany(
                    "INSERT INTO profile_archive_entries VALUES (?, ?, ?, ?)",
                    [
                        (profile.profile_id, position, title, content)
                        for position, (title, content) in enumerate(archives, 1)
                    ],
                )
                connection.executemany(
                    "INSERT INTO profile_voice_lines VALUES (?, ?, ?, ?, ?)",
                    [
                        (profile.profile_id, position, category, label, text)
                        for position, (category, label, text) in enumerate(voice_lines, 1)
                    ],
                )
        for checkpoint in checkpoints:
            connection.execute(
                "INSERT INTO canon_checkpoints VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    checkpoint.checkpoint_id,
                    checkpoint.source_work,
                    checkpoint.display_name,
                    checkpoint.sequence,
                    checkpoint.game_version,
                    checkpoint.chapter,
                    None,
                    checkpoint.spoiler_scope,
                ),
            )
        for checkpoint in checkpoints:
            if checkpoint.predecessor_id:
                connection.execute(
                    "UPDATE canon_checkpoints SET predecessor_id = ? WHERE checkpoint_id = ?",
                    (checkpoint.predecessor_id, checkpoint.checkpoint_id),
                )
        for scene in read_jsonl(root / "scenes.jsonl", SceneRecord):
            connection.execute(
                "INSERT INTO scenes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    scene.scene_id,
                    scene.source_id,
                    scene.source_part_id,
                    scene.start_ms,
                    scene.end_ms,
                    scene.chapter,
                    scene.summary,
                    scene.canon_checkpoint,
                    scene.review_status,
                ),
            )
            connection.executemany(
                "INSERT INTO scene_participants VALUES (?, ?)",
                [(scene.scene_id, character_id) for character_id in scene.participants],
            )
        for item in read_jsonl(root / "evidence.jsonl", EvidenceRecord):
            connection.execute(
                "INSERT INTO evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.evidence_id,
                    item.scene_id,
                    item.character_id,
                    item.observation,
                    item.interpretation,
                    item.confidence,
                    item.limitations,
                    json.dumps(item.affected_fields, ensure_ascii=False),
                ),
            )
        for trait in read_jsonl(root / "traits.jsonl", TraitRecord):
            connection.execute(
                "INSERT INTO traits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    trait.trait_id,
                    trait.character_id,
                    trait.name,
                    trait.importance,
                    trait.frequency,
                    trait.review_status,
                    json.dumps(trait.triggers, ensure_ascii=False),
                    json.dumps(trait.expressions, ensure_ascii=False),
                    json.dumps(trait.boundaries, ensure_ascii=False),
                    trait.prompt_summary,
                ),
            )
            connection.executemany(
                "INSERT INTO trait_evidence VALUES (?, ?)",
                [(trait.trait_id, evidence_id) for evidence_id in trait.evidence_ids],
            )
        for item in read_jsonl(root / "canon_evidence.jsonl", CanonEvidenceRecord):
            connection.execute(
                "INSERT INTO canon_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    item.canon_evidence_id,
                    item.origin_type,
                    item.scene_id or None,
                    item.profile_id or None,
                    item.source_part_id or None,
                    item.start_ms,
                    item.end_ms,
                    item.profile_locator or None,
                    item.evidence_kind,
                    item.speaker_character_id or None,
                    item.observation,
                    item.review_status,
                    item.review_notes,
                ),
            )
            connection.executemany(
                "INSERT INTO canon_evidence_actors VALUES (?, ?)",
                [
                    (item.canon_evidence_id, character_id)
                    for character_id in item.actor_character_ids
                ],
            )
            connection.executemany(
                "INSERT INTO canon_evidence_transcripts VALUES (?, ?, ?)",
                [
                    (item.canon_evidence_id, position, transcript_ref)
                    for position, transcript_ref in enumerate(item.transcript_refs, 1)
                ],
            )
        world_entities = read_jsonl(root / "world_entities.jsonl", WorldEntityRecord)
        for entity in world_entities:
            connection.execute(
                "INSERT INTO world_entities VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entity.world_entity_id,
                    entity.source_work,
                    entity.entity_type,
                    entity.names.model_dump_json(),
                    json.dumps(entity.aliases, ensure_ascii=False),
                    entity.summary,
                    entity.first_checkpoint,
                    entity.review_status,
                ),
            )
            connection.executemany(
                "INSERT INTO world_entity_evidence VALUES (?, ?)",
                [
                    (entity.world_entity_id, evidence_id)
                    for evidence_id in entity.evidence_ids
                ],
            )
        character_facts = read_jsonl(root / "character_facts.jsonl", CharacterFactRecord)
        for fact in character_facts:
            connection.execute(
                "INSERT INTO character_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    fact.fact_id,
                    fact.character_id,
                    fact.fact_type,
                    fact.value_text or None,
                    fact.value_entity_id or None,
                    fact.canon_checkpoint,
                    fact.valid_from_checkpoint or None,
                    fact.valid_to_checkpoint or None,
                    fact.confidence,
                    fact.review_status,
                    None,
                ),
            )
            connection.executemany(
                "INSERT INTO character_fact_evidence VALUES (?, ?)",
                [(fact.fact_id, evidence_id) for evidence_id in fact.evidence_ids],
            )
        for fact in character_facts:
            if fact.supersedes_id:
                connection.execute(
                    "UPDATE character_facts SET supersedes_id = ? WHERE fact_id = ?",
                    (fact.supersedes_id, fact.fact_id),
                )
        world_facts = read_jsonl(root / "world_facts.jsonl", WorldFactRecord)
        for fact in world_facts:
            connection.execute(
                "INSERT INTO world_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    fact.fact_id,
                    fact.subject_entity_id,
                    fact.predicate,
                    fact.object_entity_id or None,
                    fact.object_text or None,
                    fact.fact_scope,
                    fact.perspective_character_id or None,
                    fact.canon_checkpoint,
                    fact.valid_from_checkpoint or None,
                    fact.valid_to_checkpoint or None,
                    fact.confidence,
                    fact.review_status,
                    None,
                ),
            )
            connection.executemany(
                "INSERT INTO world_fact_evidence VALUES (?, ?)",
                [(fact.fact_id, evidence_id) for evidence_id in fact.evidence_ids],
            )
        for fact in world_facts:
            if fact.supersedes_id:
                connection.execute(
                    "UPDATE world_facts SET supersedes_id = ? WHERE fact_id = ?",
                    (fact.supersedes_id, fact.fact_id),
                )
        character_relations = read_jsonl(
            root / "character_relations.jsonl", CharacterRelationRecord
        )
        for relation in character_relations:
            connection.execute(
                "INSERT INTO character_relations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    relation.relation_id,
                    relation.source_character_id,
                    relation.target_character_id,
                    relation.category,
                    relation.label,
                    relation.directionality,
                    relation.summary,
                    relation.canon_checkpoint,
                    relation.valid_from_checkpoint or None,
                    relation.valid_to_checkpoint or None,
                    relation.confidence,
                    relation.review_status,
                    None,
                ),
            )
            connection.executemany(
                "INSERT INTO character_relation_evidence VALUES (?, ?)",
                [
                    (relation.relation_id, evidence_id)
                    for evidence_id in relation.evidence_ids
                ],
            )
        for relation in character_relations:
            if relation.supersedes_id:
                connection.execute(
                    "UPDATE character_relations SET supersedes_id = ? WHERE relation_id = ?",
                    (relation.supersedes_id, relation.relation_id),
                )
        connection.commit()
        stats["raw_sources"] = connection.execute(
            "SELECT COUNT(*) FROM sources WHERE raw_wikitext <> ''"
        ).fetchone()[0]
        stats["archive_entries"] = connection.execute(
            "SELECT COUNT(*) FROM profile_archive_entries"
        ).fetchone()[0]
        stats["voice_lines"] = connection.execute(
            "SELECT COUNT(*) FROM profile_voice_lines"
        ).fetchone()[0]
    except Exception:
        connection.close()
        temporary.unlink(missing_ok=True)
        raise
    else:
        connection.close()
        try:
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
    return stats
