# 角色与原作资料

状态：身份/版本/实例基础与 Minimal Character Schema v1 已实现并验证；2026-09-18 用户确认先按六部分拆分，等 Memory System 完成后再据此优化。

## 职责与已确认约束

负责 Character Definition、版本、Canon Checkpoint、实例引用及角色素材边界。遵循基线第 1、3、5、10 节。主角色为娜娜莉、伊洛伊、薄荷；娜娜莉承接鉴定师伙伴关系，其他两位的用户映射与初始关系待定。原作经历与个人记忆隔离，剧情进度由用户手动更新。当前三位使用联调资料，不等于正式 Canon 已完成。

## 已实现与本轮边界

`afterstory/models.py` 已有 Character、CharacterVersion、CharacterInstance；`seed.py` 校验已导入版本不可变，实例引用明确版本。前端的主题、素材和发送按钮使用独立配置。

此前暂缓角色设计的阶段安排已由本次最小 Schema 设计调整；当前先明确字段与数据归属，保留现有联调内容。正式资料采集、完整性格细化和角色资料库建设仍未开展。

## 最小 Character Schema：暂定六部分与字段草稿（2026-09-18）

已确认的是推进顺序、最小范围，以及暂按身份、性格、说话方式、行为、世界观、初始关系六部分拆分。先保持这一最小结构，等 Memory System 完成后，再根据实际接口与数据边界优化，不在当前阶段展开完整角色 Schema。以下具体字段名称、必填规则、JSONB 存储和 Prompt 编译方式仍为建议，尚未定稿；六部分暂定不等于整份字段草稿已获采纳或实现已获授权。“30%–40%”指先覆盖角色正常运行所需信息，不按字段数量计算。

### 1. characters：稳定身份与目录信息

目前仅有 `id`、`name`；这张表不是完整角色设定。

| 字段 | 状态 | 用途 |
| --- | --- | --- |
| `id` | 已有 | 稳定身份与关联键，名称重复不影响隔离 |
| `name` | 已有 | 展示姓名 |
| `source_work` | 建议新增，可空 | 来源作品；原创角色可空，不虚构来源 |
| `aliases` | 建议新增，默认空数组 | 别名、其他语言姓名，供展示或查找，不代替 ID |

当前 ID 已能作为程序标识，不再新增含义重复的 slug；封面、主题和首页装饰文案继续属于前端 Presentation 配置。

### 2. character_versions：版本化角色定义

保留已有 `id`、`character_id`、`checkpoint`、`system_prompt`；本阶段增加可空 `definition` JSONB。结构化定义固定含 `schema_version: "1.0"` 和六个文本字段；Schema 版本描述字段格式，角色版本 ID 描述某一份具体设定，两者不同。Prompt Builder Version 固定为 `1.0`，新结构角色在导入时编译并冻结 `system_prompt`。

| definition 字段 | 当前最小格式 | 保存什么 |
| --- | --- | --- |
| `identity` | 必填 string | 身份背景和原作中的角色身份 |
| `personality` | 可空 string | 核心性格和价值观；自主立场沿用 V1 基线 |
| `speaking_style` | 可空 string | 语气、初始称呼规则和稳定表达方式 |
| `behavior` | 可空 string | 基本交流方式和角色特有边界 |
| `worldview` | 可空 string | 原作世界及跨世界交流前提 |
| `relationship_premise` | 可空 string | 用户身份映射与原作关系起点，不保存后来形成的亲近程度 |

字段先采用短文本、文本数组和简单称呼映射；不展开情绪分支、评分算法或完整 Canon 资料树。已知资料才填写；未确认内容不以猜测填充，资料不完整的版本继续标注为联调版本。

### 3. 与运行数据的边界

| 示例 | 归属 |
| --- | --- |
| 角色的核心性格、默认说话习惯 | `character_versions.definition` |
| 原作剧情进度 | 当前 `character_versions.checkpoint`，完整 Canon 契约后续设计 |
| 用户不喜欢香菜、两人达成的约定 | `personal_memories`，绑定实例 |
| 当前担心用户、当前交流情绪 | `character_states`，绑定实例 |
| 相处后形成的信任与亲近 | `relationships`，绑定实例 |
| 一轮交流的原始内容 | `conversations` / `turns` / `messages` |

娜娜莉映射鉴定师伙伴关系沿用已确认基线；伊洛伊和薄荷的映射仍待确认，不复制娜娜莉的关系前提。未来工具权限属于 Runtime，不因导入角色定义自动获得。

### 4. 当前链路与后续接入建议

当前启动后需显式运行 `seed.py` 导入角色资料；已有版本必须保持不可变。发送消息时，`repository.py` 通过会话找到实例及版本，读取 `system_prompt`，交给 `context.py` 追加个人记忆、可选状态与最近历史，再调用文本 Provider。

结构化接入建议是先校验 `definition`，再由独立 Prompt Builder 编译角色提示词，复用现有上下文链路；既有纯 `system_prompt` 版本保留兼容，新设定建立新版本，不覆盖旧实例引用。是否将编译结果保存在 `system_prompt` 需在实现前定稿。

### 5. 本轮完成与下一步

Minimal Character Schema v1 的实现与验证范围见 [实施记录](../implementation/character-schema-minimal.md)。新角色包校验 `definition` 的全部七个固定键（含 `schema_version`），导入时按固定顺序编译并冻结 `system_prompt`；旧的纯提示词包保持兼容。实现不修改 API、前端、正式角色资料或实例运行数据。下一步在数据库验证完成后转入 Memory System 设计；完整角色结构与内容优化等 Memory System 完成后再开展。

## 待设计

- 定义与实例的扩展字段、正式 Canon Checkpoint 与更新契约；不把已有基础模型误记为尚未实现。
- 娜娜莉的准确剧情节点、资料来源、初始关系与 Voice Profile 引用。
- 伊洛伊、薄荷的独立角色定义、Canon 基线、用户关系映射及 Voice Profile；不直接复制娜娜莉的身份关系。
- 差异化测试角色与素材的公开边界。

## 验收方向

同一套加载与实例机制支持多个角色，不写死娜娜莉；不会加载超出实例剧情进度的资料。
