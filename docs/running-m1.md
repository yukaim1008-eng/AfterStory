# 运行 M1 后端

本阶段提供本机文字 API，保留两个原创工程测试角色。F1 已补充三位联调角色与可运行前端，F2 已补充个人记忆、受限上下文与内部状态存储边界，见 [前端运行说明](running-frontend.md)。自动记忆/状态策略和语音尚未实现。接口契约可在服务启动后的 `/docs` 查看。

## 安装与启动（仓库根目录）

前置依赖：Docker Desktop（需先启动）、`uv`。macOS 用 `brew install uv`；Windows 见 [uv 安装说明](https://docs.astral.sh/uv/getting-started/installation/)。`uv sync` 会自行下载所需的 Python 版本，不需要本机预装。前端另需 Node 24。

macOS 与 Windows 通用。命令统一使用 `uv run`，它自动使用项目 `.venv`，不需要写 `.venv/bin` 或 `.venv\Scripts`。仅有的几处平台差异见[平台差异](#平台差异)。

```bash
uv sync --locked
cp -n .env.example .env          # 仅在没有 .env 时执行；已有文件不要覆盖
docker compose up -d --wait postgres
uv run alembic upgrade head
uv run python -m afterstory.seed
uv run python -m uvicorn afterstory.api:create_app --factory --host 127.0.0.1 --port 8000
```

浏览器打开 <http://127.0.0.1:8000/docs>。`/health` 检查数据库连通性，不测试模型密钥或余额。

`.env` 按命名模型分组，每组绑定自己的供应商、API 地址、密钥、model 和参数；`LLM_ACTIVE_MODEL` 只负责选择当前组：

```dotenv
LLM_ACTIVE_MODEL=deepseek
DEEPSEEK_PROVIDER=deepseek
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_TIMEOUT_SECONDS=60
DEEPSEEK_MAX_TOKENS=1024

# 填入另一个供应商的真实配置后，切换 LLM_ACTIVE_MODEL=other_chat
# OTHER_CHAT_PROVIDER=openai_compatible
# OTHER_CHAT_BASE_URL=https://your-provider.example/v1
# OTHER_CHAT_API_KEY=
# OTHER_CHAT_MODEL=your-model-id
```

组名使用小写字母、数字和下划线；同一供应商的多个模型也可以分别建组。修改激活组后重启后端，其他组的信息会保留。密钥只填写本地配置。当前仍每次选择一个对话模型，尚未实现角色级路由或并行模型对比。

工程测试使用内置 `fake` 组：临时把 `LLM_ACTIVE_MODEL` 设为 `fake`，结束后取消，两种平台的写法见[平台差异](#平台差异)。环境变量优先于 `.env`，只影响当前终端。fake 不会在真实调用失败时自动启用。

M1 对 DeepSeek 默认关闭 thinking；其他 Chat Completions 兼容模型组使用 `PROVIDER=openai_compatible`，不发送 DeepSeek 专用参数。可同时保存多个供应商配置，其他原生协议适配器尚未实现。

官方协议依据：[Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)，核实日期 2026-09-10。适配器只接收完整 `content`，不保存 `reasoning_content`；空白、截断或异常响应作为失败处理。

## 一轮对话

1. `GET /characters` 获取 `version_id`。
2. `POST /instances`，正文 `{"version_id":"test-lan-v1"}`，取得 `instance_id`。
3. `POST /conversations`，正文 `{"instance_id":"上一步的 ID"}`，取得 `conversation_id`。
4. `POST /conversations/{conversation_id}/messages`，正文 `{"request_id":"first-message","text":"你好"}`。
5. `GET /conversations/{conversation_id}/messages?offset=0&limit=20` 获取按轮分页的历史；`offset` 和 `limit` 单位是轮，不是消息条数。

每条新消息使用新的 `request_id`。网络或模型失败后可用相同 ID 和相同文本重试；成功请求重复提交返回同一条回复。若失败后已发送了新一轮，旧失败轮不再允许重试，返回 `stale_turn_retry`，避免打乱对话顺序。

每个会话同时只处理一轮，冲突返回 409 `conversation_busy`。超过 `TURN_LEASE_SECONDS` 的遗留处理状态由下次发送请求恢复；旧调用不能覆盖新的重试结果。真实供应商超时后重试可能重复计费，本地不会重复提交成功消息。

默认上下文包含角色定义、当前实例最多 20 条/6000 字符的有效个人记忆、可选内部状态、当前会话最近 12 个成功轮次和当前消息。`HISTORY_TURNS`、`MEMORY_CONTEXT_ITEMS`、`MEMORY_CONTEXT_CHARS` 可调整容量。每条输入最多 8000 字符，输出上限由 `DEEPSEEK_MAX_TOKENS` 设置。个人记忆由用户主动保存，不自动从聊天提取。

用户身份由服务端 `DEV_USER_ID` 提供，请求不能指定 `user_id`。更改本地用户配置后需再次运行 seed；M1 仅本机开发使用，正式登录与共享部署属于后续设计。

## 平台差异

除下表外，本项目所有命令在 macOS 与 Windows 上写法相同，文档中的其他代码块两边都能直接执行。

| 操作 | macOS（zsh） | Windows（PowerShell） |
| --- | --- | --- |
| 无 `.env` 时复制示例 | `cp -n .env.example .env` | `if (-not (Test-Path .env)) { Copy-Item .env.example .env }` |
| 本次终端临时设置变量 | `export LLM_ACTIVE_MODEL=fake` | `$env:LLM_ACTIVE_MODEL='fake'` |
| 取消临时变量 | `unset LLM_ACTIVE_MODEL` | `Remove-Item Env:LLM_ACTIVE_MODEL` |
| 一键验证 | `uv run python -m scripts.verify` | 同左，或 `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1` |

`scripts/verify.ps1` 只是 `uv run python -m scripts.verify` 的 Windows 包装，两者行为一致；macOS 用 `scripts/verify.py` 即可，均以仓库根目录为工作目录运行。

## 验证

```bash
uv run pytest -q
uv run ruff check .
uv run alembic check
uv run python -m scripts.doctor
uv run python -m scripts.smoke --profile fake
# 配置真实密钥后：该命令进行八次模型调用，使用工程测试对话
uv run python -m scripts.smoke --profile deepseek
```

也可执行 `uv run python -m scripts.verify` 完成迁移、脱敏诊断、后端测试、前端构建和浏览器测试。脚本固定使用 fake Provider；若 PostgreSQL 原本未运行，结束或失败时会停止自己启动的容器，原本已运行则不会关闭。

pytest 在 PostgreSQL 中创建随机 `test_...` schema，迁移后测试并删除该 schema，不清空现有业务表。可用 `TEST_DATABASE_URL` 指定独立测试库，测试账号需要创建 schema 的权限。

smoke 启动两个先后独立的后端进程，检查两个角色各三轮文字对话，以及重启后各继续一轮；运行后关闭测试进程，保留测试会话便于检查。fake 验证通过不表示真实模型效果通过。

数据库通过 Docker 命名卷持久化，`docker compose stop` 可停止。普通重启无需重新建库，seed 可重复运行；改变角色资料需新增 `version_id`，不能覆盖已有角色版本。

## 当前验证结果

2026-09-10（Windows）：PostgreSQL 容器健康，初始迁移与测试角色导入成功；12 项 pytest 测试通过，Ruff 检查通过，Alembic 检查无模型与迁移差异。真实进程 smoke（fake Provider）通过：两个角色、八轮对话、退出并重启后恢复历史。

依赖有两条来自 Starlette/httpx/AnyIO 的弃用提示，不影响本次测试通过；锁文件保留当前已验证依赖组合。

2026-09-14（macOS 26.5，Apple Silicon）：在 macOS 上从零配置通过。环境为 `uv` 0.12.13、Python 3.14.7、Docker Desktop 29.7.2、PostgreSQL 17 容器（127.0.0.1:54329）、Node 24.15.0。`uv sync --locked`、`alembic upgrade head`（12 张表，head `f2d_state_boundary`）、`afterstory.seed`（三位主角色与两个工程测试角色）与后端 `/health` 均通过；34 项 pytest 测试、`ruff check`、`alembic check` 与 `scripts.doctor` 通过；前端 `npm ci` 与 `npm run build` 通过。本轮未执行浏览器测试、smoke 与真实消息，未验证模型连通性或表达效果。

2026-09-10 时本地 `DEEPSEEK_API_KEY` 为空，未执行真实 DeepSeek 请求；2026-09-14 已在 `.env` 填入真实密钥，但同样尚未发出真实请求，因此仍不能认定模型连通性或表达效果已通过。DeepSeek 适配器的请求字段、超时、异常和回复校验已通过模拟 HTTP 测试。
