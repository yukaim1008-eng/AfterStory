# Canon 人物、世界与关系知识层

状态：设计 v1；K0–K4 已完成 P1–P18 的正式 Scene、Canon Evidence、人物/世界/关系知识及静态审核视图，P2–P4 已形成带证据边界的 Trait（P5 起各批次按计划暂不建 Trait，留待全集归纳）；当前停在 P18，生产数据库与聊天运行时未修改。

## 1. 本轮目标

在现有人物资料研究库上建立三个可以随剧情逐步补全的 Canon 视图：

1. **人物地图**：有哪些人物、他们的稳定身份、基本资料、所属和剧情覆盖情况；
2. **世界知识**：有哪些组织、地点、概念、现象、物件和重要事件，以及它们之间已经确认的事实；
3. **人物关系图**：人物之间在指定剧情进度下存在什么关系、立场和变化。

这三项共用同一条来源与审核链，不各自重复解析剧情。它们是研究库中的 Canon 知识层，不是聊天运行时记忆，也不是直接给模型使用的一大段资料。

本设计先确定边界、数据单位、证据链、时间规则和实施顺序。K0/K0.1 已建立研究库模型和本地 SQLite 查询表，但仍未导入 P1，也未修改 Character Definition 或生产运行时。

## 2. 已确认规则、建议方案与暂缓内容

### 2.1 已确认规则

- 人物地图、世界知识和人物关系图三项都需要建设，并由后续剧情分析持续补充。
- 游戏个人档案用于人物基础资料，剧情录像用于人物表现、世界事实和关系证据。
- 视频工具的机器结果必须经过画面复核后，才能进入正式研究数据。
- 不要求用户直接审核大量 JSON；日常审核由 Agent 对照画面、文本和证据完成，用户只集中判断有争议的人设和产品取舍。
- Canon 资料与 AfterStory 中用户和角色形成的 Memory、State、Relationship 严格分开。
- Canon 原作主角与现实用户之间必须通过 CharacterInstance 的显式、冻结 Canon Role Binding 连接；缺少绑定时不得自动继承主角关系。

### 2.2 建议方案

- 继续使用 JSON/JSONL 作为 Git 中的可审计来源，用本地 SQLite 生成查询视图；当前不引入图数据库或向量数据库。
- `catalog.json` 继续作为人物稳定 ID 的唯一目录，不再建立第二套人物主表。
- 人物地图和关系图是由已接受记录生成的视图，不手工维护一份容易失真的图文件。
- 所有正式事实和关系都绑定 Canon checkpoint；后期剧情改变认知时新增记录并关闭旧记录的有效区间，不覆盖历史。
- 所有命名剧情人物都可进入目录；没有个人档案的角色先标为 `discovered`，不阻塞场景入库。

### 2.3 本阶段暂缓

- 不把完整 Canon 每轮直接注入 Provider；运行时选择与预算以后单独设计。
- 不生成 Character Schema v2，不自动改写六字段 Character Definition。
- 不建设 Lore RAG、Embedding、Vector DB、图数据库或资料管理前端。
- 不把 Canon 人物关系转换成用户和角色的运行时关系数值。
- 不自动追踪官方更新，不一次性批处理全部 22 小时视频。

## 3. 总体分层

```text
来源 Source / Source Part
        ↓
已复核台词、画面和场景 Scene
        ↓
中立 Canon Evidence
        ↓
候选事实 / 候选关系
        ↓ 审核接受
Character Facts ─ World Facts ─ Character Relations
        ↓                 ↓
人物地图          世界知识视图          人物关系图
        ↓ 可选、单独审核
Traits / Character Definition / Canon Runtime Context

Character Relations ──单向选择起点──→ Instance Canon Role Binding
                                             ↓
                              Instance Runtime Relationship
```

现有的人物塑造链继续并行存在：

```text
Scene → 人物表现 Evidence → Trait → Character Definition 候选
```

中立 Canon Evidence 记录“画面或文本直接说明了什么”；人物表现 Evidence 记录“这对某个角色的性格、说话或行为说明了什么”。同一场景可以支持两条链，但事实和解释不能混为一条记录。

## 4. 人物地图

### 4.1 人物节点

`catalog.json` 继续提供人物节点的稳定身份：

