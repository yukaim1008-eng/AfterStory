# 运行 M1 后端

本阶段提供本机文字 API，保留两个原创工程测试角色。F1 已补充三位联调角色与可运行前端，见 [前端运行说明](running-frontend.md)。长期记忆、关系变化和语音尚未实现。接口契约可在服务启动后的 `/docs` 查看。

## 安装与启动（仓库根目录，PowerShell）

```powershell
uv sync --locked
# 仅在没有 .env 时复制；已有文件不要覆盖
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --wait postgres
.venv\Scripts\alembic upgrade head
.venv\Scripts\python -m afterstory.seed
.venv\Scripts\python -m uvicorn afterstory.api:create_app --factory --host 127.0.0.1 --port 8000
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

工程测试使用内置 `fake` 组：在当前 PowerShell 设置 `$env:LLM_ACTIVE_MODEL='fake'`，结束后 `Remove-Item Env:LLM_ACTIVE_MODEL`。fake 不会在真实调用失败时自动启用。

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

默认上下文包含最近 12 个成功轮次、角色定义和当前消息。每条输入最多 8000 字符，输出上限由 `DEEPSEEK_MAX_TOKENS` 设置。M1 只保留当前会话历史，不冒充跨会话长期记忆。

用户身份由服务端 `DEV_USER_ID` 提供，请求不能指定 `user_id`。更改本地用户配置后需再次运行 seed；M1 仅本机开发使用，正式登录与共享部署属于后续设计。

## 验证

```powershell
.venv\Scripts\pytest -q
.venv\Scripts\ruff check .
.venv\Scripts\alembic check
.venv\Scripts\python -m scripts.smoke --profile fake
# 配置真实密钥后：该命令进行八次模型调用，使用工程测试对话
.venv\Scripts\python -m scripts.smoke --profile deepseek
```

pytest 在 PostgreSQL 中创建随机 `test_...` schema，迁移后测试并删除该 schema，不清空现有业务表。可用 `TEST_DATABASE_URL` 指定独立测试库，测试账号需要创建 schema 的权限。

smoke 启动两个先后独立的后端进程，检查两个角色各三轮文字对话，以及重启后各继续一轮；运行后关闭测试进程，保留测试会话便于检查。fake 验证通过不表示真实模型效果通过。

数据库通过 Docker 命名卷持久化，`docker compose stop` 可停止。普通重启无需重新建库，seed 可重复运行；改变角色资料需新增 `version_id`，不能覆盖已有角色版本。

## 当前验证结果

2026-09-10：PostgreSQL 容器健康，初始迁移与测试角色导入成功；12 项 pytest 测试通过，Ruff 检查通过，Alembic 检查无模型与迁移差异。真实进程 smoke（fake Provider）通过：两个角色、八轮对话、退出并重启后恢复历史。

依赖有两条来自 Starlette/httpx/AnyIO 的弃用提示，不影响本次测试通过；锁文件保留当前已验证依赖组合。

本地 `DEEPSEEK_API_KEY` 为空，尚未执行真实 DeepSeek 请求，不能认定模型连通性或表达效果已通过。DeepSeek 适配器的请求字段、超时、异常和回复校验已通过模拟 HTTP 测试。
