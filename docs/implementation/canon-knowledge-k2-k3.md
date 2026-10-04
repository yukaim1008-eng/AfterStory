# Canon 知识层 K2/K3：P1 结构化知识与审核视图

状态：完成。

## K2 数据结果

P1 的 29 条 accepted 中立证据经过 Agent 审核后形成：

- 12 个世界实体；
- 9 条人物事实；
- 13 条世界事实；
- 6 条人物关系。

每条 accepted 记录都引用 accepted Canon Evidence，并使用 `nt-bv1kqoabievz-p01` checkpoint。
未知人物仍保持未知；“V级以上异象可能吸引零号异象”只记录为艾尔菲德的
`character_belief`，没有提升为客观世界规则。

人物关系只描述原作人物之间及原作人物与异能者·零之间的 Canon 起点。它们没有现实
`user_id`，也没有写入生产 PostgreSQL、CharacterInstance 或 Runtime Relationship。

## K3 审核视图

新增 `scripts.character_corpus render`，按 checkpoint 读取 accepted 且处于有效区间的记录，生成：

- `views/character-map.md`：全部人物、研究状态、人物事实、当前 Canon 关系和证据；
- `views/world-knowledge.md`：世界实体、事实范围和证据；
- `views/character-relations.md`：Mermaid 关系图与关系明细。

剧情证据链接包含 B 站分 P 与秒级时间点。视图是派生审核产物，权威来源仍是正式 JSON/JSONL。

## 验证

- corpus 严格校验通过；
- SQLite Schema `1.1` 重建成功；
- 渲染器测试覆盖指定 checkpoint、未知 checkpoint、证据链接和 Runtime Relationship 隔离说明；
- Canon 相关测试与 Ruff 通过。

## 下一阶段

K4 按分 P 顺序处理 P2–P21。每个分 P 独立完成下载、OCR、画面复核、正式提升、事实审核、
视图刷新、验证和中文提交；性格 Trait 与正式 Character Definition 等全部剧情完成后统一归纳。
