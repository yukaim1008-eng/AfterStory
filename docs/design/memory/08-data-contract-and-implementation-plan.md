# Memory System 数据契约与实施阶段

状态：2026-09-23 完整待审稿，未授权实现。本文把连续性、长期记忆、持续事项、召回、生命周期、State 和 Relationship 方案收拢为可实施边界；字段名称仍可在编码前微调，但职责、依赖和兼容原则应先经用户审核。

## 1. 总体数据流

```text
成功 Turn / 显式用户操作
        ↓
持久化任务与固定来源快照
        ↓
摘要 / 事实事件提取 / 事项操作 / 关系证据候选
        ↓
应用校验、去重、版本与依赖提交
        ↓
权威 Memory 数据 + 可重建索引/摘要/快照
        ↓
本轮 Retrieval & Context Preparation
        ↓
ContextAssembler 有界组装
        ↓
Text Provider 回复 + 可选 State proposal
```

所有模型调用在数据库长事务和实例行锁之外。模型输出是经过 Schema Validation 的候选，不直接修改数据库。提交时重新检查实例语义修订、来源可见性和任务 lease。

## 2. 权威数据与派生数据

| 层 | 数据 | 是否权威 | 能否重建 |
| --- | --- | --- | --- |
| 原始交流 | Conversation、Turn、Message | 是 | 否 |
| 长期记忆 | 事实/偏好/经历的实体和不可变修订 | 是 | 版本不可从摘要反推 |
| 持续事项 | Matter、Reminder、Schedule revision | 是 | 否 |
| 用户操作 | 更正、删除、抑制、完成、取消 | 是 | 否 |
| 来源依赖 | Source link、Dependency link | 是 | 部分可重新分析，但不能假定完全恢复 |
| 压缩材料 | Segment summary、Continuity note | 否 | 是 |
| 读取优化 | Embedding、全文文档、缓存 | 否 | 是 |
| 运行快照 | State、Relationship 当前描述 | 否；事件依据权威 | 是 |

权威数据使用事务、expected revision 和幂等键保护。派生数据必须带来源版本和生成器版本；删除派生数据不会丢失用户事实，删除权威数据也不能靠派生内容恢复。

## 3. 推荐表与职责

这是逻辑表清单，不要求一次迁移全部建立。

### 3.1 长期记忆

**`personal_memories`（保留现有表作为实体根和当前投影）**

- 保留 `id`、`instance_id`、当前 `content/status/revision` 及现有 API 兼容。
- 增加逻辑类型，例如 `fact`、`preference`、`event`；证据性质另存，不能继续让 `kind` 同时表达内容类型和事实/推测。
- 现有 `source_message_id` 仅作旧数据主来源兼容，新流程以多来源表为准。

**`personal_memory_versions`**

- 每次新增、变化、纠正、删除形成不可变版本。
- 保存 schema version、类型化 payload、证据性质、状态、有效时间/精度、操作类型、前一版本和创建时间。
- `(memory_id, revision)` 唯一；根表保存当前投影，版本表保存历史。

**`memory_source_links`**

- 将一个记忆版本关联到多个 Message/Turn 或显式手动操作。
- 保存 role、消息内可选 span、来源用途和原文散列。
- 一条消息可支持多条记忆；同一记忆可跨多轮。

**`memory_dependencies`**

- 记录摘要、笔记、State/Relationship 依据、索引文档等对权威版本/来源的依赖。
- 支持直接失效和受控重建；不能存成自由文本路径。

**`memory_suppressions`**

- 保存用户要求不再用于模型的实体、来源范围或经确认主题。
- 正文最小化，保留幂等、防复活和执行所需信息。

### 3.2 长会话压缩

**`conversation_segments`**

- 实例、会话、实际成功 Turn 清单、序列范围、时间范围、来源修订和覆盖状态。
- 失败/处理中 Turn 不计入已覆盖范围。

**`segment_summaries`**

- 分段结构化摘要、生成器版本、来源内容散列、发布状态。
- 重建产生新版本；旧版本失效但不覆盖审计。

**`continuity_notes`**

