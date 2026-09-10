# 后端与数据边界

状态：M1 工程实现及 PostgreSQL 验证完成；真实模型调用待配置密钥。

## 职责与已确认约束

FastAPI、PostgreSQL、普通 Python 工作流；Provider、Repository 和接口模型保持清晰边界。遵循基线第 5 至 8 节。实现位于 `afterstory/`，数据库迁移位于 `migrations/`，运行入口见 [M1 运行说明](../running-m1.md)。

## 当前阶段需要整批解决

已整理为 [M1 最小后端文字链路](07-first-text-milestone.md)，包含模块契约、数据归属、请求重试与验收条件；用户已整批采纳前四项取舍，并选定 DeepSeek V4 Flash。

- 本地 PostgreSQL 启动方式、依赖与迁移方式。
- 用户身份来源与隔离检查，最小 API 和持久化契约。
- 文本 Provider 的首次真实接入方式、配置及错误处理。
- 最小链路验收命令与测试数据；测试替身和真实模型验证分别记录。

## 后续设计

Embedding/TTS 接入、日志及部署。M1 已实现数据库行锁、每轮请求标识、失败重试及过期处理恢复；`.env.example` 的 SQLite 遗留配置已修正，Compose 数据库已启动并通过验证。

## 验收方向

服务能启动；文字对话能持久化并在重启后恢复；请求隔离有效；错误可定位；已授权阶段有可重复的验证方式。
