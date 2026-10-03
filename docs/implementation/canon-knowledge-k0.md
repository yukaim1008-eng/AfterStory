# Canon 知识层 K0 实施记录

状态：K0 与 K0.1 完成。提交日期：2026-10-03。

## 范围

K0 只建立人物地图、世界知识和人物关系图共用的研究库骨架，不导入 P1，不修改生产 PostgreSQL、Character Definition、CharacterInstance、ContextAssembler、Provider 或前端。

## 已实现

- `SceneRecord` 增加必填 `source_part_id`，场景必须引用属于同一 source 的分 P，时间范围不能超过分 P 时长。
- 新增 `CanonCheckpointRecord`，保存作品、显示名称、顺序、版本、章节、前置节点和剧透范围。
- 新增 `CanonEvidenceRecord`。来源严格二选一：剧情证据定位 Scene、分 P 与时间；档案证据定位 Profile 与具体字段/条目。
- 新增 `WorldEntityRecord`、`CharacterFactRecord`、`WorldFactRecord` 和 `CharacterRelationRecord`。
- 新增六个空正式 JSONL 文件；P1 本地审核稿没有写入这些文件。
- 本地 SQLite 增加 checkpoint、证据、世界实体、人物事实、世界事实、人物关系及相应关联表与索引。
- SQLite 构建改为临时文件中完成，成功后原子替换目标；校验或构建失败时保留已有数据库。

## K0.1 数据契约优化

- 人物目录增加结构化 `aliases`，每项记录文本、语言及昵称、称号、OCR 变体或其他类型；同步官网名称表时保留已维护别名。
- checkpoint 增加 `content_track`，区分主线、番外、角色故事、活动和未知轨道；同一作品的全局 `sequence` 继续承担发布/剧透顺序。
- 档案证据的 `profile_locator` 从自由字符串改为 `field`、`archive`、`voice` 三种严格结构，并与 `profiles.jsonl` 中的字段、档案标题或语音分类交叉校验。
- 档案证据类型细分为 `profile_field`、`profile_archive`、`profile_voice`，必须与定位器类型一致。
- 人物事实的剧情内状态类型由 `status` 改为 `canon_status`，避免与用户实例运行时 State 混淆。
- JSON/JSONL Corpus Schema 继续为 `1.0`；派生 SQLite Schema 升为 `1.1`，并分别记录两个版本号。
- 正式 Canon 文件仍为空，因此本轮无需迁移事实、关系或场景记录，也没有修改生产 PostgreSQL。

## 主要校验

- 所有模型拒绝未知字段，固定 Schema Version `1.0`；关键 ID、名称、摘要和 checkpoint 不允许空白。
- checkpoint 的 `(source_work, sequence)` 唯一，前置节点必须属于同一作品、顺序更早且不能形成循环。
- 文本值和实体引用严格二选一；客观世界事实不能携带人物视角，人物认知必须指定对应角色。
- Canon 证据中的人物必须来自角色目录；剧情证据人物必须属于对应 Scene，档案证据人物必须对应 Profile。
- `accepted` 实体、事实和关系必须引用 `accepted` 证据；`accepted` 剧情证据必须来自 `reviewed` Scene。
- 事实、关系、checkpoint 和证据必须属于同一作品；替代链引用同类记录且不能形成循环。
- Canon 人物关系两端只能引用角色目录中的 `character_id`，现实 `user_id` 无法作为关系端点进入资料库。

## 文件

- `afterstory/character_research.py`
- `tests/test_character_research.py`
- `research/character-corpus/canon_checkpoints.jsonl`
- `research/character-corpus/canon_evidence.jsonl`
- `research/character-corpus/world_entities.jsonl`
- `research/character-corpus/character_facts.jsonl`
- `research/character-corpus/world_facts.jsonl`
- `research/character-corpus/character_relations.jsonl`
- `research/character-corpus/README.md`
- `docs/design/character/canon-knowledge-map.md`

## 验证

- `uv run pytest tests/test_character_research.py -q`：10 passed。
- 后端全量回归排除一个已确认滞后的旧断言：115 passed、1 deselected。
- `uv run ruff check .`：通过。
- 正式研究目录 `validate`：24 人物、25 来源、21 分 P、23 档案；Scene 与六类 Canon 知识记录均为 0。
- 隔离临时 SQLite 重建及本地查询库原子重建：25 张表，`PRAGMA integrity_check = ok`，无外键错误。
- 本地查询库保留 24 名人物、25 个来源、21 个分 P、23 份档案、143 个档案条目和 1955 条语音索引；结构化别名与正式 Canon 表当前为空。

唯一排除项 `test_structured_definition_reaches_provider_before_runtime_context` 已单独复现：它的精确相等断言仍只接受 Character Prompt，而当前 Conversation Response Policy v1 已按设计追加在同一 system 内容中。K0/K0.1 未修改该测试、ContextAssembler、Provider 或回复策略调用链，因此继续记录为本阶段外的既有测试滞后，不通过改弱断言掩盖。测试创建的隔离 schema 已清理，用户启动的 PostgreSQL 容器保持运行。

## 下一阶段

K1 使用已逐条复核的 P1 审核稿生成正式 Scene 与中立 Canon Evidence。K1 需要先建立 P1 对应 checkpoint，只处理 P1，不开始 P2，也不生成 Character Definition。
