# AfterStory

AfterStory 是以长期角色陪伴为核心、采用跨世界交流设定的 Web 应用。V1 主角色为《异环》的娜娜莉、伊洛伊、薄荷，三位并列；范围以决策基线为准。

M1 文字后端、F1 前端、登录系统 v1、Memory System、Conversation Core v1 和三位角色的 P22 正式版本已实现。真实模型回复、持久化和刷新恢复已做联调；完整 V1 尚未验收，语音与 Canon 运行时接入仍未完成。

Windows 首次设置在仓库根目录运行 `.\afterstory setup`，再运行 `uv run python -m afterstory.accounts create 你的用户名` 创建登录账号；日常启动运行 `.\afterstory start`。停止启动器创建的前后端用 `.\afterstory stop`，数据库默认保持运行且数据不会删除。完整说明见[启动前端与联调](docs/running-frontend.md)。

## 项目文档

- [下一阶段选择清单](docs/next-step-review.md)
- [启动前端与联调](docs/running-frontend.md)
- [启动后端与接口使用](docs/running-m1.md)

- [当前项目状态](docs/current-status.md)
- [V1 当前决策基线](docs/decisions/0001-v1-baseline.md)
- [分区设计与实施阶段](docs/design/README.md)
- [项目协作规则](AGENTS.md)

