# Canon K4：P2 剧情、知识与人物证据

状态：完成。

## 本阶段范围

本阶段只处理 `BV1kqoaBiEVZ` P2《第1话 生意经与招财宝》，复用现有本地视频工具完成下载、画面字幕 OCR、逐条审核、正式 Scene / Canon Evidence 提升、结构化知识审核和审核视图刷新。没有处理 P3，没有写入生产 PostgreSQL、Character Definition、CharacterInstance 或聊天运行时。

## 视频处理与人工审核

| 项目 | 结果 |
| --- | ---: |
| 视频时长 | 65:47 |
| 字幕候选 | 1,409 |
| 有效 OCR 样本 | 673 |
| 台词候选 | 365 |
| 审核通过 | 322 |
| 剔除 | 43 |
| 已确认说话者 | 257 |
| 上下文支持的推定说话者 | 57 |
| 保持未知 | 8 |
| 待审核 | 0 |

审核使用 41 张全画面九宫格联系表逐项回看。剔除内容包含逐字字幕中间态、重复项、玩法/教程 UI 与背景文字；世界内文档继续保留。没有根据单个镜头强行猜测电影过场说话者。

原视频、OCR checkpoint、审核帧、逐字稿和 HTML 报告继续保存在 Git 忽略的 `research/character-corpus/local/video-pipeline/`，正式研究库只保存摘要、稳定 ID、时间范围和逐字稿引用。

## 正式入库结果

- 新增 checkpoint `nt-bv1kqoabievz-p02`，前置 checkpoint 为 P1；
- 322 条审核通过逐字稿整理为 20 个正式叙事场景和 20 条 accepted Canon Evidence；
- 新增塔吉多、柯达两个剧情人物；
- 新增 10 个世界实体、15 条人物事实、7 条世界事实和 5 条原作人物关系；
- 新增 17 条人物表现证据，并从多条证据归纳 7 个 `evidence_confirmed` Trait；
- 达芙蒂尔目前只有一条表现证据，没有提前提升为稳定 Trait；
- P2 source part 更新为 `reviewed`，画面字幕状态更新为 `verified_present`。

浔的性格证据归纳为“精明圆滑的经营者”，包含轻松圆滑、偶尔狡黠、重视经营和成员处境，并明确限制为“不是恶意欺骗、不是只看利益”。其他 Trait 同样保存适用场景和反向边界，避免把一次剧情表现无限泛化。

## 数据边界

P2 中阿德勒、浔、塔吉多、薄荷和娜娜莉对异能者·零的态度，只记录为原作 Canon 关系。记录不含现实 `user_id`，没有写入 Runtime Relationship，也没有把游戏主角经历赋给 AfterStory 用户。

人物表现证据与 Trait 留在研究库，尚未修改三位正式角色的六字段 Definition。后续必须在累计剧情证据完成并经过角色资料审核后，才能创建新的不可变 CharacterVersion。

## 验证

- P2 复核覆盖校验：365/365 已决定，322 条通过，43 条剔除，0 条待审；
- 提升计划完整覆盖 322 条通过逐字稿，SHA-256 固定；
- 同一提升计划重复执行返回 `idempotent_replay=true`；
- 正式 corpus 全量引用校验通过；
- 隔离 SQLite Schema `1.1` 重建成功；
- P2 checkpoint 三张审核视图生成成功；
- Canon、视频工具、提升和视图定向测试通过；
- Ruff 通过。

全后端回归已启动，但本机 `dockerDesktopLinuxEngine` 管道当前不存在，`scripts.doctor` 也确认数据库不可达；数据库用例在连接超时后终止。P2 不依赖 PostgreSQL，未启动、停止或修改用户容器。

## 停止点

P2 已完整闭环，P3 尚未下载或处理。下一阶段应继续以单个分 P 为单位处理 P3，不自动开始。
