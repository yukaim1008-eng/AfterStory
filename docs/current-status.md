# AfterStory 当前项目状态

- 更新日期：2026-10-11。
- Memory System M1 已实现：记忆不可变版本、多来源、依赖/抑制基础、持久化任务 lease、独立 data revision，以及消息时间和时区来源已落库；旧 PersonalMemory API 与数据继续兼容。
- Memory System M2 已实现：有界分段摘要、跨会话连续性笔记、原文关键词回读，以及 prepare/reserve/finish 的短事务发送边界。
- Memory System M3 已实现：成功轮次后台提取任务、严格候选校验、稳定事实/事件身份、跨批次去重，以及显式记住/纠正/忘记操作回执。
- Memory System M4 已实现：PostgreSQL 全文与 pgvector 混合候选、可选重排、PreparedRuntimeContext 预算和 ContextAssembler 接入；实例与删除状态先做硬过滤。
- Memory System M5 已实现：版本化持续事项、单次站内提醒、到期/错过领取、投递 lease、改期和取消；应用关闭后的外部通知仍按约定留到 Tools 阶段。
- Memory System M6 已实现：来源 span、结构化依赖、有界删除屏障、后台重建、删除 suppression 防复活，以及有明确用户证据的自动纠正版本。
- Memory System M7 已实现：带持续性质的 State proposal、过期视图、关系证据与慢速定性 revision；单条互动和普通轮数不会升级关系。
- Memory System M0–M8 已完整实现并通过统一验收：65 项后端测试、Ruff、前端生产构建和 32 项 Playwright 全部通过；前端已支持长期记忆分类、持续事项与站内提醒，非 fake 运行配置启用持久化提取/摘要/rebuild worker。测试未调用真实模型；离线系统通知继续留到 Tools 编排。
- 2026-09-27 已用隔离 schema、工程角色和虚拟用户完成第一轮真实模型联合验收：稳定偏好、假设过滤、明确纠正、事件补充、跨用户隔离、20 轮摘要/跨会话续聊和站内提醒共 26/26 项通过。联调修复了结构化 JSON 契约、摘要输出预算、自动纠正候选及事件时间/版本问题；30 次 Provider 调用最终无重试，未改默认用户数据。详见 [真实模型评测](implementation/runtime-evaluation.md)。
- 2026-09-30 Response Policy v1 接入后，聊天输入/输出仍为 24000/1024；Character、Memory、State/Relationship、Continuity、History、当前消息与 Runtime/Policy 余量分别为 2500/3000/500/4000/8200/4000/1800。历史按完整旧轮次淘汰，角色与当前消息不静默截断；记忆提取与摘要预算不变。完整说明见 [真实模型评测](implementation/runtime-evaluation.md#token-预算收敛)。
- Token 预算优化后 83 项后端测试、Ruff、Alembic 一致性与 26/26 真实模型回放通过。开发库中“版本已到 head、既有 Memory 表缺失”的历史漂移已用单事务增量补表修复；原有 28 轮/56 条消息和 1 条个人记忆保留，并补齐该记忆的版本与检索索引。本阶段没有新增 migration，也没有修改前端。
- Conversation Core v1 已实现：Provider 返回严格的 Conversation Decision v1，角色回复与显式记住/纠正/忘记、线上提醒、短期 State 和 Relationship evidence 在同一轮编排；assistant 消息与 effects outbox 同事务保存，现有领域服务负责最终校验与幂等提交。普通事实仍走后台提取，纠正/忘记只能引用当前可见记忆。没有新增 migration 或前端改动，详见 [Conversation Core v1 实施记录](implementation/conversation-core-v1.md)。
- Conversation Core v1 最终验收：91 项后端测试、Ruff、Alembic 一致性、脱敏诊断、前端生产构建和 32 项 Playwright 通过；隔离 schema 的真实 DeepSeek 回放 30/30 项通过，共 37 次结构化调用，所有纳入检查的任务最终 completed。评测没有写入默认用户数据或停止用户 Docker。
- Conversation Response Policy v1 已实现：在现有单次结构化调用中加入版本化固定策略，覆盖倾诉/建议/问答/续聊/操作/边界、篇幅、追问、自然记忆引用及 State/Relationship 表达；纯文本 Provider 和安全降级也使用同一策略。没有新增数据库、第二次模型调用或前端改动。17 个 DeepSeek 场景无硬失败，软质量 15/17（88.2%）通过，详见 [实施记录](implementation/response-policy-v1.md)。
- 当前实施：用户已授权 Memory System M0–M8 连续开发。本轮按阶段实现、验证、复查和中文提交，全部完成后统一汇报；实施记录见 [Memory System 实施记录](implementation/memory-system.md)。
- 最新设计进度：Memory System 已按 M0–M8 实现并验收长期连续性、长期记忆、持续事项/提醒、召回、生命周期及 State/Relationship；未打开 AfterStory 时的主动通知仍留到后续 Tools 编排。见 [记忆、状态和关系](design/03-memory-state.md)。
- 长期事实、经历与写入更新规则已形成 [完整待审稿](design/memory/03-long-term-memory-writing.md)。推荐基线覆盖自动保存、推测边界、稳定事件身份、时间精度、后台增量整理、两层去重和冲突更新；用户审核前不视为产品决策，未修改业务代码。
- 最新细化：用户提出事件保留日/月级时间即可，久远回忆可以较粗略；讨论稿补充告知时间与发生时间、精度、后台分批提取、稳定事件身份、两层去重和压缩协作。提取/压缩共用写入入口但分别记录处理进度；这些具体方案仍待评审，未开始实施。
- 持续事项与线上提醒已形成 [完整待审稿](design/memory/04-ongoing-matters-and-online-reminders.md)：推荐单次提醒、服务端投递记录、应用上线补发、改期取消和多入口幂等领取；关闭应用后的通知仍留到 Tools 阶段。
- 记忆召回与上下文选择已形成 [完整待审稿](design/memory/05-retrieval-and-context-selection.md)：推荐确定性读取、PostgreSQL 全文/结构化过滤和 pgvector 混合候选，复杂问题才使用第二阶段模型重排；检索准备不进入现有持锁路径。
- 纠正、删除与重建已形成 [完整待审稿](design/memory/06-lifecycle-correction-deletion-and-rebuild.md)：显式操作同步建立可见性屏障，派生摘要/索引/状态异步受控重建；来源不完整时继续使用现有 `history_floor_revision` 保守保护。
- State 与 Relationship 演进已形成 [完整待审稿](design/memory/07-state-and-relationship-evolution.md)：短期状态可随回复提出并按时间缓和，长期关系由有效事件慢速评估；普通轮数、缺席和单方面关系声明均不自动升级关系。
- [数据契约与实施阶段](design/memory/08-data-contract-and-implementation-plan.md) 已定义权威/派生数据、版本/来源/任务边界、兼容 migration、Runtime 接入和 M0–M8 分阶段验收。整套设计包现等待用户集中审核，不构成开发授权。
- 2026-09-24 只优化 Memory 待审设计稿：M2 提前承担最小原文查找与跨会话未覆盖原文补查，M3 在现有候选上做事件去重并暂缓会高频触发全实例历史排除的自动替代；补上对话内显式操作回执、后台写入与回复安全修订分工、有界删除屏障，以及新消息的接收时间/时区来源。业务代码、数据库及运行数据均未改动，以上仍待集中审核。
- 长会话设计进度：[连续性与压缩](design/memory/01-conversation-continuity.md) 的保留原文、分段摘要配合连续性笔记、压缩赶不上时等待或重试三项方向已确认；[摘要组织、原文选择与离开后续聊](design/memory/02-summary-and-resumption.md) 已形成完整待审稿。数值预算和阈值由实施回放确定。
- 当前阶段：Minimal Character Schema v1 已完成。CharacterVersion 新增可空 `definition` JSONB；结构化定义使用 Schema Version `1.0`、身份/性格/说话方式/行为/世界观/初始关系六个文本字段，并由 Prompt Builder Version `1.0` 编译冻结 `system_prompt`。旧提示词角色保持兼容；Memory、State、Relationship、Conversation 仍归实例运行数据。隔离 schema 迁移升级/回滚与 41 项后端测试均通过，实施记录见 [最小 Character Schema 实施计划](implementation/character-schema-minimal.md)。
- 2026-10-01 已将娜娜莉、伊洛伊、薄荷的官网介绍与公开档案/语音整理为 [正式角色六字段候选](design/character/README.md)。候选包使用完整 Character Definition Schema v1 并可由 Prompt Builder v1.0 编译；本轮只整理公开稳定资料，不补完整剧情 Canon 或 Voice Profile。候选尚待用户集中审核，未导入数据库、未修改前端版本绑定、未切换任何现有角色实例。
- 2026-10-01 人物资料研究库 M0 已完成：建立角色、来源、个人档案、剧情场景、人物证据和特征卡的独立 Schema，支持 MediaWiki revision 同步、严格引用校验和本地 SQLite 重建。异环信息站当前登记 24 名角色，23 名已有个人档案；本地库识别 143 个档案条目与 1955 条语音。完整页面快照和 SQLite 不提交 Git，生产 PostgreSQL、现有角色实例和前端均未修改。后续顺序见 [人物资料研究库](design/character/character-corpus.md)。
- 人物资料研究库 M1 已登记 B 站剧情合集 `BV1kqoaBiEVZ`：21 个分 P、总长 80,387 秒，标题覆盖至 1.4。P1 `05:00–10:00` 的本地画面字幕 OCR 试跑已完成：五分钟精确片段从桌面端缓存生成，PP-OCRv5 在 47 个有效采样帧上得到 21 个去重候选片段，清晰正文与中英混合字幕可用；逐字显示、短句召回和无姓名过场的说话者归属仍需批处理工具处理。媒体与逐字稿只保存在忽略的 `local/`，未开始 22 小时全文分析。详见 [画面字幕 OCR 试跑](implementation/character-corpus-ocr-pilot.md)。
- 2026-10-02 剧情视频本地处理工具 Version `1.0` 已实现并完整处理 P1：35:14 视频从约 63,430 帧筛出 786 个候选，得到 382 个有效 OCR 样本、215 段台词候选和 22 个机器场景草稿。随后完成全画面逐条复核：189 条通过、26 条菜单/误识别/重复/战斗 UI 被剔除；124 条说话者已确认、40 条为证据支持的推定、25 条保持未知。工具已增加静态 HTML 审核报告和严格覆盖校验；审核稿仍只在本地暂存，没有写入 `scenes/evidence/traits`、SQLite、PostgreSQL 或 Character Definition。详见 [剧情视频本地处理工具与 P1 验证](implementation/character-video-pipeline.md)。
- 2026-10-03 [Canon 人物、世界与关系知识层](design/character/canon-knowledge-map.md) 的 K0/K0.1 资料库骨架已实现：新增 checkpoint、中立 Canon 证据、世界实体、人物事实、世界事实和人物关系严格模型；Scene 已补分 P 定位，档案与剧情证据严格二选一，accepted 知识必须引用 accepted 证据。K0.1 又补充结构化人物别名、checkpoint 内容轨道、field/archive/voice 三类严格档案定位，并将剧情事实状态命名为 `canon_status`。引用、作品边界、有效区间、替代链和现实用户 ID 混入均有校验，本地 SQLite Schema `1.1` 采用成功后原子替换。Instance Canon Role Binding 仍只完成设计约束，生产 PostgreSQL、Character Definition、CharacterInstance 和 Provider 均未修改。实施记录见 [Canon 知识层 K0](implementation/canon-knowledge-k0.md)。
- 2026-10-04 Canon K1 已把 P1 的 189 条逐画面复核台词正式提升为 29 个叙事场景和 29 条 accepted 中立证据，并登记艾尔菲德、奈丽两个剧情人物。提升命令校验源候选全覆盖、复核稿 SHA-256、场景覆盖、时间范围和不可变 ID；重复执行幂等，冲突内容拒绝覆盖。完整逐字稿和原视频仍只在忽略的本地暂存区，正式库只保存摘要、定位和引用。见 [Canon 知识层 K1](implementation/canon-knowledge-k1.md)。
- 2026-10-04 Canon K2/K3 已从 P1 accepted 证据形成 12 个世界实体、9 条人物事实、13 条世界事实和 6 条人物关系，并生成按 checkpoint 过滤的 [人物地图](../research/character-corpus/views/character-map.md)、[世界知识页](../research/character-corpus/views/world-knowledge.md) 与 [人物关系图](../research/character-corpus/views/character-relations.md)。所有表项可回到 B 站分 P 时间点；原作关系与现实用户 Runtime Relationship 在视图中再次明确隔离。见 [K2/K3 实施记录](implementation/canon-knowledge-k2-k3.md)。
- 2026-10-05 Canon K4 已完成 P2《第1话 生意经与招财宝》闭环：365 条台词候选逐项复核后保留 322 条，提升为 20 个场景和 20 条 Canon Evidence；补充 10 个世界实体、15 条人物事实、7 条世界事实、5 条原作关系、17 条人物表现证据和 7 个证据确认 Trait。隔离 SQLite、审核视图、幂等提升、定向测试和 Ruff 均通过。见 [P2 实施记录](implementation/canon-knowledge-p2.md)。
- 2026-10-05 剧情视频低成本审核流程已实现：本地规则生成最多 40 条台词、20 张风险图的哈希审核包，轻量模型响应必须经过严格 Schema、说话者边界和自动候选安全门。P2 `00:00–03:50` 盲回放验证了精度；P3 又完成整集自动分包、第二轮轻量复核、41 条残余高审和确定性最终合并。见 [设计](design/character/low-cost-video-review.md) 与 [实施记录](implementation/character-video-low-cost-review.md)。
- 2026-10-05 Canon K4 已完成 P3《番外 月光当铺》闭环：687 条候选经两轮轻量审核与 41 条残余高审后保留 617 条，提升为 25 个场景和 25 条 Canon Evidence；新增 11 名人物、1 个别名、13 个世界实体、17 条人物事实、19 条世界事实、12 条原作关系、19 条人物表现证据与 6 个 Trait。低成本 Prompt 升为 `1.2`，新增整集自动分包和确定性最终合并。隔离 SQLite、三张视图、幂等提升、测试和 Ruff 均通过。见 [P3 实施记录](implementation/canon-knowledge-p3.md)。
- 2026-10-07 剧情审核低 Token 协议 v2 已完成 P4 实跑：65:43 视频产生 563 条候选，本地放行 103 条，其余 460 条组成 5 个无图稀疏文本包；最终只有 74 条进入 9 张视觉联络表，审核保留 500 条、剔除 63 条。P4 已提升为 21 个正式场景和 21 条 Canon Evidence，并新增 3 名人物、7 个世界实体、7 条人物事实、6 条世界事实、4 条原作关系、15 条人物表现证据和 4 个 Trait。核心处理墙钟 32 分 24.9 秒；可复现文本载荷按项目保守算法折算下限约 96,966 Token，图片与 Codex 会话上下文 Token 无法从客户端读取；138 项全量后端测试和 Ruff 全部通过。见 [P4 实施记录](implementation/canon-knowledge-p4.md) 与 [低成本审核实施记录](implementation/character-video-low-cost-review.md)。
- 2026-10-08 P5–P22 已完成协议 v2 全量逐条审核。合集新增 P6《番茄酱暴走现场实录！》后共 22 个分 P，原 P6–P21 顺延为 P7–P22；来源登记已按 B 站分 P ID 重新对齐。P5–P22 共 7,845 条源候选、76 个无图文本包和 590 条视觉复核，最终保留 7,308 条、剔除 537 条。76/76 `lean-validate`、18/18 视觉覆盖与 18/18 `review-validate` 经 WorkBuddy 执行后又由 Codex 独立复验，均无错误。完整 MP4 已在审核证据生成并校验后删除；正式审核稿仍位于本地 staging，尚未提升为 Scene、Canon Evidence、结构化知识或 Character Definition，也未写入产品数据库。
- 2026-10-11 Canon K4 批次一完成 P5–P8 正式提升：第3话《成交？成交！》与三部番外（番茄酱暴走现场实录 / 不言不知秋 / 某传奇乐队（吗？）的第一页）的 2,584 条候选经审核保留 2,327 条，提升为 156 个 Scene 与 232 条 Canon Evidence；新增简森、伊里卡、麦考贝、菲尔、西汀、西瑞尔、安德鲁、科林、克西娅、麦月、炜桦、塞尔温、玲果、黎兰、奥利弗、杪冬、清泽 17 名人物，人物目录 42→59，并为既有 `akane-rin` 补别名「明音」。新增 31 个世界实体、45 条人物事实、16 条世界事实、25 条原作关系、27 条人物表现证据；按计划本批次不建 Trait，留到全集归纳。P5–P8 source part 更新为 `verified_present`，视图刷新到 P08。隔离 SQLite、幂等提升、三张视图、43 项定向测试与 Ruff 全部通过。见 [批次一实施记录](implementation/canon-knowledge-p5-p8.md)。
- 2026-10-11 Canon K4 批次二完成 P9–P11 正式提升：第4话《红字的研究 1/2》与第5话《游梦洄廊》的 1,940 条候选经审核保留 1,838 条，提升为 123 个 Scene 与 446 条 Canon Evidence；新增蕾妮、风花、拉维尼娅、贝拉、德洛莉丝、伊薇特、伊南娜、珀塞特、虎老大、桀桀熊 10 名人物，人物目录 59→69。新增 34 个世界实体、75 条人物事实、37 条世界事实、47 条原作关系、58 条人物表现证据；仍不建 Trait。P9–P11 source part 更新为 `verified_present`，视图刷新到 P11。P10 揭示 P9 委托人蕾妮的真实身份，前后记录并存不回改；梦境与不可靠叙述按 `reported_claim`/`character_belief` 保存。隔离 SQLite、幂等提升、三视图、43 项定向测试与 Ruff 全部通过。见 [批次二实施记录](implementation/canon-knowledge-p9-p11.md)。
- 2026-10-11 Canon K4 批次三完成 P12–P15 正式提升：第6话《雾巢游戏 1–4》的 1,095 条候选经审核保留 1,005 条，提升为 67 个 Scene 与 142 条 Canon Evidence；新增妮夏、小贞 2 名人物，人物目录 69→71。新增 9 个世界实体、49 条人物事实、33 条世界事实、21 条原作关系、41 条人物表现证据；仍不建 Trait。P12–P15 source part 更新为 `verified_present`，视图刷新到 P15。本批次登记雾巢、雾巢游戏、雾柩、雾枢、特殊收容、小夜蛾、囿巢鸟、辉环、雾巢伴生歧骸等新实体；幻象/梦境/广播按 `reported_claim` 保存；「小男孩（阿洛伊斯）」等无法稳定消歧的名字不强行登记。隔离 SQLite、幂等提升、三视图、44 项定向测试与 Ruff 全部通过。见 [批次三实施记录](implementation/canon-knowledge-p12-p15.md)。
- 2026-10-11 Canon K4 批次四完成 P16–P18 正式提升：第7话《勇者斗赤龙 1–3》的 926 条候选经审核保留 891 条，提升为 28 个 Scene 与 103 条 Canon Evidence；本批次未新增人物，人物目录保持 71。新增 9 个世界实体、16 条人物事实、9 条世界事实、5 条原作关系、13 条人物表现证据；仍不建 Trait。P16–P18 source part 更新为 `verified_present`，视图刷新到 P18。本话为薄荷家中桌游「九百九十九夜」的冒险游戏，游戏世界设定（沃伦大陆、绵绵、赤龙、龙之铠甲、琥珀湖等）一律按 `reported_claim` 保存，游戏内 NPC 不登记为人物。隔离 SQLite、幂等提升、三视图、44 项定向测试与 Ruff 全部通过。见 [批次四实施记录](implementation/canon-knowledge-p16-p18.md)。
- 2026-10-11 Canon K4 批次五完成 P19–P22 正式提升：第8话《魔女 1–4》的 1,300 条候选经审核保留 1,247 条，提升为 46 个 Scene 与 129 条 Canon Evidence；新增褪月、夏莉、费伊、安妮、维克托、路易、多特、阿比盖尔、贝蒂、费思、科顿、比利、玛丽、里维斯、皮克托、丽兹、吉尔斯、梅露菈 18 名人物，人物目录 71→89。新增 10 个世界实体、49 条人物事实、16 条世界事实、21 条原作关系、27 条人物表现证据；仍不建 Trait。P19–P22 source part 由 `user_confirmed_present` 更新为 `verified_present`，视图刷新到 P22。本话舞台是「圣阿尔博镇」异象空间，「审判官」为未具名敌人不登记人物，褪月/安妮/梅露拉的同一性保持未知、只记录剧情关联；异象空间内的世界事实一律按 `reported_claim` 保存。隔离 SQLite、幂等提升、三视图、41 项定向测试与 Ruff 全部通过。见 [批次五实施记录](implementation/canon-knowledge-p19-p22.md)。五个提升批次全部完成，下一步进行 P1–P22 全集 Trait 归纳与三角色六字段候选。
- 2026-10-11 Canon K4 全集归纳完成：五个提升批次（P5–P8、P9–P11、P12–P15、P16–P18、P19–P22）全部闭环后，基于 P1–P22 已接受的 Scene / Canon Evidence / 人物表现证据做跨 P Trait 归纳，新增 34 条 Trait，Trait 总数 17→51；规则为「某表现须由 ≥2 个独立 Scene 支持才成 Trait，单章表现标 `conditional`，高解释性标签必配反向边界」。所有拥有 ≥2 条表现证据的 33 名角色均获得 Trait，24 名单条证据角色保持 evidence-only。P5–P22 共 420 Scene / 1,052 Canon Evidence，人物目录 42→89。同时产出 `docs/implementation/character-definition-candidates-p05-p22.md`（nanally/iroi/mint 六字段候选，仅审核未导入）。18 个提升计划哈希/链/覆盖/幂等复查全绿；validate 89/515/1147、build、P22 三视图、42 项定向测试与 Ruff 全部通过。汇总见 [P5–P22 汇总报告](implementation/canon-knowledge-p05-p22-summary.md)。
- 当前授权：UI / UX 完整改版 Phase 1–8 已完成；用户随后要求按页面分阶段清理旧视觉技术债，ChatPage 布局清理和角色氛围文案精修、Home、Characters、Memories 及 SettingsPage 视觉精修均已完成并通过前端验证。全站最终视觉审查与最小统一修正亦已完成，见 [执行记录](implementation/ui-redesign.md)。本轮未修改后端与角色提示词。
- 最新授权：全站最终视觉审查只统一 Design System、响应式与状态表现，不重构页面、不新增功能或修改业务逻辑；已完成后停止。
- 当前阶段：用户授权的 A–E 五阶段方案已全部实现、验证并分别提交。执行结果见 [F2 方案](implementation/f2-foundations.md)。
- F2 已交付历史与旧版本恢复、个人记忆管理、上下文契约、状态与关系内部存储边界，以及脱敏诊断和整体验证入口。
- F1 开发授权及结果保留；用户已确定后续优先级为：对话理解与角色表达、正式角色内容、聊天效果验收、自动记忆与关系变化、语音、正式使用环境。完整 V1 尚未验收。

## 已完成

- Vue 3 + TypeScript + Vite 前端已完成角色化改版：首页、角色、回忆、设置四个一级入口；角色聊天为沉浸式二级空间。三位角色聊天、可扩展选择、资料、历史、通用/外观/声音/数据设置，以及个人记忆管理均保留。
- ChatPage 已移除旧 40:60 Grid 和全局 `.workspace` 依赖，改为覆盖单个 viewport 的角色场景与绝对定位 Chat Glass Layer；人物由背景肖像层和跨越玻璃左缘的独立穿入层组成，聊天材质与聊天内容分层，页面本身锁定纵向滚动，只有消息列表可滚动。
- ChatPage 的角色空间目录、签名、头像短句及玻璃内上下角批注已改为 `characters.json` 中每个角色独立的 `sceneDecorations` 配置；娜娜莉、伊洛伊、薄荷已有不同文案、主题色、角度和位置，回忆入口通过 `{name}` 使用当前角色名。无配置角色由统一解析器提供安全目录和欢迎文案，缺少的可选批注不渲染。
- 三位角色的 ChatPage 默认场景图已分别接入根目录 `背景/` 下的横版素材；开发和构建前会自动复制到未跟踪的 `frontend/public/media/`，角色切换时由现有 `sceneBackground` 配置同步切换。
- 五个核心页面已统一 Desktop 尺寸：72px Header、32–48px 横向留白、20px 纵向留白/间距（低高度窗口 16px）；Home 和 Characters 使用剩余高度，Memories 和 Settings 将滚动限制为列表/内容区。未修改页面内容、颜色、背景与业务逻辑。
- HomePage 已改为以当前角色为中心的相见入口：完整 Hero 场景与淡玻璃欢迎区域自然融合，最近回忆以头像/时间/摘要呈现，空数据时改为小图标、引导与原有聊天入口；快捷动作和其他角色入口去除嵌套 Card，并以同一套轻 surface 收拢为“继续故事”的方向。默认 Hero 复用已配置的角色横版场景；已有个人封面仍优先。三个角色新增独立 `sceneDecorations.homeGreeting`，缺省回退“欢迎回来”。全局尺寸、其他页面样式和业务逻辑未修改。
- CharactersPage 已改为“选择今天想进入谁的世界”的单层舞台：当前角色占左侧主视觉，读取已有角色签名并保留“当前角色/继续和她聊天”入口；另两位角色在右侧作为同屏可见的轻量故事入口。第二轮精修让角色图以渐变延伸到文字区域，移除“图片 + 白色资料区”的硬切分；签名使用轻微手写倾斜，娜娜莉、伊洛伊、薄荷分别保留暖粉、柔和薄荷和更活跃的青蓝 hover。点击仍复用 `choose()` 的原角色切换与聊天跳转，角色扩展时只有右侧列表内部滚动。
- 已确认三位主题、手动语音默认、封面仅当前用户当前角色、09 控件形态。性格素材、封面、主题与发送按钮配置独立于业务代码。
- 文字发送、失败重试、草稿保留、刷新恢复、30 轮历史加载；封面上传、独立裁切、取消、保存与恢复默认。
- 后端保留 M1 API，补充 /api 前缀、并发安全的会话发现、用户隔离的历史列表。
- 个人记忆按角色实例隔离；支持手动录入、保存已完成轮次中的用户消息、后台稳定事实/事件提取，以及 Conversation Core 中明确的记住/纠正/忘记，使用请求 ID 幂等和修订号防止旧上下文覆盖新修改。
- 上下文由独立组装器按固定顺序构建；有效个人记忆可跨同一实例的会话使用，条数和字符数均可配置，不保存完整提示词。记忆变化使生成中的旧上下文回复失效并可重试。
- 短期交流状态与长期关系分别保存；关系只使用熟悉、信任、亲近的文字描述。内部提交必须绑定成功轮次，事件与快照原子保存；普通聊天不会自行产生状态变化，前端也没有关系评分接口。
- `python -m scripts.doctor` 提供脱敏诊断；HTTP 使用 `X-Request-ID` 关联安全日志；`scripts/verify.ps1` 可重复执行全套检查并只停止它自己启动的 PostgreSQL。
- 已用独立 frontend-smoke 身份完成一次真实 DeepSeek 浏览器发送、回复、数据库持久化与刷新恢复；未将测试对话写入默认用户。
- F2 最终验收记录：34 项后端测试、10 项浏览器测试、前端构建、Ruff、脱敏诊断和 Alembic 一致性检查通过；迁移升降级在隔离 schema 中回归通过。一键脚本成功后已停止自己启动的 PostgreSQL，没有遗留前后端服务。

## 当前边界与待定

- 三位主角色：娜娜莉、伊洛伊、薄荷。当前角色包明确标注为联调资料，正式 Canon、性格细节和 Voice Profile 尚未完成。
- 娜娜莉承接与鉴定师的伙伴关系；另外两位的初始关系和身份映射待独立确认。
- 个人记忆、连续性摘要、短期 State 和定性 Relationship 已进入受限运行时上下文；后台记忆提取、混合召回和受控演进已实现。当前没有关系数值算法；Voice、完整 Canon、离线通知和剧情更新仍未实现。
- 本机开发身份由后端注入；无正式登录和跨设备同步。封面、偏好保存在浏览器，聊天保存在 PostgreSQL。
- 当前是完整文字回复，不是流式输出。历史不编造数据库尚未提供的日期。
- 页面视觉重设计已推进 ChatPage、HomePage、CharactersPage、MemoriesPage 与 SettingsPage；MemoriesPage 保留确认布局，以居中的 1060px 单栏回忆流、紧凑统一的筛选工具栏、角色上下文、主面板内日记式条目、轻量连接提示及空/有数据状态完成第三轮精修。SettingsPage 已改为窄分类导航加宽主内容的单栏偏好工作区，当前角色仅在导航底部轻量呈现，通用/外观/声音/数据管理均使用统一 Section + Row 结构，右侧内容独立滚动；其中外观页已进一步拆分角色主题与角色封面，封面以较完整预览和宽松操作区呈现。
- 全站最终视觉审查已覆盖三位角色、Home/Characters/Chat/Memories/Settings、空/有数据/错误状态及四档 Desktop 尺寸；确认所有非 Chat Header 高度为 72px，统一为 20px 居中 active underline，focus ring 改由全局 token 提供。没有页面级纵向或横向 overflow；Home/Characters/Chat 维持单屏，Memories 与 Settings 分别只在列表/右侧面板内部滚动。未发现需要重构的视觉问题。
- 模型上下文默认使用最近 12 轮成功对话，可配置；前端每次加载 30 轮历史。这两者都不等于长期记忆，也不代表模型能读取全部保存记录。

## 运行与上下文

- [下一阶段选择清单](next-step-review.md)：已确认规则、未完成能力、候选工作与暂缓事项。
- [前端运行说明](running-frontend.md)、[前端 README](../frontend/README.md)。
- [前端当前基准](design/06-frontend.md)、[分区入口](design/README.md)。
- [V1 基线](decisions/0001-v1-baseline.md)、[M1 说明](running-m1.md)。

## 下一步

Minimal Character Schema v1、Memory System M0–M8、Conversation Core v1 和 Conversation Response Policy v1 已完成。人物资料研究库已完成 P1–P22 的机械抽取、逐条审核、正式入库与全集 Trait 归纳；Canon K0–K4 已完成 P1–P22 的正式入库、结构化知识、三张审核视图闭环，并完成跨 P Trait 归纳（Trait 51 条）。三位正式角色（nanally / iroi / mint）的六字段修改候选已产出，**仅供审核、仍未导入**；正式 Character Definition 未被修改。离线通知、Voice、Character Schema v2 和 Canon 运行时接入均未启动。

2026-09-18 最新顺序为：最小 Character Schema（暂按六部分拆分）→ Memory 系统设计 → Memory System 完成后优化角色 Schema 与内容；具体字段和实现范围仍待定稿。此次决定调整下方旧阶段排序的当前起点，不表示 Memory 系统已经开发或验收。

2026-09-12 确认的旧优先级为 `3 → 2 → 1 → 4 → 5 → 6`，对应：

1. 对话理解和角色表达。
2. 正式角色内容。
3. 用户集中验收聊天效果。
4. 自动记忆和关系变化。
5. 语音。
6. 正式登录、跨设备同步和部署等使用环境。

每一阶段仍须先明确范围与验收条件；当前先收敛最小角色字段，不因排序一次性实现其余阶段。

测试结束停止 Agent 自己启动的前后端和项目依赖，用户需要看效果时自行启动；不关闭用户自行启动的服务、不删除数据。

暂不增加社区、商城、角色创建器、工具调用、LangGraph、微信、ASR/VAD 或实时语音；不展示好感度、关系进度条或内部分析。
