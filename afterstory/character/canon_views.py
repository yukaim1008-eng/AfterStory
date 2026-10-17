from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from afterstory.character.research import (
    CanonCheckpointRecord,
    CanonEvidenceRecord,
    CharacterFactRecord,
    CharacterRelationRecord,
    SceneRecord,
    SourcePartRecord,
    SourceRecord,
    WorldEntityRecord,
    WorldFactRecord,
    load_catalog,
    read_jsonl,
)


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _at_checkpoint(record, checkpoint: CanonCheckpointRecord, checkpoint_by_id: dict) -> bool:
    observed = checkpoint_by_id[record.canon_checkpoint]
    if observed.source_work != checkpoint.source_work or observed.sequence > checkpoint.sequence:
        return False
    valid_from = getattr(record, "valid_from_checkpoint", "")
    valid_to = getattr(record, "valid_to_checkpoint", "")
    return (
        not valid_from or checkpoint_by_id[valid_from].sequence <= checkpoint.sequence
    ) and (not valid_to or checkpoint.sequence <= checkpoint_by_id[valid_to].sequence)


def _evidence_link(
    evidence_id: str,
    evidence_by_id: dict[str, CanonEvidenceRecord],
    scene_by_id: dict[str, SceneRecord],
    part_by_id: dict[str, SourcePartRecord],
    source_by_id: dict[str, SourceRecord],
) -> str:
    evidence = evidence_by_id[evidence_id]
    if evidence.origin_type == "profile":
        return f"`{evidence_id}`（档案）"
    scene = scene_by_id[evidence.scene_id]
    part = part_by_id[scene.source_part_id]
    source = source_by_id[scene.source_id]
    seconds = (evidence.start_ms or scene.start_ms) // 1000
    separator = "&" if "?" in str(source.url) else "?"
    url = f"{source.url}{separator}p={part.position}&t={seconds}"
    return f"[{evidence_id}]({url})"


