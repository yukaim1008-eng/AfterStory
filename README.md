# AfterStory

AfterStory 是一个以长期角色陪伴为核心的多角色语音对话项目。项目首先完成一个经过验证的主角色和少量测试角色，后续再扩展用户自定义角色、工具调用和微信等外部渠道。

M1 后端文字链路已实现并通过 PostgreSQL 工程验证：角色实例、会话、多轮消息、持久化与失败重试。首次文本模型为 DeepSeek V4 Flash；真实调用待在本地配置密钥后验证。长期记忆、关系变化、语音和前端尚未实现。

## 项目文档

- [启动后端与接口使用](docs/running-m1.md)

- [当前项目状态](docs/current-status.md)
- [V1 当前决策基线](docs/decisions/0001-v1-baseline.md)
- [分区设计与实施阶段](docs/design/README.md)
- [项目协作规则](AGENTS.md)