- 按实例内话题保存当前进度、未答问题、最后相关来源、主动提起策略和状态。
- 跨会话可引用，不能因 Conversation 切换自动结束。

### 3.3 持续事项与提醒

**`ongoing_matters`**

- 类型、当前状态、内容、下一步、时间范围/精度、主动提起策略、修订和来源。

**`matter_revisions`**

- 保存创建、改期、完成、取消和策略变化的不可变历史。

**`reminders`**

- 关联事项、当前 schedule revision、绝对触发时间、时区语义和状态。

**`reminder_deliveries`**

- occurrence/channel 的领取、lease、送达和失败状态。
- 稳定唯一键防止启动、前台恢复、轮询和聊天准备重复投递。

### 3.4 后台处理与检索

**`memory_jobs`**

- job type、实例、来源范围、目标语义修订、payload hash、状态、attempt、lease、错误码和时间。
- 支持摘要、提取、重建、索引及关系评估；任务正文不复制完整私人内容，只引用权威来源。

**`memory_index_documents`**

- 指向具体有效版本/摘要，保存用于全文检索的受控文本、Embedding 模型版本和向量。
- PostgreSQL 全文与 pgvector 是派生读取优化；权威状态硬过滤始终生效。

### 3.5 State 与 Relationship

**现有 `character_states` / `relationships`** 继续作为当前快照，增加生成时间、持续性质或快照依赖版本等必要元数据。

**`state_events`** 逐步收窄为 State 变化事件；不再要求同一行同时改三个关系方面。

**`relationship_evidence`** 保存影响 familiarity/trust/closeness 的有效事件、方向语义、理由和来源。

**`relationship_revisions`** 保存各方面定性快照的不可变变化；普通轮次不产生版本。

## 4. 类型化 payload 原则

不同记忆类型共享版本与来源机制，但 payload 由独立 Validation Model 校验并带 schema version：

- Fact/Preference：主体、事项、内容、条件、否定、场景、有效时间。
- Event：主题、参与者、场景、发生时间/范围与精度、经过、当前结果、开放问题。
- Summary：话题、经过与变化、结论、未完交流、精确片段引用。
- Matter：类型、内容、下一步、状态、计划时间、主动提起策略。

JSONB 适合保存各类型逐步演进的结构，但权限、状态、实例、修订、时间和常用过滤条件使用明确数据库列。未知字段拒绝；版本不匹配不能静默忽略。不要建立一个无验证的万能 JSON 字段。

## 5. Provider 与领域接口

现有 `TextProvider.generate(messages) -> str` 保留给角色回复。Memory System 增加框架无关的结构化边界，具体模型可共享底层客户端：

- `SummaryProvider.summarize(input) -> SummaryCandidate`
- `MemoryExtractionProvider.extract(input) -> list[MemoryOperationCandidate]`
- `RetrievalReranker.rerank(input) -> RankedCandidateIds`
- `EmbeddingProvider.embed(texts) -> vectors`
- Character Response 未来可带 `state_proposal`；若暂时继续字符串 Provider，则通过独立解析/评估适配，不让数据库模型依赖 Provider JSON。

所有返回先经过严格 schema 校验、大小限制和引用检查。候选只引用输入中提供的稳定 ID；模型不能发明数据库 ID、用户权限或来源。Provider 超时和格式错误产生可重试错误，不提交半份结果。

Prompt/Extractor/Summary/Reranker 都有独立版本常量，保存到相应派生记录。更换模型或 Prompt 不自动重写权威记忆；需要重建时创建显式任务。

## 6. 后台任务执行模型

V1 不必引入外部队列或 LangGraph。推荐先用 PostgreSQL 持久化任务表和普通 Python worker：

1. 成功 Turn 或显式操作在同一业务事务内登记 job/outbox。
2. worker 使用有界批量和 `FOR UPDATE SKIP LOCKED`/等价 lease 领取任务。
3. 读取固定来源快照后释放锁，在事务外调用模型。
4. 短事务提交前核对 lease、实例修订、来源可见性和幂等结果。
5. 失败采用有限退避；永久格式错误记录错误码，不能无限热循环。

