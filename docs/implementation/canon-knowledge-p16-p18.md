# Canon K4 批次四：P16–P18

状态：完成。

## 本批次范围

本批次把 P16–P18 的本地审核稿提升为正式研究数据：

- P16《第7话 勇者斗赤龙 1》（`main_story`）
- P17《第7话 勇者斗赤龙 2》（`main_story`）
- P18《第7话 勇者斗赤龙 3》（`main_story`）

按提升流程执行「已审核逐字稿 → 分 P Scene → 中立 Canon Evidence → 人物/世界/原作知识 → 人物表现证据」。本批次**不建立任何 Trait**，跨 P Trait 归纳留到五个批次全部完成后的全集阶段。没有写入生产 PostgreSQL、Character Definition、CharacterInstance 或聊天运行时。

## 审核数据（预检与审核校验）

| 分 P | 标题 | 源候选 | 审核通过 | 剔除 | 确认说话者 | 保持未知 | 视觉复核 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P16 | 第7话 勇者斗赤龙 1 | 544 | 525 | 19 | 292 | 233 | 22 |
| P17 | 第7话 勇者斗赤龙 2 | 205 | 196 | 9 | 139 | 57 | 9 |
| P18 | 第7话 勇者斗赤龙 3 | 177 | 170 | 7 | 79 | 91 | 7 |
| 合计 | — | 926 | 891 | 35 | 510 | 381 | 38 |

每个分 P 的 `review_validate` 均通过，`approved + rejected = source_utterances`，无无效裁决。完整逐字稿、候选帧和原视频仍只保存在 Git 忽略的本地 staging。

## 正式入库结果

- 新增 checkpoint `nt-bv1kqoabievz-p16` 至 `nt-bv1kqoabievz-p18`，内容轨道均为 `main_story`；前置链 `p15 → p16 → p17 → p18`，sequence 为 16–18。
- 891 条审核通过逐字稿整理为 **28 个正式 Scene**（P16 13 / P17 6 / P18 9），并生成 **103 条 accepted Canon Evidence**（P16 44 / P17 29 / P18 30）；每个通过逐字稿恰好归属一个 Scene。
- 人物目录保持 **71 人**，本批次**未新增人物**：本话有名字的登场者仅有薄荷（`mint`）、伊洛伊（`iroi`）、真红（`shinku`）、娜娜莉（`nanally`）、阿德勒（`adler`），均已在目录中。
- 结构化知识新增：9 个世界实体、16 条人物事实、9 条世界事实、5 条原作人物关系、13 条人物表现证据。
- **本批次不创建 Trait**；`traits` 计数保持 17。
- P16–P18 的 source part 保持 `reviewed`，`visual_subtitle_status` 更新为 `verified_present`。
- 三张审核视图刷新到 P18 checkpoint：71 名人物、125 个世界实体、125 条人物关系。

## 关键处理与边界

- 本话是一场桌游式冒险游戏（薄荷家中的「九百九十九夜」），登记 `jiubai-jiushijiu-ye`（九百九十九夜）、`chengzhu-shaizi`（城主骰子）、`wolun-continent`（沃伦大陆）、`mianmian`（绵绵）、`mianmian-village`（绵绵村）、`mianmian-city`（绵绵城）、`scarlet-dragon`（赤龙）、`dragon-armor`（龙之铠甲）、`amber-lake`（会致幻的琥珀湖）共 9 个世界实体；收容二组（`containment-group-two`）沿用既有 id。
- 游戏世界的设定（沃伦大陆、绵绵由棉花糖构成、赤龙霸占绵绵城、龙之铠甲会侵蚀精神、琥珀湖致幻等）**一律按 `reported_claim` 保存**，不写成客观世界规则；游戏中「大英雄」等叙述亦为剧内故事。
- 游戏旁白/规则（城主骰子借众人声音解说）与角色扮演创建环节按中立证据记录，不把游戏机制当成现实设定。
- 角色扮演中的命名对象（神秘商绵、好斗绵、失主绵、艺术绵、维修绵、村长绵、赤龙等）均为游戏内 NPC 或通用角色标签，**不登记为人物**；「可可」为鉴定师在游戏中的化名，归入既有 `esper-zero`。
- 真红的梦境（独属于她一人的梦、被指责「那才是真正的你」）属致幻作用下的内心投射，按带 `limitations` 的表现证据保存，不写成客观事实。
- 原作人物关系仍不进入现实用户与角色实例的 Runtime Relationship。

## 验证

- 预检：18 个分 P、7,845 源候选、7,308 通过、537 剔除无错误；P16–P18 逐 P 覆盖与复查校验通过。
- 每个分 P 的提升计划重复执行均返回 `idempotent_replay=true`（首次 `false`、二次 `true`）。
- 28 个 Scene 对 891 条通过逐字稿恰好覆盖一次。
- 正式 corpus 全量引用校验通过：人物 71、场景 469、Canon Evidence 1018、world 实体 125、人物事实 233、世界事实 140、人物关系 125、人物表现证据 190。
- 隔离 SQLite Schema `1.1` 重建成功；P18 checkpoint 三张审核视图生成成功。
- 44 项定向测试通过；Ruff 通过。
- 知识构建器新增 `affected_fields` 枚举前置校验（本批次修复了 1 条误用 `ability` 的表现证据），并沿用事实二选一与引用存在性校验。

## 后续

本批次在 P18 闭环后继续原任务，下一批次为 P19–P22（最后一组），随后进行 P1–P22 全集 Trait 归纳与 `docs/implementation/character-definition-candidates-p05-p22.md`。
