# 正式角色资料整理入口

状态：档案基线与 P1–P22 剧情证据均已整理并通过本轮用户审核；薄荷默认称用户为“可可”，“鉴定师”只用于职业或任务语境。完整角色包已作为三个新的不可变 `CharacterVersion` 导入数据库，现有 `CharacterInstance` 未切换。

## 本轮范围

本目录整理娜娜莉、伊洛伊、薄荷在公开角色介绍、角色语音和 P1–P22 已接受剧情证据中能够确认的稳定信息，并映射到 Minimal Character Schema v1 的六个字段。档案基线候选保留在 `fixtures/companions.profile-v1.candidate.json`；P1–P22 增补依据见 [三位正式角色六字段修改候选](../../implementation/character-definition-candidates-p05-p22.md)；按用户审核结果形成并已导入的正式包位于 `fixtures/companions.canon-p22.json`：

- `identity`：角色身份与稳定背景；
- `personality`：核心性格和价值倾向；
- `speaking_style`：默认称呼和稳定表达习惯；
- `behavior`：基本交流方式、自主立场与互动边界；
- `worldview`：海特洛、异象与跨世界通信的稳定前提；
- `relationship_premise`：用户身份映射和初始关系，不写入后续关系变化。

档案基线本身不从零散语音推定具体共同事件；后续 P1–P22 Canon 已通过独立 Scene、Evidence、知识和 Trait 门禁形成修改候选。当前仍不建立 Voice Profile，也不把 Memory、State、Runtime Relationship 或 Conversation 写入 Character Definition。

## 来源与证据类型

| 类型 | 含义 | 使用方式 |
| --- | --- | --- |
| 游戏个人档案 | 游戏内公开的身份、档案和语音；信息站属于该内容的搬运来源 | 可以确认档案中明确写出的事实，但官网与搬运页出现同一文本时只算一份内容来源 |
| 游戏剧情录像 | 主线、角色故事、羁遇、都市偕游和活动的实际录屏 | 按场景和时间点记录角色选择、反应与表达，是人物塑造的主要证据 |
| 人物归纳 | 根据多段档案语音或剧情表现形成的判断 | 必须记录触发条件、表现方式、边界和证据引用 |
| 玩家总结 | 评论、攻略或人物分析 | 只用于发现待查线索，不单独证明稳定人设 |
| 用户确认 | 用户根据实际剧情体验确认的人物理解 | 可以先作为暂定判断保存，之后补具体剧情证据 |

候选文本不复制整段官网文案或语音，只记录事实摘要和表达模式。每位角色的来源、已确认信息、推断边界和待审点分别记录在本目录文档中。

面向所有命名角色的资料结构、采集顺序和当前覆盖见 [人物资料研究库](character-corpus.md)。

人物地图、世界知识与人物关系图的共同证据链、时间版本和数据结构见 [Canon 人物、世界与关系知识层](canon-knowledge-map.md)。K0–K4 已完成 P1–P22 的复核、正式入库、结构化知识、审核视图和跨 P Trait 归纳，但尚未接入生产 PostgreSQL、Character Definition 或聊天运行时。

## 已导入版本与边界

2026-10-11 已通过现有 `seed()` 导入以下不可变版本，Prompt Builder v1.0 在导入时生成并冻结 `system_prompt`：

- `nanally-canon-p22-v1`
- `iroi-canon-p22-v1`
- `mint-canon-p22-v1`

三者共同使用 checkpoint `nt-bv1kqoabievz-p22`。前端 `versionId` 已切换到对应正式版本，但没有更新任何现有 `CharacterInstance`；默认入口会为正式版本打开新会话，旧联调版本及其历史聊天仍可从历史入口继续使用。

## 当前已确认与后续检查

- 娜娜莉与伊洛伊采用当前剧情增补；伊洛伊因跨章证据量较少，相关表现保持 supporting 强度。
- 薄荷默认称呼为“可可”；“鉴定师”只在职业身份或鉴定、任务语境使用。
- `relationship_premise` 已明确原作主角身份承接与现实用户独立身份的边界，不自动把原作共同经历赋给用户。
- 语言风格只规定稳定倾向和使用节制，避免把剧情台词机械改写成每句话都重复的口头禅。
- 正式不可变 CharacterVersion 与前端默认版本切换均已完成；下一步是直接进行真实聊天验收，现有实例和联调版本不自动迁移。
