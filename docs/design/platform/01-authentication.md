# 登录系统 v1：部署前实现

状态：用户名密码登录已实现；2026-10-17 增加管理员发放的一次性邀请码注册。服务器部署、域名/TLS 和备份仍是独立阶段。

## 目标与边界

AfterStory 的 `User → CharacterInstance → Conversation / Memory / State / Relationship` 归属模型已经存在，所有业务路由通过 `current_user` 取得用户 ID。登录系统只替换该身份来源，并提供账号建立、登录、会话续期、退出与失效处理。角色定义和 Canon 仍可由多个账号共用；每位用户的实例与运行数据继续隔离。

首版面向轻量多用户、自托管部署。语音、第三方账号、复杂个人资料、邮箱通知、组织权限与运营后台不进入本阶段。网站允许持有效邀请码的访客自助注册；邀请码只能由管理员在服务器命令行发放，仍无开放注册。

## 已确认产品取舍

| 决策 | 推荐 | 影响 |
| --- | --- | --- |
| 账号开放 | 管理员可直接创建账号，也可发放一次性邀请码让访客注册；无邀请码不能注册 | 限制公网产生模型费用的入口。 |
| 登录凭据 | 用户名＋密码；忘记密码由服务器命令重设 | 不需要邮件服务。 |
| 旧 `local-user` 数据 | 首个账号使用新的用户 ID，不绑定旧用户 | 最初实施时保留旧个人数据；2026-10-16 用户随后明确要求删除 4 个旧用户，已单独清理。公共角色及版本继续可用。 |

## 已实现边界

代码现位于 `afterstory/auth/`：`service.py` 负责凭据、会话与邀请码，`http.py` 负责 Cookie、CSRF 和当前用户依赖，`routes.py` 暴露登录/注册接口，`cli.py` 实现管理员账号命令。`afterstory.accounts` 保留原命令入口。

1. `users` 保留稳定 ID，新增唯一用户名、Argon2id 密码哈希、启用状态。`auth_sessions` 只保存随机 Cookie 令牌的 SHA-256 摘要、用户、创建/最近使用/绝对到期/撤销时间；`auth_login_attempts` 保存按用户名/IP 摘要计数的失败尝试，15 分钟窗口内每个维度最多 8 次。
2. 管理员在仓库根目录运行 `uv run python -m afterstory.accounts create <用户名>` 或 `uv run python -m afterstory.accounts reset-password <用户名>`；密码由隐藏输入提示读取，不进入 shell 参数。账号名会规范为小写，密码长度为 12–128 字符；重置会撤销该用户全部登录会话。无旧用户认领命令。
3. `POST /api/auth/login` 设置 `HttpOnly; SameSite=Strict; Path=/` Cookie；生产模式使用 `Secure` 和 `__Host-` 前缀。会话绝对有效期 30 天、空闲有效期 7 天；退出或改密立即撤销。所有业务写请求及退出/改密必须携带 `/api/auth/me` 返回的 CSRF 令牌。令牌仅在前端内存中，不写入 `localStorage`、URL 或日志。
4. `GET /api/auth/me` 返回当前账号 ID、用户名、CSRF 令牌及前端能力；匿名业务请求返回 401。`current_user` 从已验证会话取得 `users.id`，现有实例归属检查保持。`/health` 仅返回 `status`，不暴露用户或模型配置。`/characters` 仍公开读取公共角色定义。
5. 前端在认证完成前只展示登录入口；退出、改密或会话过期清空当前内存状态，浏览器草稿、偏好和封面仍按用户 ID 分区。角色导入 `seed` 不再创建 `DEV_USER_ID`，既有旧用户行也不会自动升级成可登录账号。

## 邀请码注册（2026-10-17）

