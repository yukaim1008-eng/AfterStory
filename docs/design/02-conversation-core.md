# 理解与回复

状态：Conversation Core v1 已于 2026-09-27 实现。2026-09-30 已形成 [Conversation Response Policy v1 完整待审稿](conversation/01-response-policy-v1.md)，用于把现有结构化理解收敛为可长期试聊的回复行为；尚未授权实施。

## 职责与边界

本模块负责组织 Character Definition 的冻结提示词、Runtime Context 和当前消息，生成框架无关的 Character Response。它不保存或暴露模型思维链，也不把 Memory、State、Relationship 写回 CharacterVersion。

运行时上下文继续由 `ContextAssembler` 按既有顺序提供：

1. CharacterVersion.system_prompt
2. Personal Memory
3. Character State / Relationship
4. Continuity Summary / Open Topics
5. Recent History
6. Current Message

Conversation Core 只解释这些输入并提出本轮决策。Memory、Matter、State 和 Relationship 各自由原有领域服务校验和持久化。

## Conversation Decision v1

契约版本和编排器版本均为 `1.0`。模型必须返回且只能返回：

- `reply`：角色自然回复。
- `intent_labels`：本轮意图标签，只用于诊断和契约检查。
- `memory_commands`：明确记住、纠正、忘记命令。
- `reminder_commands`：精确提醒或时间尚不完整的持续事项。
- `state`：有真实依据、会影响后续表达的短期状态 proposal。
- `relationship`：重大或重复互动形成的关系证据，以及证据足够时的定性快照 proposal。

未知字段、错误类型、缺失字段和非法枚举都会被拒绝。普通“我叫……”“我喜欢……”仍交给后台稳定事实提取，不被当作用户明确要求立即记住。

## Provider 输入和失败降级

`ContextAssembler` 不因本阶段重构。进入结构化 Provider 前，所有 system 内容合并为一条系统消息，既往 user/assistant 原文序列化为 history 数据，当前输入单独标记为 `current_user_message`。这样既保留原上下文，又避免历史中的普通 assistant 回复干扰 JSON 输出格式。

若 Provider 不支持结构化输出，继续使用旧的纯文本回复路径。结构化输出为空或契约不合法时，系统进行一次受限的纯文本降级；降级提示禁止声称已完成记忆、纠正、删除或提醒。其他 Provider 错误继续按原有 502 边界处理。

## 命令授权与受控提交

模型输出不是写库权限。提交前还有确定性授权：

- 记住、纠正、忘记和提醒必须能在当前用户原文中找到相应的明确表达。
- 纠正和忘记必须引用本轮 Runtime Context 中实际可见的 `memory_id + revision`。
- 所有目标仍由领域服务再次检查用户、实例、revision 和状态。
- 普通轮数、长时间未聊天和用户单方面宣称关系不会升级 Relationship。
- Relationship 至少需要来自两个不同成功轮次的有效证据。

assistant 消息与待执行 effects 在同一数据库事务中落库。effects 使用现有 `memory_jobs` 作为 outbox；同步提交失败或进程中断后，worker 可以按 lease 重试。记忆 operation ID、事项 request ID、State request ID 和关系证据键都具备幂等边界。

API 的 Character Response 增加 `effects` 回执，状态为 `committed`、`deferred`、`skipped`、`failed` 或任务处理中状态。模型生成的回复先作为候选保存；显式 Memory / Matter 操作全部得到 `committed` 回执后才发布候选回复。失败或仍待恢复时，消息正文会替换为不声称成功的安全说明；worker 恢复成功后，同一 request ID 会恢复原候选回复。内部 State / Relationship proposal 不影响普通回复发布。

## 当前边界

- 自动稳定事实/事件提取仍由 Memory worker 独立完成，不与显式命令混成同一套判定。
- 精确提醒目前只支持站内投递；应用关闭后的系统通知留到 Tools 编排阶段。
- 不生成或保存完整思维链。
- 不包含 Voice、TTS、完整 Canon、Character Schema v2 或前端角色编辑器。
- 当前是完整文本回复，不是流式输出。

实现和验收记录见 [Conversation Core v1](../implementation/conversation-core-v1.md) 与 [真实模型评测](../implementation/runtime-evaluation.md)。
