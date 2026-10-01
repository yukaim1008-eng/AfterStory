# AfterStory 人物资料研究库

本目录是角色资料的制作来源，不是聊天运行时数据库。生产链路仍只读取经过审核的 `CharacterVersion.definition` 与冻结 `system_prompt`。

## 文件职责

| 文件 | 内容 |
| --- | --- |
| `catalog.json` | 有稳定 ID 的命名角色目录、多语言名称与研究状态 |
| `sources.jsonl` | 档案页、剧情录像等来源及其版本、哈希与采集状态 |
| `profiles.jsonl` | 个人档案的结构化事实、档案目录和语音覆盖统计 |
| `scenes.jsonl` | 剧情场景、时间范围、参与角色和 Canon checkpoint |
| `evidence.jsonl` | 某个场景对某个角色提供的人物表现证据 |
| `traits.jsonl` | 多条证据归纳后的人物特征卡及 Prompt 摘要 |

`.cache/` 保存从来源站点取得的页面快照，`local/corpus.sqlite3` 是查询库。两者均为可重建的本地数据，不提交 Git。Git 中不保存完整游戏档案或整份语音原文，只保存来源定位、事实索引、覆盖统计和后续人工归纳结果。

## 当前覆盖

- 目录来自异环信息站的“角色名称表”，当前登记 24 名命名角色。
- 其中 23 名已有个人档案页面并完成同步；明音凛只有名称记录，来源页尚未建立。
- 本地查询库当前包含 23 份页面快照、143 个档案条目和 1955 条语音索引内容。
- `scenes`、`evidence`、`traits` 仍为空，等待 B 站剧情来源进入下一阶段。

异环信息站属于游戏个人档案的搬运来源，因此标记为 `in_game_archive_mirror`。它能确认游戏内档案和语音内容，但同一文本在不同搬运页面出现时不会被当作多份独立证据。

## 命令

```powershell
uv run python -m scripts.character_corpus sync-ntestation
uv run python -m scripts.character_corpus validate
uv run python -m scripts.character_corpus build
```

`sync-ntestation` 使用 MediaWiki API 读取角色名称表和各角色页面，并记录页面 revision 与内容哈希。`validate` 检查 Schema、唯一键和跨文件引用。`build` 从索引和本地快照重建 SQLite；没有本地快照时仍可建立目录与来源表，但档案正文和语音表需要重新同步后才会填充。

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