- 管理员先运行 `alembic upgrade head`，再运行 `uv run python -m afterstory.accounts invite-create --days 7` 生成一个邀请码；有效期可设置为 1–90 天，默认 7 天。明文仅在终端显示一次，数据库只保存带用途前缀的 SHA-256 摘要。需要撤销时运行 `uv run python -m afterstory.accounts invite-revoke`，在隐藏输入中粘贴原码。
- 访客在登录页切换到“使用邀请码注册”，填写用户名、至少 12 字符的密码和邀请码。`POST /api/auth/register` 先检查同源请求和按来源 IP 的失败次数，再在单个数据库事务内锁定邀请码、创建用户、标记已使用并创建登录会话；成功后沿用登录的 HttpOnly Cookie 和 CSRF。邀请码一次有效，过期、撤销和重复使用均拒绝；用户名冲突或注册失败不消耗邀请码。
- `registration_invites` 只记录邀请码摘要、创建/到期、核销时间与用户及撤销时间；迁移 `a2_invite_registration` 不修改旧用户、角色、实例或聊天。管理员直接创建账号的命令和旧登录流程继续可用。邀请码不能代替生产部署的 HTTPS、备份或滥用监控。

## 部署关联边界

生产启动设置 `APP_ENV=production` 与明确的 `ALLOWED_HOSTS=<实际域名>`，并在同源 HTTPS 反向代理后运行；应用会使用 Secure Cookie，拒绝默认开发 Host 配置。`compose.yaml` 仍是开发数据库口令及本机端口，`afterstory` 启动器仍是本地开发入口。部署前另行核对域名、TLS、数据库口令与备份、密钥注入及服务常驻方式；登录与注册测试本身不等于部署验收。数据库部署选项见[服务器部署边界](02-deployment.md)。

## 验收范围

- 匿名用户无法读取或修改会话、记忆、状态、关系和提醒；登录后只能访问本人数据，伪造用户 ID 无效。
- 登录、刷新、过期、退出、改密失效和换账号均正确；Cookie 属性、CSRF、限速和错误信息经过测试。
- 老 `local-user` 数据不绑定新账号；登录系统实施时未自动删除，后来按用户单独指示清理。迁移升级/回滚在隔离 schema 中验证。
- 前端登录态切换不显示其他账号的草稿和封面；后端、前端与浏览器测试使用 fake Provider，不调用真实模型。
- Ruff、类型检查、构建和相关测试通过；测试后只停止本轮启动的服务。

2026-10-16 验收：隔离 PostgreSQL schema 的升级/回滚、147 项后端测试、36 项 Playwright、Ruff、前端类型检查/构建与 Alembic 一致性均通过；没有调用真实模型。开发库已升级到 `a1_authentication`，原有角色、版本和实例数量未因本次迁移改变。部署时需核对反向代理传递的真实客户端 IP，避免多用户共享一个登录限速来源。

2026-10-17 邀请码注册验收：37 项 Playwright、全量 155 项后端测试、Ruff、前端构建、Alembic 一致性检查均通过。数据库集成测试在隔离 PostgreSQL schema 中覆盖单次核销、过期/撤销、失败不消耗、来源限制、限速、并发、生产 Cookie 及迁移升降级。开发库已升级到 `a2_invite_registration`，仅新增空的 `registration_invites` 表；原有 30 张表行数一致，账号、角色版本、实例、聊天和记忆等关键表的内容校验值一致。没有创建真实邀请码或新账号，也没有调用真实模型。

2026-10-16 后续数据清理：按用户明确指示，在单个数据库事务内删除 `alice`、`bob`、`frontend-smoke`、`local-user` 这 4 个无登录凭据的旧用户及其用户归属数据（含 15 个角色实例、15 段会话、29 个轮次、58 条消息和 1 条个人记忆）。检查外键归属范围后清理 25 张依赖表；清理前后对公共 `characters` 与 `character_versions` 做整行校验，分别保持 6 条和 9 条且内容不变。此操作不属于登录 migration，也不影响后续新账号创建。

安全方案参考：[OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)、[OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)、[OWASP 随机单次令牌规则](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)。
