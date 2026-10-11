# P5–P22 Canon 提升与全集归纳：汇总实施报告

状态：完成。生产数据库、Memory、Provider、前端与正式 Character Definition 均未改动。

## 一、五个批次与提交

| 批次 | 范围 | 提交 |
| --- | --- | --- |
| 批次一 | P5–P8（第 3 话 + 3 番外） | `b1bda85` |
| 批次二 | P9–P11（第 4 话 1–2、第 5 话） | `90d9795` |
| 批次三 | P12–P15（第 6 话 1–4） | `0adfcfb` |
| 批次四 | P16–P18（第 7 话 1–3） | `79bbbf0` |
| 批次五 | P19–P22（第 8 话 1–4） | `ba98e62` |

随后在第五节提交「全集 Trait 归纳 + 三角色六字段候选」。

## 二、每个分 P 的 Scene 与 Canon Evidence

| 分 P | Scene | Canon Evidence | 分 P | Scene | Canon Evidence |
| --- | ---: | ---: | --- | ---: | ---: |
| P05 | 43 | 43 | P14 | 16 | 32 |
| P06 | 37 | 81 | P15 | 23 | 51 |
| P07 | 29 | 33 | P16 | 13 | 44 |
| P08 | 47 | 75 | P17 | 6 | 29 |
| P09 | 27 | 67 | P18 | 9 | 30 |
| P10 | 45 | 171 | P19 | 13 | 30 |
| P11 | 51 | 208 | P20 | 13 | 39 |
| P12 | 13 | 30 | P21 | 10 | 33 |
| P13 | 15 | 29 | P22 | 10 | 27 |
| **合计** | **420** | **1,052** | | | |

P1–P4 另有 95 个 Scene / 95 条 Canon Evidence。正式库合计 515 个 Scene、1,147 条 Canon Evidence。

## 三、人物、世界与关系增量（P5–P22）

| 项 | 批次一 | 批次二 | 批次三 | 批次四 | 批次五 | 合计 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 新增人物 | 17 | 10 | 2 | 0 | 18 | **47** |
| 世界实体 | 31 | 34 | 9 | 9 | 10 | **93** |
| 人物事实 | 45 | 75 | 49 | 16 | 49 | **234** |
| 世界事实 | 16 | 37 | 33 | 9 | 16 | **111** |
| 原作关系 | 25 | 47 | 21 | 5 | 21 | **119** |
| 人物表现证据 | 27 | 58 | 41 | 13 | 27 | **166** |

人物目录由 42 增至 **89**（新增 47 名具名人物，均先登记为 `discovered`）。正式库现有 135 个世界实体、282 条人物事实、156 条世界事实、146 条原作关系、217 条人物表现证据。

## 四、全集 Trait 归纳（P1–P22）

输入为已接受的 Scene、Canon Evidence 与 `evidence.jsonl`，未重新读取长逐字稿。

- 新增 **34 条** Trait，Trait 总数 17 → **51**。
- 归纳规则：某一表现模式须由 **≥2 个相互独立的 Scene** 支持才形成 Trait；只在单章或单一触发条件出现的表现标记为 `conditional` 并在 `boundaries` 写清章节范围；腹黑/毒舌/依赖/爱慕/敌意等高解释性标签一律配反向边界。
- 覆盖：**所有拥有 ≥2 条表现证据的角色（33 名）都获得了至少一条 Trait**；拥有 1 条证据的次要角色共 24 名保持 **evidence-only**，不强行归纳。
- 新增 Trait 涉及角色：nanally(2)、blackbird(2)、esper-zero(2)、daffodill(3)、adler(1)、mint(1)、hotori(1)、edgar(1)、sakiri(1)、taygedo(1)、iroi(1)、chaos(1)、shinku(1)、zankou(1)、linko(1)、leini(1)、nixia(1)、yinanna(1)、beila(1)、deluolisi(1)、anni(1)、xiaozhen(1)、baicang(1)、haniel(1)、jansen(1)、skia(1)、aierfeide(1)、fadia(1)、akane-rin(1)。
- 保持 evidence-only 的单条证据角色：abigail、duote、erika、fenghua、hulaoda、jiejiexiong、jiersi、kedun、lacrimosa、laweiniya、lilian、liweisi、lizi、meilula、mitsuki、naili、phil、piketuo、posaite、qingze、tuiyue、weituo、xiari、yiweite。
- P1–P4 既有 17 条 Trait 未被覆盖或改写；新 Trait 只描述未被既有 Trait 覆盖的侧面。

