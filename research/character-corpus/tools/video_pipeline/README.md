# 剧情视频本地处理工具

这个工具把本地剧情录像转换为带时间轴、说话者状态和审核状态的研究暂存包。工具代码提交到 Git；视频、候选帧、OCR 原文和场景草稿固定写入 `research/character-corpus/local/video-pipeline/`，不会直接修改 `scenes.jsonl`、SQLite 或产品数据库。

## 处理边界

```text
B 站桌面端缓存 / 标准视频
→ 标准 MP4
→ 画面字幕候选帧
→ PP-OCRv5
→ 逐字显示合并与去重
→ 说话者状态
→ 场景草稿与审核队列
→ 人工或后续复核
→ 才允许进入研究库
```

说话者使用 `confirmed / probable / ambiguous / unknown` 四种状态。角色目录中的明确姓名标签会成为 `confirmed`；在固定姓名位置稳定重复至少四次的屏幕标签也可确认其字面标签，但没有目录映射时仍进入人工映射审核。电影过场没有标签时保持 `unknown`，工具不会猜测。所有新台词和场景默认 `review_status=pending`，因此初次运行的 `export_ready` 必须为 `false`。

## 运行 P1

```powershell
& research/character-corpus/tools/video_pipeline/run.ps1 `
  -Command run `
  -PartId bilibili-BV1kqoaBiEVZ-p01 `
  -Title "第0话 不虞亦先兆" `
  -CacheDir "$env:USERPROFILE\Videos\bilibili\37739368085"
```

## 下载并处理后续分 P

后续分 P 可以从已登记的 B 站合集按 1080p 视频与最高可用音频分轨下载；下载支持断点续传，
媒体直接写入对应的 Git 忽略 staging 目录：

```powershell
& research/character-corpus/tools/video_pipeline/download.ps1 -PartNumber 2

& research/character-corpus/tools/video_pipeline/run.ps1 `
  -Command run `
  -PartId bilibili-BV1kqoaBiEVZ-p02 `
  -Title "第1话 生意经与招财宝" `
  -Video "research/character-corpus/local/video-pipeline/bilibili-BV1kqoaBiEVZ-p02/media/source.mp4" `
  -Device gpu
```

下载脚本要求目标分 P 已登记在 `source_parts.jsonl`，低于 4GiB 可用空间时拒绝开始，已有
`source.mp4` 时幂等返回。它使用隔离的 `uvx yt-dlp` 和 `imageio-ffmpeg`，不修改项目依赖。

`-Device gpu` 使用官方 CUDA 11.8 Windows wheel，并把推理设备固定为 `gpu:0`；默认仍为
`cpu`，因此没有 NVIDIA GPU 的机器和既有 P1 流程保持兼容。CPU/GPU 可以复用同一 OCR
checkpoint，设备信息只记入 manifest，不改变输入配置哈希。

首次运行会在忽略目录中安装独立 Python 3.12，并通过 uv 缓存 FFmpeg、PaddleOCR、PaddlePaddle 和 OpenCV；不会修改项目 `pyproject.toml` 或 `.venv`。阶段文件存在时会从已有规范化视频、候选帧或 OCR checkpoint 继续。

也可以输入普通视频：

```powershell
& research/character-corpus/tools/video_pipeline/run.ps1 `
  -Command run `
  -PartId local-example-p01 `
  -Video "D:\path\episode.mp4"
```

## 本地产物

| 文件 | 内容 |
| --- | --- |
| `manifest.json` | 输入、Preset、媒体信息、阶段状态和配置哈希 |
| `media/source.mp4` | 从 B 站分轨缓存规范化得到的本地视频 |
| `candidates.jsonl` | 字幕变化检测选择的候选帧及时间范围 |
| `ocr.checkpoint.jsonl` | 可恢复的逐候选 OCR checkpoint |
| `ocr.raw.jsonl` | 过滤后的 OCR 样本 |
| `utterances.jsonl` | 合并后的台词、说话者状态和审核状态 |
| `scenes.draft.jsonl` | 依据对白间隔形成的场景草稿 |
| `review-queue.jsonl` | 未确认说话者、低置信度和短句 |
| `report.json` | 本次处理统计 |
| `review-full-frames/` | 按台词时间点提取的全画面审核证据 |
| `review-decisions.jsonl` | 逐条人工或 Agent 审核决定，不覆盖原始 OCR |
| `reviewed-transcript.jsonl` | 只包含审核通过并修订后的可读稿 |
| `review-report.html` | 全画面、原 OCR、修订稿、说话者和结论的浏览器报告 |
| `review-sheets/` | 每页九帧的视觉审核联络表，便于快速定位说话人和界面误识别 |
| `low-cost-review/<packet-id>/request.json` | 最多 40 条台词、20 张风险图的轻量模型审核包 |
| `low-cost-review/<packet-id>/response.json` | 轻量模型严格响应，不直接进入正式审核稿 |
| `low-cost-review/<packet-id>/auto-review-candidates.jsonl` | 通过确定性安全门的候选 |
| `low-cost-review/<packet-id>/escalation-queue.jsonl` | 需要高能力模型或人工复核的疑难项 |