- `character_id`：跨来源稳定 ID；
- `names`：中、日、韩、英名称；
- `aliases`：结构化别名列表，每项记录文本、语言和 `nickname` / `title` / `ocr_variant` / `other` 类型；
- `source_work`：作品；
- `research_status`：当前资料完成度；

别名只用于剧情称呼、人物消歧和 OCR 归一化，不替代稳定 `character_id`。当前 24 名人物暂未人工补别名，因此目录中均显式保存空数组；后续只能根据档案或已复核剧情逐项增加。

玩家主角继续使用现有 `esper-zero` 节点。男主/女主或不同外观先作为来源中的 `presentation_variant`，不因为画面形象不同复制两套 Canon 人物；只有未来确认剧情事实本身发生分歧时，才增加分支规则。

### 4.2 人物基本资料

个人档案原文索引继续保存在 `profiles.jsonl`。人物地图展示时，将最新有效档案中的姓名、性别、生日、所属、能力、登场版本等字段标准化，并与审核后的剧情事实合并。

K0 已新增 `character_facts.jsonl`，只保存已经标准化、可以引用和带时间范围的人物事实。每条记录至少包含：

| 字段 | 含义 |
| --- | --- |
| `fact_id` | 稳定事实 ID |
| `character_id` | 对应人物 |
| `fact_type` | 身份、职业、所属、能力、背景、Canon 状态或其他受控类型；Canon 状态使用 `canon_status`，不与运行时 State 共名 |
| `value_text` / `value_entity_id` | 文本值或指向世界实体；两者只使用一个 |
| `canon_checkpoint` | 该事实被确认时的剧情进度 |
| `valid_from_checkpoint` | 已知从何时成立；未知可空 |
| `valid_to_checkpoint` | 已知何时失效；仍有效或未知可空 |
| `confidence` | `direct`、`supported`、`provisional` |
| `review_status` | `candidate`、`accepted`、`rejected`、`superseded` |
| `evidence_ids` | 支持这条事实的中立证据 |
| `supersedes_id` | 新认知替代哪条旧记录；不是原地覆盖 |

人物地图是读取模型，按某个 checkpoint 汇总：基本资料、所属组织、首次/最近剧情出现、已接受特征、主要关系和证据覆盖。缺失字段直接显示未知，不能靠模型补齐。

## 5. 世界知识

### 5.1 世界实体

K0 已新增 `world_entities.jsonl`，保存可被多条事实引用的稳定对象。初始类型保持有限：

- `organization`：组织、机构、阵营；
- `location`：城市、区域、建筑；
- `concept`：世界规则、术语、制度；
- `phenomenon`：异象、能力机制或自然现象；
- `object`：重要物件、装置；
- `event`：有专名且会被多处引用的重要事件；
- `species`：剧情明确存在的种族或生物类别。

单个剧情片段仍是 `Scene`，不会因为发生过一件事就自动新建 `event`。世界实体至少保存稳定 ID、类型、多语言名称/别名、短说明、首次出现 checkpoint、审核状态和证据引用。

### 5.2 世界事实

K0 已新增 `world_facts.jsonl`。每条事实由主语、谓词和宾语构成，但保持人可以直接审核：

- `subject_entity_id`；
- `predicate`，例如“位于”“隶属于”“负责”“导致”“被称为”；
- `object_entity_id` 或 `object_text`；
- `fact_scope`：`objective`、`character_belief`、`reported_claim`；`character_belief` 另以 `perspective_character_id` 标明是谁的认知；
- checkpoint、有效区间、confidence、review status、evidence IDs 和 supersedes ID。

`objective` 表示当前剧情把它当作客观事实；`character_belief` 表示某人物相信如此；`reported_claim` 表示剧情中有人或文档这样声称，但真实性尚未确认。人物误解、传闻和后续反转由此保留下来，不会被提前写成客观世界规则。

Character Definition 中的 `worldview` 仍是角色在指定版本下需要遵循的稳定认知摘要。它可以以后从已审核世界知识中人工压缩，但不能等同于整套世界数据库。

## 6. 人物关系图

### 6.1 三类关系必须分开

| 关系 | 归属 | 示例 |
| --- | --- | --- |
| 原作人物 ↔ 原作人物 | 本文的 Canon 关系图 | 同事、伙伴、上下级、亲属、敌对、警惕 |
| 原作人物 ↔ 原作玩家主角 | 本文的 Canon 关系图 | 娜娜莉与鉴定师在某 checkpoint 的伙伴关系 |
| AfterStory 角色实例 ↔ 现实用户 | 现有运行时 `relationships` | 聊天后形成的熟悉、信任和亲近 |

