# AfterStory 人物资料研究库

本目录是角色资料的制作来源，不是聊天运行时数据库。生产链路仍只读取经过审核的 `CharacterVersion.definition` 与冻结 `system_prompt`。

## 文件职责

| 文件 | 内容 |
| --- | --- |
| `catalog.json` | 有稳定 ID 的命名角色目录、多语言名称、结构化别名与研究状态 |
| `sources.jsonl` | 档案页、剧情录像等来源及其版本、哈希与采集状态 |
| `source_parts.jsonl` | 长视频的分 P、CID、时长、字幕模式与处理进度 |
| `profiles.jsonl` | 个人档案的结构化事实、档案目录和语音覆盖统计 |
| `scenes.jsonl` | 剧情场景、时间范围、参与角色和 Canon checkpoint |
| `evidence.jsonl` | 某个场景对某个角色提供的人物表现证据 |
| `traits.jsonl` | 多条证据归纳后的人物特征卡及 Prompt 摘要 |
| `canon_checkpoints.jsonl` | Canon 剧情节点、顺序、前置节点和剧透范围 |
| `canon_evidence.jsonl` | 可回溯到剧情 Scene 或个人档案字段的中立 Canon 证据 |
| `world_entities.jsonl` | 组织、地点、概念、现象、物件、事件和种族目录 |
| `character_facts.jsonl` | 带 checkpoint、证据和有效区间的标准化人物事实 |
| `world_facts.jsonl` | 客观事实、人物认知和剧情内转述 |
| `character_relations.jsonl` | 带方向、checkpoint、证据和有效区间的 Canon 人物关系 |

`.cache/` 保存从来源站点取得的页面快照，`local/corpus.sqlite3` 是查询库。两者均为可重建的本地数据，不提交 Git。Git 中不保存完整游戏档案或整份语音原文，只保存来源定位、事实索引、覆盖统计和后续人工归纳结果。

## 当前覆盖

- 目录以异环信息站的“角色名称表”为基础，并补充已复核剧情中明确出现的人物，当前登记 26 名命名角色。
- 其中 23 名已有个人档案页面并完成同步；明音凛只有名称记录，来源页尚未建立。
- 本地查询库当前包含 23 份页面快照、143 个档案条目和 1955 条语音索引内容。
- 已登记 B 站剧情合集 `BV1kqoaBiEVZ`：21 个分 P，总长 80,387 秒，覆盖标题标注至 1.4；平台接口未提供 CC 字幕，用户已确认录制的游戏画面内含字幕。
- P1 `05:00–10:00` 的本地 PP-OCRv5 试跑已通过：清晰正文和中英混合字幕可以抽取，逐字显示合并、短句保护和无姓名过场的说话者归属仍需由单分 P 批处理工具解决。视频、截图与试跑逐字稿只在忽略的 `local/` 中保存。
- 本地视频工具 Version `1.0` 已完成完整 P1：786 个候选帧生成 382 个有效 OCR 样本、215 段台词候选和 22 个机器场景草稿。全画面逐条复核保留 189 条、剔除 26 条；124 条说话者已确认、40 条为推定、25 条保持未知。静态 HTML 报告可直接浏览画面、原 OCR、修订稿和审核结论。
- Canon 知识层 K0–K3 已完成 P1 闭环：189 条复核台词提升为 29 个正式场景和 29 条 accepted 中立证据，并形成 12 个世界实体、9 条人物事实、13 条世界事实和 6 条人物关系；艾尔菲德、奈丽已登记为剧情人物。
- `evidence` 与 `traits` 仍为空，尚未把单场表现归纳为正式性格；P1 完整逐字稿继续只在忽略的 `local/video-pipeline/` 保存，正式库只保存短摘要、时间定位和引用 ID。

异环信息站属于游戏个人档案的搬运来源，因此标记为 `in_game_archive_mirror`。它能确认游戏内档案和语音内容，但同一文本在不同搬运页面出现时不会被当作多份独立证据。

## 命令

```powershell
uv run python -m scripts.character_corpus sync-ntestation
uv run python -m scripts.character_corpus sync-bilibili --bvid BV1kqoaBiEVZ
uv run python -m scripts.character_corpus promote-video `
  --staging research/character-corpus/local/video-pipeline/bilibili-BV1kqoaBiEVZ-p01 `
  --plan research/character-corpus/video_promotions/bilibili-BV1kqoaBiEVZ-p01.json
uv run python -m scripts.character_corpus render --checkpoint nt-bv1kqoabievz-p01
uv run python -m scripts.character_corpus validate
uv run python -m scripts.character_corpus build
```

剧情视频处理工具及运行方式见 [`tools/video_pipeline/README.md`](tools/video_pipeline/README.md)。抽取工具只写本地审核暂存区；`promote-video` 另行校验完整审核覆盖、逐字稿哈希、场景覆盖、时间范围和不可变 ID 后，才把已审核结果提升到正式 JSONL。提升计划保存在 `video_promotions/`，不复制完整剧情逐字稿。`render` 按指定 checkpoint 生成 `views/` 下的人物地图、世界知识页和 Mermaid 人物关系图，每条记录都能回到视频分 P 与时间点。

`sync-ntestation` 使用 MediaWiki API 读取角色名称表和各角色页面，并记录页面 revision 与内容哈希。`sync-bilibili` 只读取公开视频元数据、分 P 和平台字幕状态，不下载视频或音频。`validate` 检查严格 Schema、唯一键、checkpoint 内容轨道与全局剧透顺序、结构化档案定位、时间范围、审核门禁和跨文件引用。`build` 先在隔离临时文件中完成 SQLite 重建，成功后才原子替换目标；校验或构建失败不会覆盖已有查询库。没有本地快照时仍可建立目录与来源表，但档案正文和语音表需要重新同步后才会填充。

人物别名记录 `value`、`language` 和 `kind`，供剧情称呼、OCR 归一化与人物消歧使用。档案 Canon 证据不接受自由字符串路径：字段、档案条目和语音条目分别使用 `field`、`archive`、`voice` 定位器，并与 `profiles.jsonl` 的索引交叉校验。人物事实类型中的剧情内状态统一命名为 `canon_status`，与用户实例的运行时 State 保持边界。

## 内容状态

资料进入运行时前依次经过：

```text
discovered
→ profile_collected
→ evidence_collected
→ profile_draft
→ reviewed
→ runtime_ready
```

当前同步只完成前两级，不自动生成角色性格，也不自动导入 AfterStory。