def render_canon_views(
    corpus_root: Path, output_dir: Path, checkpoint_id: str = ""
) -> dict[str, int | str]:
    catalog = load_catalog(corpus_root)
    checkpoints = read_jsonl(
        corpus_root / "canon_checkpoints.jsonl", CanonCheckpointRecord
    )
    if not checkpoints:
        raise ValueError("canon review views require at least one checkpoint")
    checkpoint_by_id = {item.checkpoint_id: item for item in checkpoints}
    if checkpoint_id:
        checkpoint = checkpoint_by_id.get(checkpoint_id)
        if checkpoint is None:
            raise ValueError(f"unknown canon checkpoint: {checkpoint_id}")
    else:
        checkpoint = max(checkpoints, key=lambda item: item.sequence)

    sources = read_jsonl(corpus_root / "sources.jsonl", SourceRecord)
    parts = read_jsonl(corpus_root / "source_parts.jsonl", SourcePartRecord)
    scenes = read_jsonl(corpus_root / "scenes.jsonl", SceneRecord)
    evidence = read_jsonl(
        corpus_root / "canon_evidence.jsonl", CanonEvidenceRecord
    )
    entities = [
        item
        for item in read_jsonl(corpus_root / "world_entities.jsonl", WorldEntityRecord)
        if item.review_status == "accepted"
        and checkpoint_by_id[item.first_checkpoint].source_work == checkpoint.source_work
        and checkpoint_by_id[item.first_checkpoint].sequence <= checkpoint.sequence
    ]
    character_facts = [
        item
        for item in read_jsonl(
            corpus_root / "character_facts.jsonl", CharacterFactRecord
        )
        if item.review_status == "accepted"
        and _at_checkpoint(item, checkpoint, checkpoint_by_id)
    ]
    world_facts = [
        item
        for item in read_jsonl(corpus_root / "world_facts.jsonl", WorldFactRecord)
        if item.review_status == "accepted"
        and _at_checkpoint(item, checkpoint, checkpoint_by_id)
    ]
    relations = [
        item
        for item in read_jsonl(
            corpus_root / "character_relations.jsonl", CharacterRelationRecord
        )
        if item.review_status == "accepted"
        and _at_checkpoint(item, checkpoint, checkpoint_by_id)
    ]

    character_by_id = {item.character_id: item for item in catalog}
    entity_by_id = {item.world_entity_id: item for item in entities}
    evidence_by_id = {item.canon_evidence_id: item for item in evidence}
    scene_by_id = {item.scene_id: item for item in scenes}
    part_by_id = {item.part_id: item for item in parts}
    source_by_id = {item.source_id: item for item in sources}

    def links(ids: list[str]) -> str:
        return "、".join(
            _evidence_link(
                item, evidence_by_id, scene_by_id, part_by_id, source_by_id
            )
            for item in ids
        )

    facts_by_character = defaultdict(list)
    relations_by_character = defaultdict(list)
    for fact in character_facts:
        facts_by_character[fact.character_id].append(fact)
    for relation in relations:
        relations_by_character[relation.source_character_id].append(relation)
        relations_by_character[relation.target_character_id].append(relation)

    character_lines = [
        "# Canon 人物地图",
        "",
        (
            f"> 派生审核视图；checkpoint：`{checkpoint.checkpoint_id}`"
            f"（{checkpoint.display_name}）。权威数据仍是研究库 JSON/JSONL。"
        ),
        "",
        "| 人物 | 研究状态 | 已接受事实 | 当前关系 | 证据 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for character in catalog:
        facts = facts_by_character[character.character_id]
        fact_text = "；".join(
            f"{fact.fact_type}：{fact.value_text or entity_by_id[fact.value_entity_id].names.zh}"
            for fact in facts
        ) or "—"
        relation_texts = []
        for relation in relations_by_character[character.character_id]:
            other_id = (
                relation.target_character_id
                if relation.source_character_id == character.character_id
                else relation.source_character_id
            )
            arrow = "↔" if relation.directionality == "symmetric" else (
                "→" if relation.source_character_id == character.character_id else "←"
            )
            relation_texts.append(
                f"{arrow}{character_by_id[other_id].names.zh}：{relation.label}"
            )
        evidence_ids = sorted(
            {
                item
                for fact in facts
                for item in fact.evidence_ids
            }
            | {
                item
                for relation in relations_by_character[character.character_id]
                for item in relation.evidence_ids
            }
        )
        character_lines.append(
            "| "
            + " | ".join(
                [
                    f"{_escape(character.names.zh)} (`{character.character_id}`)",
                    character.research_status,
                    _escape(fact_text),
                    _escape("；".join(relation_texts) or "—"),
                    links(evidence_ids) if evidence_ids else "—",
                ]
            )
            + " |"
        )

    facts_by_entity = defaultdict(list)
    for fact in world_facts:
        facts_by_entity[fact.subject_entity_id].append(fact)
    world_lines = [
        "# Canon 世界知识",
        "",
        f"> 派生审核视图；checkpoint：`{checkpoint.checkpoint_id}`（{checkpoint.display_name}）。",
        "",
        "| 实体 | 类型 | 摘要 | 已接受事实 | 证据 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entity in entities:
        facts = facts_by_entity[entity.world_entity_id]
        fact_texts = []
        for fact in facts:
            target = (
                entity_by_id[fact.object_entity_id].names.zh
                if fact.object_entity_id
                else fact.object_text
            )
            scope = (
                f"（{character_by_id[fact.perspective_character_id].names.zh}的认知）"
                if fact.fact_scope == "character_belief"
                else ""
            )
            fact_texts.append(f"{fact.predicate}{target}{scope}")
        evidence_ids = sorted(
            set(entity.evidence_ids)
            | {item for fact in facts for item in fact.evidence_ids}
        )
        world_lines.append(
            "| "
            + " | ".join(
                [
                    f"{_escape(entity.names.zh)} (`{entity.world_entity_id}`)",
                    entity.entity_type,
                    _escape(entity.summary),
                    _escape("；".join(fact_texts) or "—"),
                    links(evidence_ids),
                ]
            )
            + " |"
        )

    relation_lines = [
        "# Canon 人物关系图",
        "",
        (
            f"> 派生审核视图；checkpoint：`{checkpoint.checkpoint_id}`"
            f"（{checkpoint.display_name}）。Canon 人物关系不等于现实用户与角色实例的 "
            "Runtime Relationship。"
        ),
        "",
        "```mermaid",
        "graph LR",
    ]
    relation_character_ids = sorted(
        {item.source_character_id for item in relations}
        | {item.target_character_id for item in relations}
    )
    mermaid_ids = {
        character_id: f"c{position}"
        for position, character_id in enumerate(relation_character_ids, 1)
    }
    for character_id in relation_character_ids:
        relation_lines.append(
            f'    {mermaid_ids[character_id]}["{character_by_id[character_id].names.zh}"]'
        )
    for relation in relations:
        arrow = "---" if relation.directionality == "symmetric" else "-->"
        relation_lines.append(
            f"    {mermaid_ids[relation.source_character_id]} {arrow}|{relation.label}| "
            f"{mermaid_ids[relation.target_character_id]}"
        )
    relation_lines.extend(
        [
            "```",
            "",
            "| 关系 | 类别 | 说明 | 证据 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for relation in relations:
        source_name = character_by_id[relation.source_character_id].names.zh
        target_name = character_by_id[relation.target_character_id].names.zh
        arrow = "↔" if relation.directionality == "symmetric" else "→"
        relation_lines.append(
            f"| {source_name} {arrow} {target_name}：{_escape(relation.label)} | "
            f"{relation.category} | {_escape(relation.summary)} | {links(relation.evidence_ids)} |"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "character-map.md": character_lines,
        "world-knowledge.md": world_lines,
        "character-relations.md": relation_lines,
    }
    for filename, lines in outputs.items():
        (output_dir / filename).write_text(
            "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
        )
    return {
        "checkpoint_id": checkpoint.checkpoint_id,
        "characters": len(catalog),
        "world_entities": len(entities),
        "character_relations": len(relations),
        "output": str(output_dir.resolve()),
    }
