import json
import sqlite3
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from afterstory.character_research import (
    CanonCheckpointRecord,
    CanonEvidenceRecord,
    CharacterAlias,
    CharacterCatalogEntry,
    CharacterFactRecord,
    CharacterRelationRecord,
    LocalizedNames,
    ProfileArchiveLocator,
    ProfileFieldLocator,
    ProfileIndexRecord,
    ProfileVoiceLocator,
    SceneRecord,
    SourcePartRecord,
    SourceRecord,
    WorldEntityRecord,
    WorldFactRecord,
    _merge_catalog,
    build_sqlite,
    parse_name_table,
    parse_profile,
    validate_corpus,
    write_catalog,
    write_jsonl,
)
from afterstory.config import ROOT

CORPUS_ROOT = ROOT / "research/character-corpus"
EMPTY_CORPUS_FILES = (
    "profiles.jsonl",
    "scenes.jsonl",
    "evidence.jsonl",
    "traits.jsonl",
    "canon_checkpoints.jsonl",
    "canon_evidence.jsonl",
    "world_entities.jsonl",
    "character_facts.jsonl",
    "world_facts.jsonl",
    "character_relations.jsonl",
)


def sample_wiki():
    return """{{角色信息
|姓名=伊洛伊（中）<br>Iroi（英）
|性别=女
|所属=异象管理局收容二组
}}
='''角色介绍'''=
温和的收容组成员。
='''羁遇资料'''=
看起来天然，但并不迟钝。
='''档案'''=
{{角色档案
|按钮1 = 详细情报
|内容1 = <nowiki>她会观察和学习人类。</nowiki>
|按钮2 = 在收容二组
|内容2 = <nowiki>她与同伴一起行动。</nowiki>
}}
==语音记录（文本）==
===日常===
{| class="ci-info-table"
|-
| 初次见面 || 叫我伊洛伊就好~
|}
===战斗===
{| class="ci-info-table"
|-
| 上阵 || 我会加油的！
|}
"""


def test_name_table_and_profile_parser_preserve_structure():
    names = parse_name_table(
        "| '''[[伊洛伊]]''' || イロヒ || 일로이 || Iroi\n"
        "| '''[[异能者·零]]''' || 異能者·零 || 이능력자·제로 || Esper Zero\n"
    )
    assert [item.character_id for item in names] == ["iroi", "esper-zero"]

    fields, archives, voices = parse_profile(sample_wiki())
    assert fields["所属"] == "异象管理局收容二组"
    assert fields["角色介绍"] == "温和的收容组成员。"
    assert [title for title, _ in archives] == ["详细情报", "在收容二组"]
    assert voices == [("日常", "初次见面", "叫我伊洛伊就好~"), ("战斗", "上阵", "我会加油的！")]


def test_source_catalog_refresh_preserves_curated_aliases_and_review_status():
    discovered = [
        CharacterCatalogEntry(
            character_id="iroi",
            names=LocalizedNames(zh="伊洛伊", en="Iroi"),
            research_status="discovered",
        )
    ]
    existing = [
        CharacterCatalogEntry(
            character_id="iroi",
            names=LocalizedNames(zh="伊洛伊", en="Iroi"),
            aliases=[CharacterAlias(value="小伊", language="zh", kind="nickname")],
            research_status="reviewed",
        )
    ]

    merged = _merge_catalog(discovered, existing)

    assert merged[0].aliases[0].value == "小伊"
    assert merged[0].research_status == "reviewed"


