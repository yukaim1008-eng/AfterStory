from pathlib import Path

import pytest

from afterstory.canon_views import render_canon_views
from afterstory.config import ROOT

CORPUS_ROOT = ROOT / "research/character-corpus"


def test_render_canon_views_uses_accepted_checkpointed_records(tmp_path: Path):
    result = render_canon_views(
        CORPUS_ROOT, tmp_path, checkpoint_id="nt-bv1kqoabievz-p01"
    )

    assert result == {
        "checkpoint_id": "nt-bv1kqoabievz-p01",
        "characters": 59,
        "world_entities": 12,
        "character_relations": 6,
        "output": str(tmp_path.resolve()),
    }
    character_map = (tmp_path / "character-map.md").read_text(encoding="utf-8")
    world_knowledge = (tmp_path / "world-knowledge.md").read_text(encoding="utf-8")
    relations = (tmp_path / "character-relations.md").read_text(encoding="utf-8")
    assert "薄荷 (`mint`)" in character_map
    assert "对异象奇点具有敏锐感知力" in character_map
    assert "（艾尔菲德的认知）" in world_knowledge
    assert "graph LR" in relations
    assert "Canon 人物关系不等于现实用户与角色实例" in relations
    assert "?p=1&t=" in relations


def test_render_canon_views_includes_reviewed_p02_knowledge(tmp_path: Path):
    result = render_canon_views(
        CORPUS_ROOT, tmp_path, checkpoint_id="nt-bv1kqoabievz-p02"
    )

    assert result == {
        "checkpoint_id": "nt-bv1kqoabievz-p02",
        "characters": 59,
        "world_entities": 22,
        "character_relations": 11,
        "output": str(tmp_path.resolve()),
    }
    character_map = (tmp_path / "character-map.md").read_text(encoding="utf-8")
    world_knowledge = (tmp_path / "world-knowledge.md").read_text(encoding="utf-8")
    relations = (tmp_path / "character-relations.md").read_text(encoding="utf-8")
    assert "塔吉多 (`taygedo`)" in character_map
    assert "伊波恩古董店维修师" in character_map
    assert "胶片照片异象 (`film-photo-anomaly`)" in world_knowledge
    assert "塔吉多 → 异能者·零：主动称为朋友" in relations
    assert "Canon 人物关系不等于现实用户与角色实例" in relations
    assert "?p=2&t=" in relations


def test_render_canon_views_includes_reviewed_p03_knowledge(tmp_path: Path):
    result = render_canon_views(
        CORPUS_ROOT, tmp_path, checkpoint_id="nt-bv1kqoabievz-p03"
    )

    assert result == {
        "checkpoint_id": "nt-bv1kqoabievz-p03",
        "characters": 59,
        "world_entities": 35,
        "character_relations": 23,
        "output": str(tmp_path.resolve()),
    }
    character_map = (tmp_path / "character-map.md").read_text(encoding="utf-8")
    world_knowledge = (tmp_path / "world-knowledge.md").read_text(encoding="utf-8")
    relations = (tmp_path / "character-relations.md").read_text(encoding="utf-8")
    assert "奥托 (`otto`)" in character_map
    assert "并非该空间真正的主人" in character_map
    assert "月光当铺 (`moonlight-pawnshop`)" in world_knowledge
    assert "嘭嘭 ↔ 墨菲克斯：爱犬与照料者" in relations
    assert "Canon 人物关系不等于现实用户与角色实例" in relations
    assert "?p=3&t=" in relations


def test_render_canon_views_includes_reviewed_p04_knowledge(tmp_path: Path):
    result = render_canon_views(
        CORPUS_ROOT, tmp_path, checkpoint_id="nt-bv1kqoabievz-p04"
    )

    assert result == {
        "checkpoint_id": "nt-bv1kqoabievz-p04",
        "characters": 59,
        "world_entities": 42,
        "character_relations": 27,
        "output": str(tmp_path.resolve()),
    }
    character_map = (tmp_path / "character-map.md").read_text(encoding="utf-8")
    world_knowledge = (tmp_path / "world-knowledge.md").read_text(encoding="utf-8")
    relations = (tmp_path / "character-relations.md").read_text(encoding="utf-8")
    assert "塔可 (`tako`)" in character_map
    assert "随担保人搬离海特洛市" in character_map
    assert "随心泥 (`wish-clay`)" in world_knowledge
    assert "塔吉多 → 塔可：单向爱慕并尝试告白" in relations
    assert "Canon 人物关系不等于现实用户与角色实例" in relations
    assert "?p=4&t=" in relations


def test_render_canon_views_rejects_unknown_checkpoint(tmp_path: Path):
    with pytest.raises(ValueError, match="unknown canon checkpoint"):
        render_canon_views(CORPUS_ROOT, tmp_path, checkpoint_id="missing")
