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

校验暂存包：

```powershell
& research/character-corpus/tools/video_pipeline/run.ps1 `
  -Command validate `
  -Output "research/character-corpus/local/video-pipeline/bilibili-BV1kqoaBiEVZ-p01"
```

当前工具没有“直接写数据库”命令。后续导出必须先完成台词、说话者和场景审核，并由校验结果给出 `export_ready=true`；在此之前所有结果都是可丢弃、可重跑的研究草稿。
