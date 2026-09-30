# Conversation Response Policy v1 实施记录

状态：2026-09-30 已实现并完成可用环境内的工程验收。

## 实施范围

本阶段新增版本固定为 `1.0` 的共享回复策略，继续复用 Character Definition、ContextAssembler、Conversation Decision 1.0 和单次 Provider 调用。策略负责当前目标、新旧话题、回复顺序、篇幅、追问、建议分寸、角色自主、记忆引用和跨世界行动边界；不读取或保存具体用户运行数据。

Provider 输入顺序保持为角色冻结提示、Memory / State / Relationship / Continuity 等运行资料、对话数据说明、Response Policy、Conversation Orchestrator。结构化 Provider、旧纯文本 Provider 和结构化失败后的安全降级都使用同一策略。Conversation Decision Schema、effects/outbox、ContextAssembler 数据读取和数据库模型没有改变。

## Token 预算

普通聊天总输入仍为 24000 token，输出仍为 1024 token。Recent History 从 9000 调整为 8200，Runtime/Policy Overhead 从 1000 调整为 1800；Character 2500、Memory 3000、State/Relationship 500、Continuity 4000 和当前消息 4000 均保持不变。

固定 Response Policy 与 Conversation Orchestrator 的保守估算总量受 1800 token 测试约束。ContextAssembler 的直接构造默认值、Settings、`.env.example`、诊断预期和文档使用同一组数值。

## 场景评测

新增 17 个合成场景，覆盖普通聊天、具体回应好消息、只倾听、明确求建议、事实回答、先给部分答案、纠正记忆、跨会话续接、新话题优先、相关记忆、告别、角色自主、关系边界、跨世界行动、明确记住、明确提醒和一轮多问。

评测把错误事实、操作 effect 缺失、明确边界违反、内部字段泄露、关系无依据升级和跨世界假执行作为硬失败；自然措辞覆盖与默认追问数量作为软质量，并要求至少 80% 场景无需修改即可使用。最终 DeepSeek 回放共 17 次结构化调用：硬失败 0，软质量 15/17，通过率 88.2%。两个软告警是一轮多问，以及新话题回复用代词承接而未复述 fixture 中的名词；回复仍处理了正确话题。

评测只使用合成角色、合成上下文和进程内 Provider 输入，没有写入数据库、默认用户数据或正式角色资料。原始报告保存于未跟踪的 `.local-run/response-policy-evaluation.json`。

执行入口：

```powershell
uv run python -m scripts.evaluate_response_policy --profile deepseek
```

## 自动检查与环境边界

- Response Policy、评测器、配置、Provider 与 Conversation Decision 的 34 项相关无数据库回归通过，其中本阶段直接新增或调整的定向检查为 13 项。
- Ruff 与 `git diff --check` 通过。
- 真实模型场景达到 0 个硬失败、88.2% 软质量通过。
- 本阶段没有新增数据库模型或 migration，也没有修改前端。
- 当前机器的 Docker API 不可用，未重复执行依赖 PostgreSQL 的 96 项完整后端回归、Alembic 一致性和隔离 schema 检查；本阶段涉及的 Provider、固定提示与配置检查已独立通过。数据库恢复后应使用既有 `uv run pytest -q` 与 `uv run alembic check` 补做回归。

## 当前边界

策略是可开始实际聊天的统一基线，不替代正式角色 Definition 的内容质量，也不保证随机模型每轮都严格遵守软表达偏好。后续应由用户持续聊天并保存不满意的具体轮次，再将可复现问题加入场景 fixture。离线通知、Voice、Tools、完整 Canon、Character Schema v2、第二次 planner 调用和前端调整均未进入本阶段。