用户映射为鉴定师时，Character Version 提供兼容的关系前提，CharacterInstance 再通过显式身份绑定承接 `esper-zero` 与该角色的 Canon 起点；此后在 AfterStory 形成的变化仍只写入该实例的运行数据。

### 6.2 Instance Canon Role Binding

仅将 Canon 数据与运行时数据库分开还不够。如果模型不知道“当前用户是否就是原作主角”，仍可能把鉴定师当成第三个人、把原作经历误认为现实用户经历，或把运行时关系写回 Canon。

因此 Canon 与现实用户之间只允许存在一个显式桥梁：**Instance Canon Role Binding**。它属于 CharacterInstance 的冻结身份前提，不属于运行时 Relationship。建议契约至少包含：

| 字段 | 含义 |
| --- | --- |
| `character_instance_id` | 当前角色实例；现实用户身份由实例归属确定 |
| `identity_mode` | `canon_role_continuation` 或 `separate_person` |
| `canon_role_character_id` | 承接的原作角色 ID；continuation 必填，separate 必须为空 |
| `canon_checkpoint_id` | 绑定采用的 Canon 起点 |
| `source_relation_ids` | 创建实例时选中的 Canon 关系记录，用于来源追踪和冻结 |
| `binding_status` | 首版只允许 `frozen` |

两种模式的语义必须明确：

- `canon_role_continuation`：当前用户在这个实例中承接指定原作角色身份。例如绑定 `esper-zero` 后，娜娜莉与鉴定师的适用 Canon 关系成为该实例的关系起点；组装上下文时不能再把鉴定师作为独立第三人重复注入。
- `separate_person`：现实用户与原作主角是不同人物。原作主角仍可作为 Canon 人物被提及，但用户不能继承其经历和关系。

绑定必须遵循以下不变量：

1. Canon 人物、事实和关系记录中永远不出现 `user_id`；
2. 不能根据称呼、名字、相似台词或模型推理自动创建绑定；
3. `source_relation_ids` 只单向形成实例起点，之后的 Runtime Relationship 不得反向修改 Canon；
4. CharacterVersion 的冻结 `relationship_premise` 必须与绑定模式兼容，冲突时拒绝启用 Canon 上下文；
5. 身份模式、角色或 checkpoint 发生实质变化时创建新 CharacterInstance，不修改旧实例；
6. Canon 后续更新不自动改写旧绑定，也不自动切换旧实例；
7. 旧实例没有明确绑定时继续依靠原有冻结 `system_prompt`，不得从文本反推并补建绑定。

运行时组装时，continuation 模式应形成“原作关系起点 + AfterStory 后续发展”；separate 模式应形成“原作主角关系 + 当前用户独立关系”。两部分必须使用不同标题和数据来源，运行时 Relationship 的证据仍只能来自该实例中的 AfterStory 互动。

### 6.3 关系边

K0 已新增 `character_relations.jsonl`。每条边至少包含：

| 字段 | 含义 |
| --- | --- |
| `relation_id` | 稳定关系记录 ID |
| `source_character_id` / `target_character_id` | 两端人物 |
| `category` | `family`、`organizational`、`cooperative`、`social`、`protective`、`adversarial`、`romantic` 或 `other` |
| `label` | 人可读的准确关系，如“同事”“警惕”“临时合作” |
| `directionality` | `directed` 或 `symmetric` |
| `summary` | 关系含义及边界，不写成单个分值 |
| `canon_checkpoint` | 关系被确认的剧情点 |
| `valid_from_checkpoint` / `valid_to_checkpoint` | 关系有效区间 |
| `confidence` / `review_status` | 证据强度和审核状态 |
| `evidence_ids` | 支持关系的中立证据 |
| `supersedes_id` | 关系变化时连接前一记录 |

同一对人物允许同时存在多条边。例如两人可以是同事，同时一方警惕另一方；“同事”可以对称，“警惕”必须有方向。关系变化通过新增边和有效区间表达，不覆盖早期状态，也不计算好感度。

关系图按用户选择的 Canon checkpoint 生成。默认只显示 `accepted`；`supported` 证据可以用虚线展示，`provisional` 默认隐藏，避免推测看起来像官方设定。

