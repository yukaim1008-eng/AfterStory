# Canon K4 批次五：P19–P22

状态：完成。

## 本批次范围

本批次把 P19–P22 的本地审核稿提升为正式研究数据：

- P19《第8话 魔女 1》（`main_story`）
- P20《第8话 魔女 2》（`main_story`）
- P21《第8话 魔女 3》（`main_story`）
- P22《第8话 魔女 4》（`main_story`）

按提升流程执行「已审核逐字稿 → 分 P Scene → 中立 Canon Evidence → 人物/世界/原作知识 → 人物表现证据」。本批次**不建立任何 Trait**，跨 P Trait 归纳留到五个批次全部完成后的全集阶段。没有写入生产 PostgreSQL、Character Definition、CharacterInstance 或聊天运行时。

## 审核数据（预检与审核校验）

| 分 P | 标题 | 源候选 | 审核通过 | 剔除 | 确认说话者 | 保持未知 | 视觉复核 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P19 | 第8话 魔女 1 | 285 | 269 | 16 | 89 | 180 | 16 |
| P20 | 第8话 魔女 2 | 375 | 361 | 14 | 74 | 287 | 14 |
| P21 | 第8话 魔女 3 | 401 | 392 | 9 | 99 | 293 | 10 |
| P22 | 第8话 魔女 4 | 239 | 225 | 14 | 40 | 185 | 14 |
| 合计 | — | 1,300 | 1,247 | 53 | 302 | 945 | 54 |

每个分 P 的 `review_validate` 均通过，`approved + rejected = source_utterances`，无无效裁决。完整逐字稿、候选帧和原视频仍只保存在 Git 忽略的本地 staging。

## 正式入库结果

- 新增 checkpoint `nt-bv1kqoabievz-p19` 至 `nt-bv1kqoabievz-p22`，内容轨道均为 `main_story`；前置链 `p18 → p19 → p20 → p21 → p22`，sequence 为 19–22。
- 1,247 条审核通过逐字稿整理为 **46 个正式 Scene**（P19 13 / P20 13 / P21 10 / P22 10），并生成 **129 条 accepted Canon Evidence**（P19 30 / P20 39 / P21 33 / P22 27）；每个通过逐字稿恰好归属一个 Scene。
- 人物目录由 **71 人增至 89 人**，本批次**新增 18 名具名人物**（均先登记为 `discovered`）：褪月（`tuiyue`）、夏莉（`xiari`）、费伊（`feiyi`）、安妮（`anni`）、维克托（`weituo`）、路易（`luyi`）、多特（`duote`）、阿比盖尔（`abigail`）、贝蒂（`beidi`）、费思（`feisi`）、科顿（`kedun`）、比利（`bili`）、玛丽（`mali`）、里维斯（`liweisi`）、皮克托（`piketuo`）、丽兹（`lizi`）、吉尔斯（`jiersi`）、梅露菈（`meilula`）。
- 结构化知识新增：10 个世界实体、49 条人物事实、16 条世界事实、21 条原作人物关系、27 条人物表现证据。
- **本批次不创建 Trait**；`traits` 计数保持 17。
- P19–P22 的 source part 保持 `reviewed`，`visual_subtitle_status` 由 `user_confirmed_present` 更新为 `verified_present`。
- 三张审核视图刷新到 P22 checkpoint：89 名人物、135 个世界实体、146 条人物关系。

## 关键处理与边界

- 第 8 话的舞台是「圣阿尔博镇」异象空间：该空间是过去被烧死的「魔女」梅露菈用灵魂与恶魔交易换来的异能造物（「血肉之笼」），囚禁着猎巫异象「审判官」。登记 `saint-albo-town`（圣阿尔博镇）、`yushi`（谕石）、`holy-tree`（神树）、`witch-hunt-anomaly`（猎巫异象）、`judge-anomaly`（「审判官」）、`flesh-cage`（血肉之笼）、`witch-trials`（魔女审判）、`malleus-maleficarum`（《魔女之锤》）、`xingchen-bay`（星沉湾）、`witch-purification`（净化与引渡）共 10 个世界实体。
- 异象空间内的一切（圣阿尔博镇的传说、谕石成因、魔女审判流程、《魔女之锤》、「审判官」的特性、血肉之笼的来源、星沉湾无梅露菈之情报）**一律按 `reported_claim` 保存并标注 `perspective_character_id`**，不写成当下海特洛的客观世界规则。
- **人物消歧**：本话口语化称呼极多，`speaker_label` 大量为未具名或泛称，故只登记可稳定映射的具名人物。**不登记**：卡面未具名的敌人「审判官」（`participants` 保持空）、全程未出场的「司铎」、仅在文本中被提及而从未作为说话者出现的玛莎 / 约翰 / 维达 / 丽贝卡 / 弗兰 / 莉莉 / 汤姆 / 威廉 / 哈桑，以及泛称「镇民们 / 女孩们」和 OCR 噪声 `23415` / `小` / `J川G`。
- **身份悬置**：「褪月」「安妮」「梅露拉」三者的关系只按剧情给出的关联与疑点记录，不擅自合并人物。关系 `tuiyue-anni-same-body-unknown` 标为 `confidence="supported"`，明确声明「是否同一人保持未知」；人物事实 `anni-canon-status-later-revealed-as-meilula-disguise` 只记录第 8 话结尾的「假扮」揭示，不把 `anni` 合并进 `meilula`。
- 「安妮」「褪月」「科顿」等主观说法、传闻与剧情内文档同样按 `character_belief` / `reported_claim` 标注，不写成客观事实。
- 原作人物关系仍不进入现实用户与角色实例的 Runtime Relationship。

## 验证

- 预检：P5–P22 共 18 个分 P、7,845 源候选、7,308 通过、537 剔除、590 条视觉复核，无错误；P19–P22 逐 P 覆盖与复查校验通过。
- 每个分 P 的提升计划重复执行均返回 `idempotent_replay=true`（首次 `false`、二次 `true`）。
- 46 个 Scene 对 1,247 条通过逐字稿恰好覆盖一次。
- 正式 corpus 全量引用校验通过：人物 89、别名 12、场景 515、Canon Evidence 1147、canon checkpoint 22、world 实体 135、人物事实 282、世界事实 156、人物关系 146、人物表现证据 217、Trait 17。
- 隔离 SQLite Schema `1.1` 重建成功；P22 checkpoint 三张审核视图生成成功。
- 41 项定向测试通过；Ruff 通过。
- 修复：知识构建器初版把本批次 16 条世界事实误写成 `objective + perspective_character_id`，与 `WorldFactRecord` 约束（`objective` 事实不得带 `perspective_character_id`）冲突。构建器 `wf()` 改为「带 prospective 即自动降为 `reported_claim`」，并以一次性修复脚本移除误写行后重建，全量校验恢复通过。

## 后续

本批次在 P22 闭环后，五个提升批次全部完成。下一步按原任务执行 P1–P22 全集 Trait 归纳，并产出 `docs/implementation/character-definition-candidates-p05-p22.md`（仅审核，覆盖 nanally / iroi / mint 三个正式角色的六字段候选），最后做统一验收。