校验暂存包：

```powershell
& research/character-corpus/tools/video_pipeline/run.ps1 `
  -Command validate `
  -Output "research/character-corpus/local/video-pipeline/bilibili-BV1kqoaBiEVZ-p01"
```

当前工具没有“直接写数据库”命令。后续导出必须先完成台词、说话者和场景审核，并由校验结果给出 `export_ready=true`；在此之前所有结果都是可丢弃、可重跑的研究草稿。

生成可视审核报告和校验审核覆盖率：

```powershell
& research/character-corpus/tools/video_pipeline/run.ps1 `
  -Command review-report `
  -Output "research/character-corpus/local/video-pipeline/bilibili-BV1kqoaBiEVZ-p01"

& research/character-corpus/tools/video_pipeline/run.ps1 `
  -Command review-validate `
  -Output "research/character-corpus/local/video-pipeline/bilibili-BV1kqoaBiEVZ-p01"
```

`review-report` 是静态 HTML，不需要启动前后端服务。审核决定必须覆盖全部源候选，且审核通过的 ID 必须与 `reviewed-transcript.jsonl` 一致，`review-validate` 才会成功。审核完成仍不等于已经生成正式场景、人物证据或 Character Definition。

## 低成本模型审核

完整分 P 先自动规划审核包：

```powershell
& research/character-corpus/tools/video_pipeline/run.ps1 `
  -Command low-cost-plan `
  -Output research/character-corpus/local/video-pipeline/bilibili-BV1kqoaBiEVZ-p03
```

计划会在 `low-cost-review/plan.json` 中列出全部连续包及其文本/图片预算。也可以继续用 `low-cost-pack` 单独生成一个时间范围，适合校准或重跑。

先为一个连续小段生成紧凑审核包：

```powershell
& research/character-corpus/tools/video_pipeline/run.ps1 `
  -Command low-cost-pack `
  -Output research/character-corpus/local/video-pipeline/bilibili-BV1kqoaBiEVZ-p02 `
  -StartMs 0 `
  -EndMs 230000
```

轻量模型只读取生成目录中的 `instructions.md`、`request.json` 及 request 明确列出的风险图片，并把严格响应保存为 `response.json`。随后运行：

```powershell
& research/character-corpus/tools/video_pipeline/run.ps1 `
  -Command low-cost-validate `
  -Packet "<packet-dir>/request.json" `
  -Response "<packet-dir>/response.json"
```

校准 P1/P2 时可以额外传入人工金标准运行 `low-cost-benchmark`。新分 P 不存在金标准时不得伪造 benchmark；直接审核自动候选和升级队列。低成本输出不会覆盖 `review-decisions.jsonl` 或 `reviewed-transcript.jsonl`，完整安全规则见 [设计文档](../../../../docs/design/character/low-cost-video-review.md)。

所有包完成，并对第二轮仍未解决的条目生成高审 JSON 后，使用确定性合并命令：

```powershell
& research/character-corpus/tools/video_pipeline/run.ps1 `
  -Command low-cost-finalize `
  -Output research/character-corpus/local/video-pipeline/bilibili-BV1kqoaBiEVZ-p03 `
  -HighReview path/to/high-review-a.json,path/to/high-review-b.json
```

合并器要求自动路径与高审路径共同完整覆盖候选，拒绝缺失、重复和越界 ID；成功后才写正式审核文件，再运行 `review-validate` 和 `promote-video`。

大量候选可先生成联络表：

```powershell
.\research\character-corpus\tools\video_pipeline\run.ps1 `
  -Command review-sheets `
  -Output research\character-corpus\local\video-pipeline\bilibili-BV1kqoaBiEVZ-p02
```
