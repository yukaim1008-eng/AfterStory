param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 999)]
    [int]$PartNumber,
    [string]$Bvid = "BV1kqoaBiEVZ"
)

$ErrorActionPreference = "Stop"
$ToolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CorpusRoot = (Resolve-Path (Join-Path $ToolDir "..\..")).Path
$PartId = "bilibili-$Bvid-p$($PartNumber.ToString('00'))"
$OutputDir = Join-Path $CorpusRoot "local\video-pipeline\$PartId"
$MediaDir = Join-Path $OutputDir "media"
$Target = Join-Path $MediaDir "source.mp4"

$Part = Get-Content -LiteralPath (Join-Path $CorpusRoot "source_parts.jsonl") |
    ForEach-Object { $_ | ConvertFrom-Json } |
    Where-Object { $_.part_id -eq $PartId }
if (-not $Part) {
    throw "Part is not registered in source_parts.jsonl: $PartId"
}
if (Test-Path -LiteralPath $Target) {
    Write-Output ($Part | Select-Object part_id, title, duration_ms)
    Write-Output "Media already exists: $Target"
    exit 0
}

$Drive = Get-PSDrive -Name ([System.IO.Path]::GetPathRoot($CorpusRoot).TrimEnd(':\'))
if ($Drive.Free -lt 4GB) {
    throw "At least 4 GiB free space is required before downloading a 1080p part."
}

New-Item -ItemType Directory -Force -Path $MediaDir | Out-Null
$Ffmpeg = (& uv run --no-project --with imageio-ffmpeg python -X utf8 -c `
    "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" | Select-Object -Last 1).Trim()
if (-not (Test-Path -LiteralPath $Ffmpeg)) {
    throw "FFmpeg bootstrap failed: $Ffmpeg"
}

$Url = "https://www.bilibili.com/video/$Bvid/?p=$PartNumber"
$OutputTemplate = Join-Path $MediaDir "source.%(ext)s"
& uvx --from yt-dlp yt-dlp `
    --no-playlist `
    --continue `
    --no-mtime `
    --format "30080+30280/30080+30232/bv*[height<=1080]+ba/b[height<=1080]" `
    --merge-output-format mp4 `
    --ffmpeg-location $Ffmpeg `
    --output $OutputTemplate `
    $Url
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
if (-not (Test-Path -LiteralPath $Target)) {
    throw "Download completed without the expected target: $Target"
}

Write-Output ($Part | Select-Object part_id, title, duration_ms)
Get-Item -LiteralPath $Target | Select-Object FullName, Length, LastWriteTime