def test_committed_character_corpus_is_valid_and_tracks_missing_profile():
    stats = validate_corpus(CORPUS_ROOT)
    assert stats == {
        "characters": 28,
        "character_aliases": 0,
        "sources": 25,
        "source_parts": 21,
        "profiles": 23,
        "scenes": 49,
        "evidence": 17,
        "traits": 7,
        "canon_checkpoints": 2,
        "canon_evidence": 49,
        "world_entities": 22,
        "character_facts": 24,
        "world_facts": 20,
        "character_relations": 11,
    }
    catalog = json.loads((CORPUS_ROOT / "catalog.json").read_text(encoding="utf-8"))
    missing = [item for item in catalog if item["research_status"] == "discovered"]
    assert [(item["character_id"], item["names"]["zh"]) for item in missing] == [
        ("akane-rin", "明音凛")
    ]
    parts = [
        json.loads(line)
        for line in (CORPUS_ROOT / "source_parts.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert [parts[0]["title"], parts[-1]["title"]] == [
        "第0话 不虞亦先兆",
        "第8话 魔女 4",
    ]
    assert sum(part["duration_ms"] for part in parts) == 80_387_000
    assert {part["subtitle_mode"] for part in parts} == {"no_platform_subtitles"}
    assert [part["visual_subtitle_status"] for part in parts[:2]] == [
        "verified_present",
        "verified_present",
    ]
    assert {part["visual_subtitle_status"] for part in parts[2:]} == {
        "user_confirmed_present"
    }


def test_sqlite_build_populates_local_profile_content(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    raw_path = root / ".cache/ntestation/iroi.wiki"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(sample_wiki(), encoding="utf-8")
    write_catalog(
        root,
        [
            CharacterCatalogEntry(
                character_id="iroi",
                names=LocalizedNames(zh="伊洛伊", en="Iroi"),
                research_status="profile_collected",
            )
        ],
    )
    source = SourceRecord(
        source_id="ntestation-iroi",
        source_type="profile_archive_mirror",
        provenance="in_game_archive_mirror",
        platform="ntestation",
        title="伊洛伊角色个人档案",
        url="https://www.ntestation.com/伊洛伊",
        page_title="伊洛伊",
        revision_id=1,
        revision_timestamp=datetime.now(timezone.utc),
        retrieved_at=datetime.now(timezone.utc),
        content_hash="hash",
        raw_cache_path=".cache/ntestation/iroi.wiki",
        status="available",
    )
    profile = ProfileIndexRecord(
        profile_id="iroi-ntestation-r1",
        character_id="iroi",
        source_id=source.source_id,
        source_revision_id=1,
        content_hash="hash",
        fields={"性别": "女"},
        has_character_introduction=True,
        has_encounter_profile=True,
        archive_entry_titles=["详细情报", "在收容二组"],
        voice_category_counts={"日常": 1, "战斗": 1},
    )
    write_jsonl(root / "sources.jsonl", [source])
    write_jsonl(root / "profiles.jsonl", [profile])
    (root / "source_parts.jsonl").write_text("", encoding="utf-8")
    for name in EMPTY_CORPUS_FILES:
        if name == "profiles.jsonl":
            continue
        (root / name).write_text("", encoding="utf-8")

    database = tmp_path / "corpus.sqlite3"
    stats = build_sqlite(root, database)
    assert stats["raw_sources"] == 1
    assert stats["archive_entries"] == 2
    assert stats["voice_lines"] == 2
    connection = sqlite3.connect(database)
    try:
        assert connection.execute("SELECT COUNT(*) FROM characters").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM profile_archive_entries").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM profile_voice_lines").fetchone()[0] == 2
    finally:
        connection.close()


def write_canon_sample(root, *, evidence_status="accepted", relation_target="esper-zero"):
    root.mkdir()
    characters = [
        CharacterCatalogEntry(
            character_id="nanally",
            names=LocalizedNames(zh="娜娜莉", en="Nanally"),
            aliases=[CharacterAlias(value="鉴定师助手", language="zh", kind="title")],
            research_status="evidence_collected",
        ),
        CharacterCatalogEntry(
            character_id="esper-zero",
            names=LocalizedNames(zh="异能者·零", en="Esper Zero"),
            research_status="evidence_collected",
        ),
    ]
    write_catalog(root, characters)
    source = SourceRecord(
        source_id="story-video",
        source_type="story_video",
        provenance="in_game_footage",
        platform="local-test",
        title="剧情测试",
        url="https://example.com/story",
        retrieved_at=datetime.now(timezone.utc),
        status="indexed",
        duration_ms=10_000,
        part_count=1,
        subtitle_mode="no_platform_subtitles",
        visual_subtitle_status="verified_present",
    )
    profile_source = SourceRecord(
        source_id="profile-nanally",
        source_type="profile_archive_mirror",
        provenance="in_game_archive_mirror",
        platform="local-test",
        title="娜娜莉角色个人档案",
        url="https://example.com/nanally",
        retrieved_at=datetime.now(timezone.utc),
        status="available",
    )
    profile = ProfileIndexRecord(
        profile_id="nanally-profile",
        character_id="nanally",
        source_id=profile_source.source_id,
        source_revision_id=1,
        content_hash="profile-hash",
        fields={"所属": "异象管理局"},
        has_character_introduction=True,
        has_encounter_profile=False,
        archive_entry_titles=["详细情报"],
        voice_category_counts={"日常": 1},
    )
    part = SourcePartRecord(
        part_id="story-video-p01",
        source_id=source.source_id,
        external_part_id="1",
        position=1,
        title="序章",
        duration_ms=10_000,
        content_type="main_story",
        subtitle_mode="no_platform_subtitles",
        visual_subtitle_status="verified_present",
        processing_status="reviewed",
    )
    checkpoint = CanonCheckpointRecord(
        checkpoint_id="nt-zero-prologue",
        source_work="异环",
        display_name="第0话",
        sequence=0,
        content_track="main_story",
        game_version="1.0",
        chapter="第0话",
        spoiler_scope="第0话",
    )
    scene = SceneRecord(
        scene_id="scene-p01-001",
        source_id=source.source_id,
        source_part_id=part.part_id,
        start_ms=1_000,
        end_ms=5_000,
        chapter="第0话",
        summary="娜娜莉与鉴定师共同处理现场情况。",
        participants=["nanally", "esper-zero"],
        canon_checkpoint=checkpoint.checkpoint_id,
        review_status="reviewed",
    )
    canon_evidence = CanonEvidenceRecord(
        canon_evidence_id="canon-evidence-001",
        origin_type="scene",
        scene_id=scene.scene_id,
        source_part_id=part.part_id,
        start_ms=2_000,
        end_ms=3_000,
        evidence_kind="dialogue",
        actor_character_ids=["nanally", "esper-zero"],
        speaker_character_id="nanally",
        observation="娜娜莉明确邀请鉴定师与她共同处理当前事件。",
        transcript_refs=["utterance-001"],
        review_status=evidence_status,
    )
    profile_evidence = CanonEvidenceRecord(
        canon_evidence_id="canon-evidence-profile-001",
        origin_type="profile",
        profile_id=profile.profile_id,
        profile_locator=ProfileFieldLocator(kind="field", field_name="所属"),
        evidence_kind="profile_field",
        actor_character_ids=["nanally"],
        observation="个人档案将娜娜莉的所属列为异象管理局。",
        review_status=evidence_status,
    )
    archive_evidence = CanonEvidenceRecord(
        canon_evidence_id="canon-evidence-archive-001",
        origin_type="profile",
        profile_id=profile.profile_id,
        profile_locator=ProfileArchiveLocator(kind="archive", entry_title="详细情报"),
        evidence_kind="profile_archive",
        actor_character_ids=["nanally"],
        observation="个人档案的详细情报记录了娜娜莉的经历。",
        review_status=evidence_status,
    )
    voice_evidence = CanonEvidenceRecord(
        canon_evidence_id="canon-evidence-voice-001",
        origin_type="profile",
        profile_id=profile.profile_id,
        profile_locator=ProfileVoiceLocator(kind="voice", category="日常", label="初次见面"),
        evidence_kind="profile_voice",
        actor_character_ids=["nanally"],
        observation="娜娜莉在日常初次见面语音中主动向对方问候。",
        review_status=evidence_status,
    )
    entity = WorldEntityRecord(
        world_entity_id="bureau",
        source_work="异环",
        entity_type="organization",
        names=LocalizedNames(zh="异象管理局"),
        aliases=["管理局"],
        summary="负责处理异象事务的组织。",
        first_checkpoint=checkpoint.checkpoint_id,
        review_status="accepted",
        evidence_ids=[canon_evidence.canon_evidence_id],
    )
    character_fact = CharacterFactRecord(
        fact_id="character-fact-001",
        character_id="nanally",
        fact_type="affiliation",
        value_entity_id=entity.world_entity_id,
        canon_checkpoint=checkpoint.checkpoint_id,
        confidence="direct",
        review_status="accepted",
        evidence_ids=[profile_evidence.canon_evidence_id],
    )
    world_fact = WorldFactRecord(
        fact_id="world-fact-001",
        subject_entity_id=entity.world_entity_id,
        predicate="负责",
        object_text="处理异象事务",
        fact_scope="objective",
        canon_checkpoint=checkpoint.checkpoint_id,
        confidence="direct",
        review_status="accepted",
        evidence_ids=[canon_evidence.canon_evidence_id],
    )
    relation = CharacterRelationRecord(
        relation_id="relation-001",
        source_character_id="nanally",
        target_character_id=relation_target,
        category="cooperative",
        label="伙伴",
        directionality="symmetric",
        summary="双方能够共同处理现场事件。",
        canon_checkpoint=checkpoint.checkpoint_id,
        confidence="direct",
        review_status="accepted",
        evidence_ids=[canon_evidence.canon_evidence_id],
    )
    records = {
        "sources.jsonl": [source, profile_source],
        "source_parts.jsonl": [part],
        "profiles.jsonl": [profile],
        "canon_checkpoints.jsonl": [checkpoint],
        "scenes.jsonl": [scene],
        "canon_evidence.jsonl": [
            canon_evidence,
            profile_evidence,
            archive_evidence,
            voice_evidence,
        ],
        "world_entities.jsonl": [entity],
        "character_facts.jsonl": [character_fact],
        "world_facts.jsonl": [world_fact],
        "character_relations.jsonl": [relation],
    }
    for filename, rows in records.items():
        write_jsonl(root / filename, rows)
    for filename in ("evidence.jsonl", "traits.jsonl"):
        (root / filename).write_text("", encoding="utf-8")


def test_canon_knowledge_schema_validates_and_builds_sqlite(tmp_path):
    root = tmp_path / "corpus"
    write_canon_sample(root)

    stats = validate_corpus(root)
    assert stats["canon_checkpoints"] == 1
    assert stats["character_aliases"] == 1
    assert stats["canon_evidence"] == 4
    assert stats["world_entities"] == 1
    assert stats["character_facts"] == 1
    assert stats["world_facts"] == 1
    assert stats["character_relations"] == 1

    database = tmp_path / "canon.sqlite3"
    build_sqlite(root, database)
    connection = sqlite3.connect(database)
    try:
        assert dict(connection.execute("SELECT key, value FROM metadata")) == {
            "schema_version": "1.1",
            "corpus_schema_version": "1.0",
        }
        assert connection.execute(
            "SELECT source_part_id FROM scenes WHERE scene_id = 'scene-p01-001'"
        ).fetchone() == ("story-video-p01",)
        assert connection.execute(
            "SELECT alias, language, kind FROM character_aliases WHERE character_id = 'nanally'"
        ).fetchone() == ("鉴定师助手", "zh", "title")
        assert connection.execute(
            "SELECT content_track FROM canon_checkpoints WHERE checkpoint_id = 'nt-zero-prologue'"
        ).fetchone() == ("main_story",)
        assert connection.execute("SELECT COUNT(*) FROM canon_evidence").fetchone()[0] == 4
        assert connection.execute(
            "SELECT profile_id, profile_locator_kind, profile_locator_key "
            "FROM canon_evidence WHERE canon_evidence_id = 'canon-evidence-profile-001'"
        ).fetchone() == ("nanally-profile", "field", "所属")
        assert connection.execute(
            "SELECT profile_locator_kind, profile_locator_key, profile_locator_category "
            "FROM canon_evidence WHERE canon_evidence_id = 'canon-evidence-archive-001'"
        ).fetchone() == ("archive", "详细情报", None)
        assert connection.execute(
            "SELECT profile_locator_kind, profile_locator_key, profile_locator_category "
            "FROM canon_evidence WHERE canon_evidence_id = 'canon-evidence-voice-001'"
        ).fetchone() == ("voice", "初次见面", "日常")
        assert connection.execute("SELECT COUNT(*) FROM world_entities").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM character_facts").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM world_facts").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM character_relations").fetchone()[0] == 1
    finally:
        connection.close()