服务重启后 lease 过期任务可恢复。相同 job key 只发布一个有效结果；用户更正/删除产生更高目标修订，使旧任务无法提交。

开发环境可以由 API 进程启动轻量 worker，但生命周期清楚、测试后停止；正式部署可拆成独立进程而不改领域接口。

## 7. Runtime 与 ContextAssembler 接入

建议把现有发送链路分为四段：

```text
prepare_context（锁外，可做检索/回读/必要重排）
  → reserve_turn（短事务，核对实例修订并预留 Turn）
  → Text Provider（锁外）
  → finish_turn（短事务，拒绝过期结果并登记后台任务）
```

当前代码在 `begin_turn` 的持锁事务内调用 ContextAssembler；实施长记忆前需要最小调整为上述准备/核验边界。request ID 幂等、conversation busy、attempt lease 和旧回复拒绝必须保持。

ContextAssembler 不发起网络请求、不查询无限历史，也不自己生成摘要。它接收 `PreparedRuntimeContext`，按已审顺序输出 Provider Messages。准备结果包含 instance ID、context revision、选择原因、预算统计和稳定来源 ID，但完整组装 Prompt 仍不持久化。

## 8. API 兼容与新增入口

现有 PersonalMemory API 在迁移期继续工作：手动创建产生事实型版本，更新/删除走新生命周期服务；返回结构可向后兼容地增加类型、来源和时间。

候选新增接口：

- `GET /instances/{id}/memory-items`：统一查看当前事实、偏好和经历。
- `PATCH/DELETE /memory-items/{id}`：带 expected revision 的纠正/删除。
- `GET/POST /instances/{id}/matters` 及事项完成、改期、取消操作。
- `GET /instances/{id}/reminder-deliveries/due`：领取线上到期项；另有 delivered/failure 确认。
- 内部 job、摘要、State 和 Relationship 评估不直接开放为用户写入 API。

最终路由和页面在各实施阶段确定。用户输入 `user_id` 继续由服务端身份注入，不能放进请求体绕过隔离。

## 9. Migration 与旧数据

所有变更采用附加式 Alembic migration：先增表/可空列和索引，再回填兼容版本，最后切换读路径。不得删除开发持久化数据、自动把旧消息猜成结构化事件或重写旧角色实例。

现有 `personal_memories`：

- 每条当前记录可生成一个标记 `legacy/manual` 的初始 version，正文和状态保持不变。
- 原 `source_message_id` 转为一个来源链接；没有来源的手动输入保留 manual origin。
- `fact/inference` 信息保留为证据性质；不自动猜偏好、人物、时间和事件结构。
- 删除墓碑继续有效，回填和 worker 不能使其复活。

现有 State/Relationship 快照继续可读；没有完整证据的旧快照标为 legacy provenance，记忆纠正时仍采用现有整体失效保护。

每个 migration 在隔离 PostgreSQL schema 验证 upgrade/downgrade、旧数据值、外键和实例引用。项目首次正式发布前是否压缩 migration 历史是单独仓库维护决定，不在功能实现中擅自删除已提交迁移。

## 10. 实施阶段

以下阶段是推荐执行顺序；用户审核整套设计后再授权编码。每阶段实现、验证、同步文档并单独提交。

### M0：评测样本与结构契约

- 建立 Memory Validation Models、Provider 候选契约、带人工预期的多会话回放样本和 token 计量接口。
- 不改变线上聊天行为。
- 验收：结构拒绝未知字段；样本覆盖事实、事件、时间、纠错、删除、续聊、事项和关系。

### M1：来源、版本、任务与可见性基础

- 新增版本、多来源、依赖、任务和抑制基础表；兼容现有 PersonalMemory。
- 建立同步可见性屏障和旧 `history_floor_revision` 回退。
- 验收：旧数据不丢失；显式 CRUD 兼容；任务幂等；删除后所有新读取路径不可见。

### M2：分段摘要、连续性笔记与长会话预算

- 实现提前压缩、覆盖游标、续聊材料、近期原文和硬上限等待/重试。
- 调整 prepare/reserve/finish 边界，消除持锁网络调用风险。
- 验收：数百轮模拟、跨会话续接、摘要失败和重启恢复、无静默截断。

