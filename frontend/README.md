# AfterStory 前端

当前为静态设计阶段，**03 版角色主题视觉方向已获用户认可，尚未授权开发**。技术栈为 Vue 3 + TypeScript + Vite，尚未初始化工程。

用户已于 2026-09-10 允许提前开展前端设计，并认可参考官方娜娜莉形象制作的粉色新版。此安排不代表后端完整 V1 已验收，也不代表立即实现业务页面。

## 当前设计：03 版

- [本轮封面操作细稿（待反馈）](../data/design-preview/cover-refinement-v02.png) / [设计说明](design/cover-refinement.md)：裁切三种预览、保存成功、恢复默认确认与失败。

- 主角色为娜娜莉、伊洛伊、薄荷三位并列。[三人角色选择效果（已认可）](../data/design-preview/three-main-characters-selection-v01.png) / [设计说明](design/three-main-characters.md)；用户于 2026-09-11 认可整体效果，它替代下方旧总览里的测试角色卡片，其余页面视觉沿用。

- 聊天采用左角色、右对话的构图；主题根据角色人设设计，辅助页面跟随当前角色配色。
- 娜娜莉采用粉白底与粉黑点缀，清爽的中文字体与留白；第一版深蓝色方案已被替代。
- 角色选择采用悬停展开，去掉小箭头；封面需方便独立替换。
- [当前设计基准](../docs/design/06-frontend.md) / [角色主题与封面说明](design/character-theme-v03.md)
- [聊天与角色选择效果图](../data/design-preview/nanally-chat-selection-v03.png)
- [资料、历史、外观设置与记忆效果图](../data/design-preview/nanally-supporting-v03.png)
- [角色选择与封面状态稿 · 2026-09-11 两项核心交互已确认](../data/design-preview/character-selection-cover-states-v01.png) / [交互说明](design/character-selection-cover.md)：悬停预览、点击切换；分别裁切，保存失败保留调整。补充原有两张基准图。

用户指定以 `data/design-preview/` 中两张效果图为准，其他旧版效果图、提示词和讨论归档已删除。最新图片位于 Git 忽略的目录，仅保存在本地工作区，不会随 Git 同步。`design/` 只保留当前方案说明与对应提示词。图片里的生成形象和示例内容不是正式角色资产或 Canon。

## 新窗口从这里开始

建议以整个 AfterStory 仓库为工作区打开，前端文件放在本目录，保留对后端契约和项目文档的访问。

先阅读：

- [项目协作规则](../AGENTS.md)
- [当前状态](../docs/current-status.md)
- [分区设计入口](../docs/design/README.md)
- [前端设计文档](../docs/design/06-frontend.md)
- [M1 后端接口与运行说明](../docs/running-m1.md)

前端设计结论集中更新到 `docs/design/06-frontend.md`；原型和视觉素材可以放在本目录。相关产品取舍整批讨论，先设计后实现，不一次生成完整项目。

## 当前设计边界

前端技术栈已确定为 Vue 3、TypeScript、Vite。用户通过角色表达感受关系，不展示好感度、关系进度或内部分析。个人记忆的数据管理、语音播放和剧情进度更新属于 V1 设计范围，但相应后端能力尚未完成，设计稿需要区分当前可用与未来规划。

当前后端可用能力为角色列表、创建角色实例、创建会话、发送文字和读取历史。详细契约以运行说明与后端 `/docs` 为准；真实模型验证、长期记忆、关系变化和语音尚未完成。