def test_canon_fact_values_and_unknown_fields_are_strict():
    common = {
        "fact_id": "fact-1",
        "character_id": "nanally",
        "fact_type": "identity",
        "canon_checkpoint": "checkpoint-1",
        "confidence": "direct",
        "evidence_ids": [],
    }
    with pytest.raises(ValidationError, match="exactly one"):
        CharacterFactRecord(**common)
    with pytest.raises(ValidationError, match="exactly one"):
        CharacterFactRecord(**common, value_text="角色", value_entity_id="entity")
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CharacterFactRecord(**common, value_text="角色", unexpected=True)

    profile_evidence = CanonEvidenceRecord(
        canon_evidence_id="profile-evidence-1",
        origin_type="profile",
        profile_id="nanally-profile",
        profile_locator=ProfileFieldLocator(kind="field", field_name="所属"),
        evidence_kind="profile_field",
        actor_character_ids=["nanally"],
        observation="档案将娜娜莉列为某组织成员。",
    )
    assert profile_evidence.scene_id == ""
    with pytest.raises(ValidationError, match="profile evidence cannot include scene locator"):
        CanonEvidenceRecord(
            canon_evidence_id="profile-evidence-2",
            origin_type="profile",
            profile_id="nanally-profile",
            profile_locator=ProfileFieldLocator(kind="field", field_name="所属"),
            scene_id="scene-1",
            evidence_kind="profile_field",
            observation="错误地混合了两种来源定位。",
        )

    with pytest.raises(ValidationError, match="profile evidence kind must match"):
        CanonEvidenceRecord(
            canon_evidence_id="profile-evidence-3",
            origin_type="profile",
            profile_id="nanally-profile",
            profile_locator=ProfileArchiveLocator(kind="archive", entry_title="详细情报"),
            evidence_kind="profile_field",
            observation="档案类型与证据类型不匹配。",
        )

    with pytest.raises(ValidationError):
        CanonEvidenceRecord(
            canon_evidence_id="profile-evidence-4",
            origin_type="profile",
            profile_id="nanally-profile",
            profile_locator="fields.所属",
            evidence_kind="profile_field",
            observation="旧的自由字符串定位不再接受。",
        )

    voice_locator = ProfileVoiceLocator(kind="voice", category="日常", label="初次见面")
    assert voice_locator.category == "日常"

    with pytest.raises(ValidationError):
        CharacterFactRecord(**{**common, "fact_type": "status"}, value_text="在场")
    assert (
        CharacterFactRecord(
            **{**common, "fact_type": "canon_status"}, value_text="在场"
        ).fact_type
        == "canon_status"
    )