## 7. 中立证据与来源定位

K0 已新增 `canon_evidence.jsonl`，作为人物事实、世界事实和人物关系共同使用的证据单元。证据来源严格二选一：

- `scene`：剧情画面证据，必须定位 Scene、source part 和起止时间；
- `profile`：游戏个人档案证据，必须定位 Profile 与具体字段/条目，不能混填剧情时间。

每条记录至少包含：

- `canon_evidence_id`；
- `origin_type`：`scene` 或 `profile`；
- Scene 来源使用 `scene_id`、`source_part_id`、`start_ms` / `end_ms`；
- Profile 来源使用 `profile_id` 和结构化 `profile_locator`；定位器严格分为档案字段 `field`、档案条目 `archive`、语音条目 `voice`，并分别记录字段名、条目标题或语音分类与标签；
- `evidence_kind`：剧情来源使用 `dialogue`、`action`、`document`、`broadcast`、`visual`；档案来源使用与定位器匹配的 `profile_field`、`profile_archive` 或 `profile_voice`；
- `actor_character_ids` 与可空的 `speaker_character_id`；
- `observation`：画面或文本直接可观察的事实摘要；
- `transcript_refs`：对应已复核台词 ID；
- `review_status` 与复核备注。

证据正文使用必要的短摘要和时间定位，不在 Git 中复制大段视频字幕。说话者未知时保持空值；不能为了生成关系边强行猜测。

现有 `evidence.jsonl` 继续专门保存人物表现解释，并引用 `scene_id`。后续实施时可以增加对 `canon_evidence_ids` 的可选引用，但本阶段不合并两种证据，也不破坏现有 Trait 链。

## 8. 时间、版本与剧透规则

### 8.1 三种时间不能混用

- **来源时间**：视频中的分 P 和毫秒位置，用于回看证据；
- **Canon checkpoint**：剧情发布/章节顺序，用于判断角色当时知道什么；
- **故事内时间**：故事发生的日期或先后关系，只有剧情明确时才记录。

视频时间戳不能代表故事时间，文件采集日期也不能代表剧情进度。

### 8.2 Checkpoint 注册表

K0 已新增 `canon_checkpoints.jsonl`，统一 checkpoint ID、显示名称、作品版本、章节顺序、内容轨道、前置 checkpoint 和剧透范围。`content_track` 固定为 `main_story`、`side_story`、`character_story`、`event_story` 或 `unknown`，用于区分主线、番外、角色故事和活动；全局 `sequence` 仍表示同一作品的发布/剧透顺序。事实、关系、场景和 Character Version 都引用注册表中的 ID，避免各文件自由填写“1.0”“第一话”“序章”等不一致值。

当事实被后续剧情推翻时，保留旧记录，把 `valid_to_checkpoint` 指向变化点，并由新记录通过 `supersedes_id` 连接。这样可以生成“序章时的人物地图”和“1.4 时的人物地图”，也能避免早期角色版本提前知道后期反转。

## 9. 从 P1 到正式知识的审核流程

P1 当前完成的是逐条画面复核，下一步不能直接生成最终人设。建议采用以下固定门禁：

1. 把机器场景草稿整理为语义完整的正式 Scene；
2. 为 Scene 补 `source_part_id` 和确定的 Canon checkpoint；
3. 从画面、台词、动作、文档和播报生成中立 Canon Evidence；
4. 做实体消歧：匹配现有人物和世界实体，未知命名人物先登记为 `discovered`；
5. 分别生成 character fact、world fact、character relation 候选；
6. Agent 回看证据，接受、拒绝或保留 provisional，并生成 HTML 审核报告；
7. 只有 `accepted` 记录进入人物地图、世界知识和关系图；
8. 需要改变 Character Definition 的结论再经过单独的人设审核和不可变版本发布。

抽取模型可以提出候选，但不能直接将候选标为 `accepted`。重复台词、同一事实的多次提及应合并为一条事实并追加 evidence ID；内容冲突时保留多条带来源和有效期的记录，不用最后出现的文本静默覆盖。

## 10. K0 已完成的两个最小修正

K0 已在正式 P1 入库前解决两个结构缺口：