## 五、三位正式角色六字段候选

已产出 `docs/implementation/character-definition-candidates-p05-p22.md`（**仅供审核，未导入**），按 Character Definition v1 六字段（identity / personality / speaking_style / behavior / worldview / relationship_premise）组织，覆盖 `nanally`、`iroi`、`mint`。主要变化：

- **nanally**：新增「以守护家人为自我价值、并独自背负与自我怀疑」和「凭直觉果断决断并即兴命名」两条 Trait 支撑的性格与表达面；补充猫头音乐队、虎老大担保等身份事实。
- **iroi**：新增「亲切条理的接待者、把关切做成实际行动」Trait，补充临时义工与手缝慰问礼物等可验证身份行为。
- **mint**：新增「把关心藏在暗中保护与立即行动里」core Trait，补充主持桌游、下厨等身份行为。
- 每条建议均给出：现有候选、建议增补/修订、支持的 Trait/Evidence/Canon Evidence ID、适用 checkpoint、反向边界与「采纳后对角色回复的影响」；末尾列出三项待审项。

## 六、验收结果

- **提升计划再校验**：P5–P22 全部 18 个计划通过哈希、checkpoint 链、sequence、Scene/Canon Evidence 唯一性、逐字稿恰好覆盖一次与 **幂等重放**（`idempotent_replay=true`）检查，`all_ok=true`。
- **正式 corpus**：`validate` 通过——人物 89、别名 12、来源 25、source_part 22、档案 23、Scene 515、表现证据 217、Trait 51、checkpoint 22、Canon Evidence 1147、世界实体 135、人物事实 282、世界事实 156、人物关系 146。
- **构建**：隔离 SQLite Schema `1.1` 重建成功。
- **视图**：P22 checkpoint 生成人物地图、世界知识与 Mermaid 人物关系图三张 views 成功（89 人物 / 135 实体 / 146 关系）。
- **定向测试**：character corpus / Canon view / video promotion / character video pipeline / character profile candidates 共 **42 项通过**。
- **Ruff**：整个仓库 `ruff check .` 通过。
- **后端测试**：本机无 Docker，后端数据库相关测试未运行（含 `tests/test_character_definition.py`，其 `database` fixture 在本环境不可用）；未调用任何真实聊天模型。
- **Git diff 检查**：仅 `research/character-corpus/traits.jsonl`、`tests/test_character_research.py` 与新增的 `docs/implementation/character-definition-candidates-p05-p22.md` 变化；无产品数据库、Memory、Provider、前端或正式角色版本变更。

## 七、发现的矛盾、未知项与保守处理

- 第 8 话「褪月 / 安妮 / 梅露拉」三者关系只记录剧情给出的关联与疑点，**不合并人物**；相关关系标 `confidence="supported"`，明确「是否同一人保持未知」。
- 异象空间/游戏世界/幻境/梦境/广播中的设定一律按 `reported_claim` / `character_belief` 保存，不写成客观世界规则；未具名敌人「审判官」、未出场「司铎」、仅文本提及的人名、泛称与 OCR 噪声均不建人物 ID。
- 修复记录：批次五知识构建器初版把 16 条世界事实误写成 `objective + perspective_character_id`，与 `WorldFactRecord` 约束冲突；`wf()` 改为「带 perspective 即自动降为 `reported_claim`」并用一次性脚本移除误写行后重建。
- 归纳阶段：梦境/内心投射中的自我怀疑只作性格参考，不当清醒时既定陈述；`iroi` 证据较少（3 条），其 Trait 标 `supporting` 并注明跨章频率待补。

## 八、阻塞项

无真实阻塞。仅「后端数据库测试因本机无 Docker 而跳过」属环境限制，不影响正式研究资料的完整性。
