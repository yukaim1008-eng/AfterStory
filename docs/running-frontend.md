# 运行 F1 前端与文字链路

当前为本地联调版：页面、真实文字链路和用户主动管理的个人记忆可测试；自动记忆/状态策略、语音、剧情更新及正式角色资料仍未完成。

## 启动

macOS 与 Windows 命令相同，平台差异见 [平台差异](running-m1.md#平台差异)。启动 Docker Desktop，在仓库根目录执行：

```bash
uv sync --locked
cp -n .env.example .env          # 仅在没有 .env 时执行；已有文件不要覆盖
docker compose up -d --wait postgres
uv run alembic upgrade head
uv run python -m afterstory.seed
uv run python -m uvicorn afterstory.api:create_app --factory --host 127.0.0.1 --port 8000
```

已有 .env 不覆盖，密钥仅保存在本地。另开终端：

```bash
cd frontend
npm ci
npm run dev
```

打开 http://127.0.0.1:5173 ，接口文档 http://127.0.0.1:8000/docs 。Vite 将 /api 代理到8000，可用 AFTERSTORY_API_URL 环境变量修改目标。仅监听本机，无正式账号登录。验证环境为 Node 24.15.0。

生产构建：npm run build；npm run preview 打开 http://127.0.0.1:4173 ，仍需后端。尚未部署公网。

## 试用顺序

1. 娜娜莉发送一句话，刷新确认记录仍在。
2. 悬停角色只展开，点击切换主题；三位分别聊天，检查隔离。
3. 历史恢复对话，设置调整字体、快捷键。
4. 更换封面，分别调两处位置，检查取消/保存/刷新/恢复默认。
5. 从成功的用户消息选择“记住这件事”，检查保存、更正、来源跳转和删除；声音与剧情信息仍明确显示尚未启用或待补全。

失败消息可复用请求 ID 重试，也可取回输入框修改后重新发送。模型配置见 [M1](running-m1.md)。健康检查只验证服务与数据库，不保证模型可用。

## 数据与接口

seed 导入原工程 fixtures 和 fixtures/companions.integration.json 的三位联调资料。已导入版本不可覆盖；完善资料时新增 version_id，同步前端 versionId，再导入。历史可继续打开当前角色的旧版本会话，使用原绑定版本；正式 Canon 更新仍未实现。

默认封面来自 data/character-assets/{id}.png，prepare:media 复制到 public/media。缺失时回退官方宣传参考图。自定义封面存当前浏览器 IndexedDB，以后端用户与角色为键；清除站点数据会移除封面和偏好，不会删除数据库聊天。

原根路径 API 保留，新增 /api 前缀副本：

| 接口 | 契约 |
| --- | --- |
| GET /api/health | 健康信息、user_id、capabilities；memory 表示手动管理可用，memory_extraction/voice/canon_update 为 false |
| POST /api/sessions/open | 输入 version_id，返回 conversation_id、instance_id；当前用户该版本存在则复用，无则创建；用户行锁防并发重复 |
| GET /api/conversations | 兼容旧列表调用，返回当前用户非空会话 |
| GET /api/history | offset/limit 分页，返回 items、total、offset、limit；条目包含角色/实例/版本/剧情节点、预览、轮数和时间 |
| GET /api/conversations/{id} | 当前用户的单会话元信息，空会话也可读取 |
| GET /api/conversations/{id}/messages | offset/limit 按轮数；around_turn_id 可定位来源轮次；条目新增 created_at |
| POST /api/conversations/{id}/messages | request_id、text，返回完整回复；重试复用 ID |
| GET/POST /api/instances/{id}/memories | 分页读取或主动新增当前角色实例的个人记忆；新增使用 request_id，可选成功用户消息来源 |
| PATCH/DELETE /api/memories/{id} | 使用 expected_revision 更正或删除；删除不改变原始聊天 |

新会话和轮次保存 UTC 创建时间，列表按最近活动和稳定 ID 排序。迁移前的记录保留未知时间，页面不编造日期。跨用户或不属于本会话的来源轮次返回404；所有会话所属用户由后端检查。

## 验证

```bash
uv run python -m pytest -q
uv run ruff check afterstory tests
cd frontend
npm run build
npx playwright install chromium
npm run test:e2e
```

仓库根目录也可运行 `uv run python -m scripts.verify`（Windows 可用 `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1`，两者等价）。该脚本使用 fake Provider，不产生模型费用，并按“只停止自己启动的服务”规则清理 PostgreSQL。

自动浏览器测试模拟 API；后端测试使用独立临时 schema，不清空用户数据库。

真实检查需单独终端把 `DEV_USER_ID` 设为 `frontend-smoke`（macOS `export DEV_USER_ID=frontend-smoke`，Windows `$env:DEV_USER_ID='frontend-smoke'`），执行 seed，再将后端启动于8001。前端目录执行 node scripts/smoke-real.mjs。它手动调用一次当前模型，产生少量费用，使用独立身份，不写入默认用户。

测试结束后，Agent 停止自己启动的测试后端、前端及项目依赖，不继续后台运行供预览；用户需要查看效果时自行启动。仅关闭能确认由 Agent 启动的服务，不关闭用户自行启动的服务，不删除数据库或卷。该规则也适用于自动测试复用的服务：复用了用户服务不代表可以将其停止。