def test_scene_part_and_canon_relation_cannot_cross_namespaces(tmp_path):
    root = tmp_path / "broken-part"
    write_canon_sample(root)
    scene = SceneRecord.model_validate_json((root / "scenes.jsonl").read_text(encoding="utf-8"))
    scene.source_part_id = "missing-part"
    write_jsonl(root / "scenes.jsonl", [scene])
    with pytest.raises(ValueError, match="Broken scene reference"):
        validate_corpus(root)

    user_root = tmp_path / "user-relation"
    write_canon_sample(user_root, relation_target="user-123")
    with pytest.raises(ValueError, match="Broken character relation reference"):
        validate_corpus(user_root)


def test_character_aliases_and_profile_locators_are_corpus_validated(tmp_path):
    alias_root = tmp_path / "duplicate-alias"
    write_canon_sample(alias_root)
    catalog_path = alias_root / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog[0]["aliases"].append(catalog[0]["aliases"][0].copy())
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate character alias"):
        validate_corpus(alias_root)

    locator_root = tmp_path / "invalid-profile-locator"
    write_canon_sample(locator_root)
    evidence_path = locator_root / "canon_evidence.jsonl"
    records = [
        CanonEvidenceRecord.model_validate_json(line)
        for line in evidence_path.read_text(encoding="utf-8").splitlines()
    ]
    records[1].profile_locator = ProfileVoiceLocator(
        kind="voice", category="不存在的分类", label="初次见面"
    )
    records[1].evidence_kind = "profile_voice"
    write_jsonl(evidence_path, records)
    with pytest.raises(ValueError, match="Invalid profile locator"):
        validate_corpus(locator_root)


def test_accepted_knowledge_requires_reviewed_accepted_evidence(tmp_path):
    root = tmp_path / "candidate-evidence"
    write_canon_sample(root, evidence_status="candidate")
    with pytest.raises(ValueError, match="Accepted record requires accepted evidence"):
        validate_corpus(root)


def test_invalid_corpus_does_not_replace_existing_sqlite(tmp_path):
    root = tmp_path / "invalid-corpus"
    write_canon_sample(root, relation_target="user-123")
    database = tmp_path / "existing.sqlite3"
    original = b"existing database placeholder"
    database.write_bytes(original)

    with pytest.raises(ValueError, match="Broken character relation reference"):
        build_sqlite(root, database)

    assert database.read_bytes() == original
    assert not list(tmp_path.glob(".*.tmp"))
