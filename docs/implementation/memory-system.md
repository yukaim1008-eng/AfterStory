# Memory System 实施记录

状态：2026-09-25 开始连续实施。用户授权按 M0–M8 完整开发、逐阶段验证并统一验收；本记录只描述已经完成的代码，不把设计稿自动视为实现结果。

## M0：评测样本与结构契约

验收矩阵：

| 输入/触发 | 预期 | 失败/边界 | 证据 |
| --- | --- | --- | --- |
| 合法事实、事件、摘要候选 | 严格解析并归一化空白 | 未知字段、错误类型和非法操作组合拒绝 | `tests/test_memory_contracts.py` |
| 事件时间 | 保留精度、时区及来源 | 已知精度无起点、未知精度带时间拒绝 | 同上 |
| 多会话回放样本 | 覆盖提取、时间、更新、拒答、提醒、关系和删除 | 样本 ID 不重复 | `fixtures/memory_evaluation.json` |
| 上下文预算预估 | 无外部 tokenizer 时提供稳定保守计量接口 | 空文本为 0 | 同上 |

实现结果：新增 `memory_contracts.py`、10 组多会话评测样本和 6 项契约测试；目标 Ruff 与测试通过。生产聊天链路未改变。

## M1：来源、版本、任务与可见性基础

- `personal_memories` 保持兼容投影，新增不可变 `personal_memory_versions` 和多来源链接。
- 新增依赖、抑制和 PostgreSQL job/lease 基础表；job key 保证幂等，过期 lease 可恢复。
- `CharacterInstance.data_revision` 用于数据/索引变化；`context_revision` 继续保护在途回复。
- 新消息保存服务端记录时间、解释相对日期所用时区及其来源；旧消息不猜测时区。
- 显式记忆 CRUD 双写版本链，删除投影立即不可见，旧 API 保持兼容。

验证：M1 定向 Ruff 通过；基础、现有记忆与会话测试共 17 项通过（与 M2 边界测试同批运行）。

## M2：分段摘要与跨会话连续性

- 成功 Turn 以固定、有界批次形成 segment，摘要严格核对 covered turn IDs 和来源 hash。
- 摘要是可重建派生数据；未完成话题形成实例级 continuity note，可跨 Conversation 使用。
- 最近原文仍按轮次保留；旧原话可通过同实例、有上限的关键词回读定位。
- 会话发送改为 `prepare_context → reserve_turn → provider → finish_turn`，准备阶段与 Provider 均不占用数据库行锁；预留时复核安全修订。
- ContextAssembler 在角色、长期资料和运行状态之后加入较早摘要/未完话题，再加入近期原文与当前消息。

验证：跨会话摘要、未完话题、原文回读和准备/预留边界测试通过；无真实模型调用。

## M3：事实、偏好与经历自动整理

- 成功回复与消息在同一事务登记提取/摘要 job；payload 只保存稳定 ID。
- 提取 Provider 输出必须通过严格契约并引用本次输入消息；候选在模型调用后短事务提交。
- 事实/偏好按主体、属性和场景，事件按标题、场景和时间精度形成稳定 key；跨批次重复候选幂等去重。
- 自动新增只推进 `data_revision`，不会令正在生成的回复连续失败；自动纠正先返回 deferred，等待显式确认。
- “记住/纠正/忘记”提供持久化 operation receipt，同一 operation ID 返回原结果。

验证：自动新增、跨轮去重、后台 job 登记、双修订和显式回执测试通过；使用 fake extractor。

## M4：混合召回与 Runtime Context

- 可重建 index document 同时保存 PostgreSQL 全文向量和 pgvector Embedding；切换至 `pgvector/pgvector:pg17` 镜像。
- 候选先执行实例、有效状态、当前修订硬过滤，再按全文、向量相似度和可选 reranker 排序。
- `PreparedRuntimeContext` 记录选择 ID、原因和预算；ContextAssembler 只消费准备结果，不调用外部 Provider。
- 无 Embedding 或 reranker 时降级到全文/近期候选；条数与保守 token 预算均有硬上限。

验证：相关性、预算、跨实例隔离、Provider 最终输入和 pgvector 迁移均使用 fake embedding 测试通过。

## M5：持续事项与站内提醒

- 事项根记录与不可变 revision 分开；创建、改期、完成和取消使用 expected revision。
- 只有带时区的绝对时刻建立单次 reminder；月/日等模糊时间可保存为事项，但不会虚假承诺定时投递。
- occurrence key 随 schedule revision 固定；改期和取消使旧 occurrence 失效。
- 站内 delivery 使用 `FOR UPDATE SKIP LOCKED` 与 lease，多入口领取同一 occurrence 只成功一次；应用下次上线可领取错过但仍有效的提醒。
- 本阶段没有系统通知、邮件或应用关闭后的外部投递渠道。

验证：到期领取、重复领取、确认送达、模糊时间拒绝投递和改期取消旧 occurrence 测试通过。
