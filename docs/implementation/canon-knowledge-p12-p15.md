# Canon K4 批次三：P12–P15

状态：完成。

## 本批次范围

本批次把 P12–P15 的本地审核稿提升为正式研究数据：

- P12《第6话 雾巢游戏 1》（`main_story`）
- P13《第6话 雾巢游戏 2》（`main_story`）
- P14《第6话 雾巢游戏 3》（`main_story`）
- P15《第6话 雾巢游戏 4》（`main_story`）

按提升流程执行「已审核逐字稿 → 分 P Scene → 中立 Canon Evidence → 人物/世界/原作知识 → 人物表现证据」。本批次**不建立任何 Trait**，跨 P Trait 归纳留到五个批次全部完成后的全集阶段。没有写入生产 PostgreSQL、Character Definition、CharacterInstance 或聊天运行时。

## 审核数据（预检与审核校验）

| 分 P | 标题 | 源候选 | 审核通过 | 剔除 | 确认说话者 | 保持未知 | 视觉复核 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P12 | 第6话 雾巢游戏 1 | 227 | 192 | 35 | 56 | 136 | 35 |
| P13 | 第6话 雾巢游戏 2 | 241 | 229 | 12 | 144 | 85 | 13 |
| P14 | 第6话 雾巢游戏 3 | 237 | 228 | 9 | 95 | 133 | 9 |
| P15 | 第6话 雾巢游戏 4 | 390 | 356 | 34 | 126 | 230 | 36 |
| 合计 | — | 1,095 | 1,005 | 90 | 421 | 584 | 93 |

每个分 P 的 `review_validate` 均通过，`approved + rejected = source_utterances`，无无效裁决。完整逐字稿、候选帧和原视频仍只保存在 Git 忽略的本地 staging。

## 正式入库结果

- 新增 checkpoint `nt-bv1kqoabievz-p12` 至 `nt-bv1kqoabievz-p15`，内容轨道均为 `main_story`；前置链 `p11 → p12 → p13 → p14 → p15`，sequence 为 12–15。
- 1,005 条审核通过逐字稿整理为 **67 个正式 Scene**（P12 13 / P13 15 / P14 16 / P15 23），并生成 **142 条 accepted Canon Evidence**（P12 30 / P13 29 / P14 32 / P15 51）；每个通过逐字稿恰好归属一个 Scene。
- 人物目录由 69 人增至 **71 人**，新增 2 名剧情人物：妮夏（P14）、小贞（P14）。全部登记为 `discovered`。
- 结构化知识新增：9 个世界实体、49 条人物事实、33 条世界事实、21 条原作人物关系、41 条人物表现证据。
- **本批次不创建 Trait**；`traits` 计数保持 17。
- P12–P15 的 source part 保持 `reviewed`，`visual_subtitle_status` 更新为 `verified_present`。
- 三张审核视图刷新到 P15 checkpoint：71 名人物、116 个世界实体、120 条人物关系。

## 关键处理与边界

- 本批次是新游戏空间「雾巢」的登场：登记 `wuchao`（雾巢）、`wuchao-game`（雾巢游戏）、`wujiu`（雾柩，规则异象黑棺）、`wushu`（雾枢，雾巢核心）、`special-containment`（特殊收容）、`xiaoyee`（小夜蛾代号）、`youchaoniao`（囿巢鸟）、`huihuan`（辉环）、`wuchao-companion-distorted-remnant`（雾巢伴生歧骸）共 9 个世界实体；「红字」「白蜡树」「维特海默值」「忒修斯之舵」「恒今时」「第一枝」「零号异象」等沿用既有 id。
- T 女士与「伊南娜」为同一人的推断、伊南娜「以女儿们化作养分」的自述、雾柩「吞噬」异象、雾枢「只留唯一胜者」等一律按 `reported_claim` / `character_belief` 保存，不写成客观世界规则。
- 幻象中的「未来伊波恩」（百年后独存的店长、第一枝推演的未来片段）、梦境与占卜式旁白（神秘旁白、谜题广播）均视为幻象或广播内容处理，不当作已发生的客观事实。
- 未登记的说话者：`小男孩`（P14 中灵可复述出姓名「阿洛伊斯」，但其本体、归属与「月退家」所指仍未确认）、`清道夫`/`学者`/`蒙特`（P13 均为职位或角色标签，「蒙特克里斯托」仅由卡厄斯一次称呼给出）、`未来的你`（P15 幻象独白）、`廷达罗斯`（P12 电波通讯中的单一代号）。这些名字要么是职位/泛称、要么无法稳定消歧，按既定规则**不强行登记人物 ID**，其台词在 Scene 内以客观概括保留。
- 原作人物关系仍不进入现实用户与角色实例的 Runtime Relationship。

## 验证

- 预检：18 个分 P、7,845 源候选、7,308 通过、537 剔除无错误；P12–P15 逐 P 覆盖与复查校验通过。
- 每个分 P 的提升计划重复执行均返回 `idempotent_replay=true`（首次 `false`、二次 `true`）。
- 67 个 Scene 对 1,005 条通过逐字稿恰好覆盖一次。
- 正式 corpus 全量引用校验通过：人物 71、场景 441、Canon Evidence 915、world 实体 116、人物事实 217、世界事实 131、人物关系 120、人物表现证据 177。
- 隔离 SQLite Schema `1.1` 重建成功；P15 checkpoint 三张审核视图生成成功。
- 44 项定向测试通过；Ruff 通过。
- 知识构建器沿用「`object_text`/`object_entity_id` 与 `value_text`/`value_entity_id` 二选一」前置校验，并在写入前校验 canon evidence、character、entity 引用是否存在。

## 后续

本批次在 P15 闭环后继续原任务，下一批次为 P16–P18，再依次为 P19–P22，最后进行 P1–P22 全集 Trait 归纳与 `docs/implementation/character-definition-candidates-p05-p22.md`。