1. `SceneRecord` 已增加必填 `source_part_id`，并验证分 P 属于对应 source、场景时间不超过分 P 时长。多分 P 的相同时间戳现在可以唯一定位。
2. 原 `EvidenceRecord` 继续描述人物表现；新的独立 `CanonEvidenceRecord` 同时支持档案和剧情来源，为三张知识视图提供共同中立证据，且不破坏 Trait 链。

两项都只发生在研究库。本地正式 `scenes/evidence/traits` 仍为空，因此不涉及旧场景迁移、生产数据库、CharacterInstance 或聊天数据。

## 11. 推荐实施阶段

| 阶段 | 范围 | 验收停止点 |
| --- | --- | --- |
| K0（已完成） | 增加 checkpoint、world entity、Canon evidence、facts、relations 的严格模型、引用校验和空文件 | Schema/校验/SQLite 隔离重建测试通过，未导入 P1 |
| K0.1（已完成） | 增加结构化人物别名与剧情轨道，收紧档案定位，区分 `canon_status` 与运行时 State | 本地 SQLite Schema 1.1 原子重建，既有档案索引保持不变 |
| K1 | 修正 Scene 的 source part 定位；把 P1 生成正式 Scene 和 Canon Evidence | P1 每条正式证据能回到分 P、时间和审核画面 |
| K2 | 从 P1 形成第一批人物事实、世界事实和关系边，Agent 完成审核 | 三个视图只包含 accepted 记录，未知项保持未知 |
| K3 | 生成静态人物地图、世界知识页和关系图审核视图 | 可按 checkpoint 查看，能从节点/边回到证据 |
| K4（进行中，P1–P18 已完成） | 使用同一流程逐 P 处理后续剧情，按批次推进 | 每个分 P 独立完成、验证和提交，不一次跑完整合集 |
| K5 | 在 Canon 资料进入 Provider 前实现 Instance Canon Role Binding、兼容性校验和上下文消歧 | continuation 不产生“第二个主角”，separate 不继承主角经历；旧实例不自动绑定 |
| K6 | 从累计证据更新 Trait 与正式角色资料候选 | 单独审核后才建立新 CharacterVersion；旧实例不变 |

## 12. 集中审核项与建议

1. **人物收录范围**：建议收录所有命名剧情人物，而不只收录可操作角色。影响是目录会更大，但一段剧情只需解析一次，关系图不会因配角缺失而断裂。
2. **主角建模**：建议继续只使用一个 `esper-zero` Canon 节点，画面性别/外观放在来源上下文。影响是关系不会重复；若未来证实路线剧情有实质差异，再增加分支。
3. **关系词表**：建议使用“少量 category + 准确自然语言 label”，不预先建立几十种关系枚举。影响是首版易维护，后续仍可按审核结果扩充受控词表。
4. **不确定关系显示**：建议 accepted 默认实线展示，supported 可切换为虚线，provisional 默认隐藏。影响是地图可表达证据强弱，又不会把推测伪装成 Canon。
5. **下一实施阶段**：K0–K4 已完成 P1–P18 闭环（批次一 P5–P8、批次二 P9–P11、批次三 P12–P15、批次四 P16–P18）；后续按批次继续 P19–P22，每批次内仍以单个分 P 完成抽取、复核、提升、事实与视图刷新、验证和提交；跨 P Trait 归纳在全部批次完成后统一进行。

## 13. 后续实施验收方向

- 任一人物、世界事实或关系都能回溯到 source part、时间段、Scene 和复核状态；
- 多分 P 时间戳不会冲突，未知说话者和未知实体不会被强制猜测；
- 同一 checkpoint 可稳定生成三张视图，换 checkpoint 后历史关系不会被后期事实污染；
- Character Canon 关系与 AfterStory 运行时 Relationship 在模型、文件和调用链上均无交叉写入；
- continuation 模式只把选中的 Canon 角色关系作为实例起点，Provider 不会同时把原作主角当成第三个人；
- separate 模式不会继承原作主角的关系或共同经历，缺少绑定时不会自动猜测身份；
- Canon 更新、关系纠正和运行时关系变化均不能修改已有绑定；切换身份模式必须创建新实例；
- 不同用户、角色实例和绑定之间保持隔离，Canon 数据中不出现现实 `user_id`；
- 重复证据追加引用，冲突事实保留版本，不覆盖历史；
- P1 的正式入库流程可重复验证，失败不会留下半写入数据；
- 未经审核的数据不能进入 Character Definition 或聊天 Provider 输入。
