# 后端与数据边界

状态：M1/F1 工程与真实模型基础链路已验证；F2 阶段 E 的诊断、日志和整体验证入口已完成。

## 职责与已确认约束

FastAPI、PostgreSQL、普通 Python 工作流；Provider、Repository 和接口模型保持清晰边界。遵循基线第 5 至 8 节。实现位于 `afterstory/`，数据库迁移位于 `migrations/`，运行入口见 [M1 运行说明](../running-m1.md)。

2026-10-17 后端代码按业务领域分包：`afterstory/api.py` 只创建应用、组装领域路由与公共中间件；`auth/` 管理登录、会话、账号命令及认证路由；`character/` 管理角色定义、Prompt Builder、导入与 Canon 研究；`conversation/` 管理对话编排、上下文、回复策略和 Repository；`memory/` 管理记忆、召回、摘要、状态、关系、持续事项与后台任务。共享 ORM 模型暂保留在 `afterstory/models.py`，配置、数据库连接、Provider 基础适配也维持现有位置。`afterstory.accounts` 与 `afterstory.seed` 保留为原命令兼容入口；这次分包不改变路由、数据库结构或用户数据。

本轮验证：43 项无需 PostgreSQL 的后端测试、Ruff、编译检查和 `git diff --check` 通过；原有 24 个 HTTP 方法/路径组合及其 `/api` 别名与重构后 OpenAPI 一致，除 `/auth/me` 把 worker 存在性改为等价布尔参数外，拆出的端点函数体与原版一致。147 项完整测试可以收集，但本机 Docker Desktop 启动时因临时 `dockerInference` socket 报错，PostgreSQL 引擎未启动，因此本轮没有完成数据库依赖测试；未运行迁移，也未修改持久化数据。测试尝试启动的 Docker 进程已关闭。

## 已完成的工程基础

已整理为 [M1 最小后端文字链路](07-first-text-milestone.md)，包含模块契约、数据归属、请求重试与验收条件；用户已整批采纳前四项取舍，并选定 DeepSeek V4 Flash。

- Docker Compose PostgreSQL、SQLAlchemy 数据访问、Alembic 迁移及运行说明。
- 服务端登录身份、会话所属检查、最小 API、持久化和失败重试；管理员命令创建账号，网站不开放注册。
- 文本 Provider、命名模型组配置及错误处理；真实模型基础连通已验证。
- 后端隔离测试、前端浏览器测试与独立身份真实联调；不同验证结果分别记录在当前状态。

## 已有模型配置与待选工作

模型配置使用简短的 `组名_字段`，例如 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`；每组独立绑定供应商、地址、密钥、model、超时和输出上限。`LLM_ACTIVE_MODEL=deepseek` 选择当前对话模型。其他模型采用相同格式，支持多个供应商和同供应商多个模型配置共存。运行示例见 [M1 运行说明](../running-m1.md)。

M1 已实现数据库行锁、每轮请求标识、失败重试及过期处理恢复；PostgreSQL 配置已验证。这是验证记录，不表示服务应持续运行。

F2 五阶段已按用户委托实施，范围与结果见 [实施方案](../implementation/f2-foundations.md)。阶段 A–D 完成历史、个人记忆、上下文和状态存储边界；阶段 E 增加只读诊断命令、请求关联日志与可清理自启依赖的整体验证脚本。正式认证、Embedding 和部署方式待设计；TTS 按语音模块约定暂缓。

部署前登录系统 v1 见[独立模块文档](platform/01-authentication.md)：已将 `current_user` 替换为服务端会话身份；旧本地用户数据不绑定新账号，并已按用户后续指示清理；服务器部署仍待单独验收。

`python -m scripts.doctor` 只输出配置是否齐全、数据库是否可达、迁移是否在最新版本，以及激活的模型组/供应商/模型名；不会输出密钥、连接串、驱动错误、提示词或聊天内容。HTTP 响应包含 `X-Request-ID`，安全日志只记录关联 ID、方法、路由模板、状态码、耗时和稳定错误码，不记录请求/响应正文或真实资源 ID。

`scripts/verify.ps1` 使用 fake Provider 运行迁移、诊断、Ruff、后端测试、前端构建和 Playwright。PostgreSQL 原本未运行时由脚本启动并在 `finally` 中停止；原本已运行时复用且不关闭。脚本不调用真实模型、不清空业务表、不删除命名卷。

测试后停止 Agent 自己启动的前后端和依赖服务，用户预览时自行启动；不停止用户自启服务、不删除持久化数据。完整规则见 AGENTS.md。

## 验收方向

F1 已补充用户行锁保护的幂等会话发现、当前用户非空会话列表，以及 /api 前缀副本，原 M1 路由保留。F1 时健康接口曾包含本地开发身份与能力标识；登录系统 v1 已将其移至受保护的 `/api/auth/me`，前端仍不传入用户身份。新增并发复用和跨用户隔离测试通过。接口与前端联调说明见 [F1 运行文档](../running-frontend.md)，完整 V1 尚未验收。

服务能启动；文字对话能持久化并在重启后恢复；请求隔离有效；错误可定位；已授权阶段有可重复的验证方式。
