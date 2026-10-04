# Canon 知识层 K1：P1 正式场景与中立证据

状态：完成。

## 范围

本阶段只把已经逐画面复核的 `BV1kqoaBiEVZ` P1 暂存稿提升为正式 Scene 与 Canon Evidence，
没有生成 Character Trait、修改 Character Definition、写入生产 PostgreSQL 或接入聊天运行时。

## 结果

- 189 条审核通过的台词重新按叙事地点和事件切为 29 个正式场景，没有直接采用 22 个机器时间间隔草稿。
- 每个场景生成一条 accepted 中立证据，共 29 条，保留分 P、毫秒范围和逐字稿引用 ID。
- 完整逐字稿、审核帧和原视频继续留在 Git 忽略的本地暂存区；正式库只提交短摘要和来源定位。
- P1 新增 checkpoint `nt-bv1kqoabievz-p01`，对应《第0话 不虞亦先兆》。
- 登记剧情中明确出现但个人档案目录尚未包含的艾尔菲德与奈丽，研究状态为 `evidence_collected`。
- P1 `source_part` 更新为 `reviewed`，画面字幕状态更新为 `verified_present`。

## 提升契约

`scripts.character_corpus promote-video` 读取本地复核稿与 Git 中的提升计划，执行以下校验后才写入：

1. 复核决定完整覆盖源候选，且 approved 集合与复核逐字稿一致；
2. 逐字稿 SHA-256 与提升计划一致；
3. 每条复核台词只属于一个正式场景，且 189 条全部覆盖；
4. 台词、证据时间范围必须落在对应场景内；
5. 参与者与说话者必须属于场景参与者；
6. 所有正式记录先在临时 corpus 中完成全量引用校验；
7. 相同稳定 ID 只允许内容完全一致的幂等重放，任何差异均拒绝覆盖。

写入后再次执行全量 corpus 校验；进程内异常会恢复四个受影响文件的原内容。

## 验证

- Canon、视频工具与提升命令定向测试：22 项通过；
- Ruff：全仓库通过；
- 正式 corpus 全量引用校验通过；
- 本地 SQLite Schema `1.1` 重建成功，包含 26 名人物、29 个场景与 29 条中立证据；
- 相同 P1 提升计划第二次执行返回 `idempotent_replay=true`。

本轮尝试执行全后端回归时，Docker Desktop Linux engine 当前不可连接，数据库用例在连接阶段超时，
因此终止了该次由 Agent 启动的 pytest；本阶段不依赖 PostgreSQL，未修改或停止用户容器。

## 当前边界

P1 的人物事实、世界实体、世界事实、人物关系以及性格 Trait 尚未生成。P2–P21 也尚未下载和处理。
下一阶段先以 P1 accepted 证据形成 K2 结构化知识，确认事实抽取闭环后再批量推进后续分 P。
