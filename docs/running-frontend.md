# 运行 F1 前端与文字链路

当前为本地联调版：页面与真实文字链路可测试；长期记忆、语音、剧情更新及正式角色资料仍未完成。

## 启动（PowerShell）

启动 Docker Desktop，在仓库根目录执行：

```powershell
uv sync --locked
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --wait postgres
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m afterstory.seed
.venv/Scripts/python -m uvicorn afterstory.api:create_app --factory --host 127.0.0.1 --port 8000
```

已有 .env 不覆盖，密钥仅保存在本地。另开终端：

```powershell
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
5. 声音、记忆与剧情信息明确显示尚未启用或待补全。

失败消息可复用请求 ID 重试，也可取回输入框修改后重新发送。模型配置见 [M1](running-m1.md)。健康检查只验证服务与数据库，不保证模型可用。

## 数据与接口

seed 导入原工程 fixtures 和 fixtures/companions.integration.json 的三位联调资料。已导入版本不可覆盖；完善资料时新增 version_id，同步前端 versionId，再导入。旧会话定义保留；正式 Canon 迁移与旧版本 UI 入口后续完善。

默认封面来自 data/character-assets/{id}.png，prepare:media 复制到 public/media。缺失时回退官方宣传参考图。自定义封面存当前浏览器 IndexedDB，以后端用户与角色为键；清除站点数据会移除封面和偏好，不会删除数据库聊天。

原根路径 API 保留，新增 /api 前缀副本：

| 接口 | 契约 |
| --- | --- |
| GET /api/health | 健康信息、user_id、capabilities；voice/memory/canon_update 当前 false |
| POST /api/sessions/open | 输入 version_id，返回 conversation_id、instance_id；当前用户该版本存在则复用，无则创建；用户行锁防并发重复 |
| GET /api/conversations | 当前用户非空列表：conversation_id、version_id、turns、preview；当前无日期 |
| GET /api/conversations/{id}/messages | 原历史结构，offset/limit 按轮数，前端每次30轮 |
| POST /api/conversations/{id}/messages | request_id、text，返回完整回复；重试复用 ID |

当前会话列表未提供大规模分页，不编造日期。所有会话所属用户由后端检查。

## 验证

```powershell
.venv/Scripts/python -m pytest -q
.venv/Scripts/ruff check afterstory tests
cd frontend
npm run build
npx playwright install chromium
npm run test:e2e
```

自动浏览器测试模拟 API；后端测试使用独立临时 schema，不清空用户数据库。

真实检查需单独终端设置 $env:DEV_USER_ID='frontend-smoke'，执行 seed，再将后端启动于8001。前端目录执行 node scripts/smoke-real.mjs。它手动调用一次当前模型，产生少量费用，使用独立身份，不写入默认用户。

测试结束后，Agent 停止自己启动的测试后端、前端及项目依赖，不继续后台运行供预览；用户需要查看效果时自行启动。仅关闭能确认由 Agent 启动的服务，不关闭用户自行启动的服务，不删除数据库或卷。该规则也适用于自动测试复用的服务：复用了用户服务不代表可以将其停止。
