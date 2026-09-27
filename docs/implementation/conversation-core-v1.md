# Conversation Core v1 实施记录

状态：2026-09-27 已实现并完成统一验收。

## 实施范围

本阶段复用现有聊天、ContextAssembler、Memory、Matter、State 和 Relationship 服务，新增最小的结构化对话决策与受控提交层。没有新增数据库表或 migration，没有修改前端，也没有开始 Voice、Tools、Canon 或 Character Schema v2。

主链路为：

```text
ContextAssembler
  -> ConversationDecisionProvider 1.0
  -> strict ConversationDecision 1.0
  -> assistant message + effects outbox
  -> existing domain services
  -> CharacterResponse.effects receipt
```

## 结构化决策

`afterstory/conversation_contracts.py` 定义严格 Pydantic 契约：角色回复、意图标签、显式记忆命令、提醒命令、短期 State proposal 和 Relationship evidence/snapshot proposal。所有对象拒绝未知字段，字符串和枚举按各自领域规则校验。

`afterstory/conversation_provider.py` 负责构造固定编排提示、请求 JSON Object、校验响应并执行命令授权。历史 assistant 回复作为 JSON 数据传入，避免模型把旧的纯文本输出风格延续到本轮结构化输出。普通文本 Provider 保持兼容。

## 受控副作用

`afterstory/conversation_effects.py` 把模型 proposal 映射到现有服务：

- remember / correct / forget -> `ExplicitMemoryOperationService`
- reminder / imprecise matter -> `MatterService`
- short-term state -> `StateEvolutionService`
- relationship evidence / snapshot -> `RelationshipEvolutionService`

assistant 消息和 effects job 由 `Repository.finish_turn` 同事务保存。同步处理失败时保留 outbox，`MemoryRuntimeWorker` 优先恢复 Conversation effects，再运行自动抽取和摘要，避免后台抽取抢在明确操作之前。

模型回复在显式 Memory / Matter effect 提交前视为候选。全部用户可见操作回执为 `committed` 时返回候选回复；失败或任务仍在恢复时，数据库消息和 API 响应都使用不声称成功的安全说明。worker 后续恢复成功后，重复同一 request ID 会从 outbox 中恢复原候选回复。

显式纠正或忘记会建立既有上下文修订边界；同一批 effects 中的 State / Relationship proposal 会跳过，避免把已失效上下文继续写入运行状态。关系升级要求至少两个不同成功轮次的证据。

## 幂等与安全边界

- 同一消息 request ID 仍返回相同 assistant 消息和 effects 回执。
- 每条 memory command、matter、State 和 Relationship evidence 都使用确定性业务键。
- correct / forget 只能引用当前上下文可见且属于当前实例的 memory ID 与 revision。
- 模型对普通事实陈述过度生成命令时，确定性授权会拒绝执行。
- 非法 JSON、未知字段或空结构化响应不会产生副作用。
- 日志只记录计数、布尔结果、预算和安全错误码，不记录消息或记忆正文。

## 测试覆盖

自动化测试覆盖严格契约、固定 Provider 输入、输出预算、非法/空响应降级、过度命令拦截、否定命令拦截、不可见记忆目标拦截、记住/纠正/忘记、精确与模糊提醒、State、跨轮次 Relationship、失败安全回复、outbox 恢复候选回复和请求幂等。

真实模型 fixture 增加自然语言明确记住和精确提醒，并要求“杭州更正为苏州”通过 Conversation effect 提交，而不是只依赖后台抽取。所有真实运行均使用隔离 PostgreSQL schema，结束后自动删除。

## 未扩展内容

本阶段未新增 migration；`memory_jobs` 继续承担持久化任务和 outbox。前端暂不展示 effects 明细，现有聊天页面会忽略新增响应字段并继续正常工作。离线系统通知、复杂工具编排、正式角色内容和长期主观效果调优属于后续阶段。

## 最终验收

- 后端：91 项 pytest 通过。
- 静态检查：Ruff 与 `git diff --check` 通过。
- 数据库：Alembic 无待生成变更；现有隔离 schema 升降级/数据保留测试通过。本阶段无新 migration。
- 诊断：`scripts.doctor --profile fake` 通过，数据库可达且 revision 位于 head。
- 真实模型：隔离 schema 下 30/30 项通过，共 37 次结构化 Provider 调用；明确记住、即时纠正、精确提醒、自动提取、跨会话召回、20 轮摘要、隔离和站内提醒均通过。少量抽取首次返回不合约时由既有任务重试恢复，最终任务全部 completed。
- 前端兼容：生产构建和 32 项 Playwright 通过；没有修改前端代码。
- 服务清理：评测 schema 自动删除，Playwright 自启服务已退出；用户自行启动的 Docker 未停止。
