# AfterStory 当前项目状态

- 最近更新：2026-09-09
- 当前阶段：V1 产品规则与技术基线讨论
- 代码状态：尚未开始 V1 代码实现

## 已完成

- 已创建 AfterStory Git 仓库，当前使用 `main` 分支。
- 已确定产品以长期角色陪伴为核心，个人助手能力作为后续扩展方向。
- 已确定 V1 先完成一个完整主角色和少量测试角色，暂不开发用户角色创建器。
- 已确定使用 `character_id` 标识角色身份，名称仅用于展示并允许重名。
- 已确定精选角色和未来的自定义角色使用同一套 Character Definition 规则。
- 已确定通过 Character Instance 隔离不同用户、角色和关系实例的 Memory、State、Relationship 与 Conversation。
- 已确定 V1 的三个核心领域为 Character System、Conversation Core 和 Voice Layer，三者需要保持清晰边界。
- 已确定前端使用 Vue 3、TypeScript 和 Vite，后端使用 Python 和 FastAPI，数据库使用 PostgreSQL。
- 已确定 V1 使用普通 Python 工作流，不提前引入 LangGraph。
- 已确定先完成并验收后端核心链路，再进行前端页面结构、交互原型、视觉设计和 Vue 实现。
- 已将产品和架构决策整理到 `docs/decisions/0001-v1-baseline.md`。

## 正在讨论

- 主角色采用哪一个角色及其哪个时期的设定。
- 主角色与用户第一次建立 Character Instance 时的默认关系。
- Character Definition、Character State、Character Response 和 Memory 的第一版规则与边界。
- 主角色资料、行为方式和 Voice Profile 如何分别组织并保持隔离。

## 下一步

1. 确定 V1 主角色、角色时期和默认关系。
2. 根据主角色和少量差异化测试角色，讨论 Character Definition 的第一版结构。
3. 讨论 Character Instance、State、Relationship、Conversation 和 Memory 的关系。
4. 确定 LLM、Embedding 和 TTS 的 V1 供应商与基本边界。
5. 在上述边界明确后，搭建可运行的 FastAPI、PostgreSQL 和测试骨架。
6. 后端核心链路完成并验收后，再开始前端设计与开发。

## V1 明确暂不进行

- 用户角色创建器。
- 天气、日历等工具调用。
- LangGraph 工作流。
- 微信接入。
- ASR、VAD、实时语音输入和全双工语音。
- 角色社区、角色市场和大规模商业运营能力。

## 后续方向

- V1 跑通后增加最简单的只读工具调用，再根据条件分支、确认、重试等需要评估 LangGraph。
- 后续开发用户角色创建器，但其产物必须使用与精选角色相同的 Character Definition 规则。
- 微信接入阶段优先考虑把 OpenClaw 和腾讯微信渠道插件作为独立消息网关，Character Runtime 保持渠道无关。
- 前端正式开发前先单独完成页面原型与视觉规范，避免在功能开发过程中不断堆叠临时界面。

## 当前待同步状态

- `README.md`、`docs/current-status.md` 和 `docs/decisions/0001-v1-baseline.md` 当前仅存在于本地工作区，尚未提交。
- 当前仓库尚未配置 Git 远程地址，因此另一台设备暂时无法通过 Git 获取这些新增内容。
- 当前 `.env.example` 仍是早期草案，其中 SQLite 配置与已经确定的 PostgreSQL 决策不一致，搭建后端骨架时需要修正。