### M3：事实、偏好与经历自动整理

- 实现后台增量提取、事件稳定身份、时间精度、两层去重和版本更新。
- 显式“记住/纠正/忘记”采用可验证操作。
- 验收：同事件跨批次不重复；推测/假设不污染事实；变化与纠错分开。

### M4：混合召回与 Runtime Context

- 接入结构化/全文候选、Embedding Provider、pgvector、重排和原文回读。
- ContextAssembler 消费 PreparedRuntimeContext。
- 验收：相关性、时间问题、精确引用、降级、预算及跨实例隔离。

### M5：持续事项与线上提醒

- 实现事项/提醒版本、站内到期领取、错过补发、改期取消和投递 lease。
- 第一版只做单次线上提醒，不实现应用关闭后的通知渠道。
- 验收：多入口并发一次投递；旧 occurrence 不补发；模糊时间不虚假承诺。

### M6：细粒度生命周期与重建

- 扩展依赖传播、摘要/索引重建和 span 级来源；逐步减少粗粒度历史丢失。
- 旧数据或依赖不完整时继续保守回退。
- 验收：纠错/删除不回流，排队旧任务不复活，无关历史在有充分来源时可以保留。

### M7：State 与 Relationship 自动演进

- 接入 State proposal、时间有效视图、关系证据和慢速评估。
- 不实现数值好感度、自动恋爱或缺席惩罚。
- 验收：短期/长期分离、证据可追溯、删除后重建、角色边界不被覆盖。

### M8：管理界面与整体验收

- 扩展现有 Memories 页面查看事实、经历和事项，支持纠正、删除、完成、取消及来源说明。
- 集中回放完整链路，比较现有 12 轮、仅摘要和完整方案的质量、token、延迟与错误率。
- 在真实模型调用前使用 fake Provider 完成工程测试；真实回放使用隔离身份和明确预算。

## 11. 不进入本阶段的内容

- 应用关闭后的系统通知、邮件、微信或日历写入。
- 完整 Tools 编排或 LangGraph。
- Canon 自动抓取、Lore RAG 或角色资料自动更新。
- 自动恋爱状态机、公开好感度、关系进度条。
- Voice/TTS、主动语音提醒。
- 跨角色共享私人记忆或跨用户记忆。
- 用 Memory System 重写 Character Definition。

## 12. 总体验收与发布门槛

工程门槛：migration 升降级和旧数据保持；跨用户/角色/实例隔离；任务恢复与并发幂等；锁外模型调用；删除即时屏障；Provider 全部可用 fake；Context token 不超预算；Ruff 和后端测试通过。

效果门槛：信息提取、跨会话续接、时间推理、知识更新、依据不足时不乱答、重复事件控制、原文精确回查、事项提醒、情绪连续及关系边界。每类都有成组对话和人工预期，不只检查 JSON 格式。

运行门槛：测量摘要/提取/Embedding/重排的调用量、p50/p95 延迟、积压、失败率、token 和索引大小；模型或参数选择以项目回放结果为准。

隐私与控制门槛：用户能查看并纠正/删除保存数据；界面准确说明删除范围；日志脱敏；被删除内容不通过摘要、索引、状态或旧任务回流。

## 13. 用户集中审核清单

1. 自动保存明确稳定信息；V1 不自动固化人格推测。
2. 事件保留最高可靠时间精度，日常表达可以更模糊。
3. 第一版单次线上提醒和站内呈现方式。
4. V1 使用 PostgreSQL 全文 + pgvector 混合召回，并允许 Embedding 失败降级。
5. 删除保存记忆与“忘记相关内容”的语义区别。
6. 来源不足时优先安全、允许暂时损失局部连续性。
7. State 随回复提出，Relationship 依据事件慢速评估。
8. 无数值好感度、无自动恋爱、无缺席惩罚。
9. M0–M8 的实施顺序和每阶段独立验收。

审核通过只代表设计定稿；开始编码仍以用户明确授权的实施范围为准。
