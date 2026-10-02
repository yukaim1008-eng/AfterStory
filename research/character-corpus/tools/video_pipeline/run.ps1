param(
    [ValidateSet("run", "validate", "assemble", "review-report", "review-validate")]
    [string]$Command = "run",
    [string]$PartId,
    [string]$Title = "",
    [string]$CacheDir,
    [string]$Video,
    [string]$Output,
    [string]$Preset,
    [string]$Catalog
)

$ErrorActionPreference = "Stop"
$ToolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CorpusRoot = (Resolve-Path (Join-Path $ToolDir "..\..")).Path
$RepoRoot = (Resolve-Path (Join-Path $CorpusRoot "..\..")).Path
$RuntimeRoot = Join-Path $CorpusRoot "local\video-pipeline\.runtime"
$PythonRoot = Join-Path $RuntimeRoot "python"

$Python = Get-ChildItem -LiteralPath $PythonRoot -Recurse -Filter python.exe -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "Lib\\venv" } |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $Python) {
    New-Item -ItemType Directory -Force -Path $PythonRoot | Out-Null
    & uv python install 3.12 --install-dir $PythonRoot --no-bin --no-registry
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $Python = Get-ChildItem -LiteralPath $PythonRoot -Recurse -Filter python.exe |
        Where-Object { $_.FullName -notmatch "Lib\\venv" } |
        Select-Object -First 1 -ExpandProperty FullName
}

$Ffmpeg = (& uv run --no-project --python $Python --with imageio-ffmpeg python -X utf8 -c `
    "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" | Select-Object -Last 1).Trim()
if (-not (Test-Path -LiteralPath $Ffmpeg)) {
    throw "FFmpeg bootstrap failed: $Ffmpeg"
}

$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = "True"
$env:PYTHONPATH = Split-Path -Parent $ToolDir
$PipelineArgs = @("-m", "video_pipeline.cli", $Command)
if ($PartId) { $PipelineArgs += @("--part-id", $PartId) }
if ($Title) { $PipelineArgs += @("--title", $Title) }
if ($CacheDir) { $PipelineArgs += @("--cache-dir", $CacheDir) }
if ($Video) { $PipelineArgs += @("--video", $Video) }
if ($Output) { $PipelineArgs += @("--output", $Output) }
if ($Preset) { $PipelineArgs += @("--preset", $Preset) }
if ($Catalog) { $PipelineArgs += @("--catalog", $Catalog) }
if ($Command -eq "run" -and $CacheDir) { $PipelineArgs += @("--ffmpeg", $Ffmpeg) }

Push-Location $RepoRoot
try {
    & uv run --no-project --python $Python `
        --with "paddleocr==3.7.0" `
        --with "paddlepaddle==3.3.1" `
        --with "opencv-python-headless==4.10.0.84" `
        python -X utf8 @PipelineArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
