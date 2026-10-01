import json
import sqlite3
from datetime import datetime, timezone

from afterstory.character_research import (
    CharacterCatalogEntry,
    LocalizedNames,
    ProfileIndexRecord,
    SourceRecord,
    build_sqlite,
    parse_name_table,
    parse_profile,
    validate_corpus,
    write_catalog,
    write_jsonl,
)
from afterstory.config import ROOT

CORPUS_ROOT = ROOT / "research/character-corpus"


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


def test_committed_character_corpus_is_valid_and_tracks_missing_profile():
    stats = validate_corpus(CORPUS_ROOT)
    assert stats == {
        "characters": 24,
        "sources": 24,
        "profiles": 23,
        "scenes": 0,
        "evidence": 0,
        "traits": 0,
    }
    catalog = json.loads((CORPUS_ROOT / "catalog.json").read_text(encoding="utf-8"))
    missing = [item for item in catalog if item["research_status"] == "discovered"]
    assert [(item["character_id"], item["names"]["zh"]) for item in missing] == [
        ("akane-rin", "明音凛")
    ]


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
    for name in ("scenes.jsonl", "evidence.jsonl", "traits.jsonl"):
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
