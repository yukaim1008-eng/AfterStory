param(
    [ValidateSet("start", "stop", "restart", "status", "logs", "setup", "help")]
    [string]$Command = "start",
    [switch]$All,
    [switch]$NoOpen
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$RuntimeRoot = Join-Path $ProjectRoot ".local-run"
$BackendPidFile = Join-Path $RuntimeRoot "backend.pid.json"
$FrontendPidFile = Join-Path $RuntimeRoot "frontend.pid.json"
$BackendLog = Join-Path $RuntimeRoot "backend.log"
$BackendErrorLog = Join-Path $RuntimeRoot "backend-error.log"
$FrontendLog = Join-Path $RuntimeRoot "frontend.log"
$FrontendErrorLog = Join-Path $RuntimeRoot "frontend-error.log"
$BackendUrl = "http://127.0.0.1:8000/api/health"
$FrontendUrl = "http://127.0.0.1:5173"

function Write-Info([string]$Message) {
    Write-Host "[AfterStory] $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[AfterStory] $Message" -ForegroundColor Green
}

function Ensure-Command([string]$Name) {
    $resolved = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $resolved) {
        throw "找不到 $Name。请先安装依赖，或运行 '.\afterstory setup' 查看具体缺项。"
    }
    return $resolved.Source
}

function Invoke-Checked(
    [string]$Executable,
    [string[]]$CommandArgs,
    [string]$WorkingDirectory = $ProjectRoot
) {
    Push-Location $WorkingDirectory
    try {
        & $Executable @CommandArgs
        if ($LASTEXITCODE -ne 0) {
            throw "命令执行失败（exit $LASTEXITCODE）：$Executable $($CommandArgs -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

function Test-Url([string]$Url, [string]$Contains = "") {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
        if ($response.StatusCode -ne 200) { return $false }
        return -not $Contains -or $response.Content.Contains($Contains)
    }
    catch {
        return $false
    }
}

function Test-Port([int]$Port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        return $task.Wait(500) -and $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Wait-Url(
    [string]$Url,
    [string]$Name,
    [int]$TimeoutSeconds = 30,
    [string]$Contains = ""
) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Url $Url $Contains) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "$Name 未能在 $TimeoutSeconds 秒内就绪。请运行 '.\afterstory logs' 查看日志。"
}

function Save-ProcessRecord(
    [System.Diagnostics.Process]$Process,
    [string]$Service,
    [string]$Path
) {
    @{
        service = $Service
        pid = $Process.Id
        started_at = $Process.StartTime.ToUniversalTime().ToString("o")
        project_root = $ProjectRoot
    } | ConvertTo-Json | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Get-OwnedProcess([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        $record = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
        if ($record.project_root -ne $ProjectRoot) { return $null }
        $process = Get-Process -Id ([int]$record.pid) -ErrorAction SilentlyContinue
        if (-not $process) { return $null }
        $recorded = [DateTime]::Parse([string]$record.started_at).ToUniversalTime()
        $actual = $process.StartTime.ToUniversalTime()
        if ([Math]::Abs(($actual - $recorded).TotalSeconds) -gt 2) { return $null }
        return $process
    }
    catch {
        return $null
    }
}

function Start-ManagedProcess(
    [string]$Service,
    [string]$Executable,
    [string[]]$CommandArgs,
    [string]$WorkingDirectory,
    [string]$PidFile,
    [string]$OutputLog,
    [string]$ErrorLog
) {
    New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
    Set-Content -LiteralPath $OutputLog -Value "" -Encoding UTF8
    Set-Content -LiteralPath $ErrorLog -Value "" -Encoding UTF8
    $process = Start-Process `
        -FilePath $Executable `
        -ArgumentList $CommandArgs `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $OutputLog `
        -RedirectStandardError $ErrorLog `
        -PassThru
    Save-ProcessRecord $process $Service $PidFile
    return $process
}

function Stop-ManagedProcess([string]$Name, [string]$PidFile) {
    $process = Get-OwnedProcess $PidFile
    if (-not $process) {
        if (Test-Path -LiteralPath $PidFile) {
            Remove-Item -LiteralPath $PidFile -Force
        }
        Write-Info "$Name 不是由启动器运行，跳过停止。"
        return
    }
    Write-Info "正在停止 $Name（PID $($process.Id)）..."
    & taskkill.exe /PID $process.Id /T /F | Out-Null
    if ($LASTEXITCODE -ne 0 -and (Get-Process -Id $process.Id -ErrorAction SilentlyContinue)) {
        throw "无法停止 $Name（PID $($process.Id)）。"
    }
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Write-Ok "$Name 已停止。"
}

function Start-Database {
    $docker = Ensure-Command "docker"
    Write-Info "正在检查 PostgreSQL..."
    Invoke-Checked $docker @("compose", "up", "-d", "--wait", "postgres")
    Write-Ok "PostgreSQL 已就绪。"
}

function Apply-Migrations {
    $uv = Ensure-Command "uv"
    Write-Info "正在检查数据库版本..."
    Invoke-Checked $uv @("run", "alembic", "upgrade", "head")
    Write-Ok "数据库 migration 已到 head。"
}

function Start-Backend {
    if (Test-Url $BackendUrl) {
        if (Get-OwnedProcess $BackendPidFile) {
            Write-Ok "后端已经由启动器运行。"
        }
        else {
            Write-Info "检测到手动启动的 AfterStory 后端，将直接复用。"
        }
        return $false
    }
    if (Test-Port 8000) {
        throw "端口 8000 已被其他程序占用，且不是可识别的 AfterStory 后端。"
    }
    $uv = Ensure-Command "uv"
    Write-Info "正在启动后端..."
    Start-ManagedProcess `
        "后端" `
        $uv `
        @("run", "python", "-m", "uvicorn", "afterstory.api:create_app", "--factory", "--host", "127.0.0.1", "--port", "8000") `
        $ProjectRoot `
        $BackendPidFile `
        $BackendLog `
        $BackendErrorLog | Out-Null
    Wait-Url $BackendUrl "后端"
    Write-Ok "后端已启动：http://127.0.0.1:8000"
    return $true
}

function Start-Frontend {
    if (Test-Url $FrontendUrl "AfterStory") {
        if (Get-OwnedProcess $FrontendPidFile) {
            Write-Ok "前端已经由启动器运行。"
        }
        else {
            Write-Info "检测到手动启动的 AfterStory 前端，将直接复用。"
        }
        return
    }
    if (Test-Port 5173) {
        throw "端口 5173 已被其他程序占用，且不是可识别的 AfterStory 前端。"
    }
    $npmCommand = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
    if (-not $npmCommand) { $npmCommand = Get-Command "npm" -ErrorAction SilentlyContinue }
    if (-not $npmCommand) { throw "找不到 npm。请先安装 Node.js。" }
    Write-Info "正在启动前端..."
    Start-ManagedProcess `
        "前端" `
        $npmCommand.Source `
        @("run", "dev") `
        $FrontendRoot `
        $FrontendPidFile `
        $FrontendLog `
        $FrontendErrorLog | Out-Null
    Wait-Url $FrontendUrl "前端" 30 "AfterStory"
    Write-Ok "前端已启动：$FrontendUrl"
}

function Start-AfterStory {
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".env"))) {
        throw "缺少 .env。请先运行 '.\afterstory setup'。"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules"))) {
        throw "前端依赖尚未安装。请先运行 '.\afterstory setup'。"
    }
    Start-Database
    Apply-Migrations
    $backendStarted = Start-Backend
    try {
        Start-Frontend
    }
    catch {
        if ($backendStarted) {
            Stop-ManagedProcess "后端" $BackendPidFile
        }
        throw
    }
    Write-Ok "AfterStory 已就绪。"
    if (-not $NoOpen) {
        Start-Process $FrontendUrl
    }
}

function Stop-AfterStory {
    Stop-ManagedProcess "前端" $FrontendPidFile
    Stop-ManagedProcess "后端" $BackendPidFile
    if ($All) {
        $docker = Ensure-Command "docker"
        Write-Info "正在停止 PostgreSQL（数据卷会保留）..."
        Invoke-Checked $docker @("compose", "stop", "postgres")
        Write-Ok "PostgreSQL 已停止，持久化数据未删除。"
    }
}

function Show-Status {
    $backendOwned = Get-OwnedProcess $BackendPidFile
    $frontendOwned = Get-OwnedProcess $FrontendPidFile
    $backendReady = Test-Url $BackendUrl
    $frontendReady = Test-Url $FrontendUrl "AfterStory"

    Write-Host "AfterStory 本地状态"
    Write-Host "  PostgreSQL : " -NoNewline
    try {
        $docker = Ensure-Command "docker"
        Push-Location $ProjectRoot
        try {
            $database = (& $docker compose ps --status running --services postgres 2>$null)
        }
        finally {
            Pop-Location
        }
        Write-Host $(if ($database -contains "postgres") { "运行中" } else { "未运行" })
    }
    catch {
        Write-Host "无法检查"
    }
    Write-Host "  后端 8000 : $(if ($backendReady) { if ($backendOwned) { "运行中（启动器管理）" } else { "运行中（手动/外部）" } } else { "未运行" })"
    Write-Host "  前端 5173 : $(if ($frontendReady) { if ($frontendOwned) { "运行中（启动器管理）" } else { "运行中（手动/外部）" } } else { "未运行" })"
}

function Show-Logs {
    Write-Host "日志目录：$RuntimeRoot"
    foreach ($item in @(
        @{ Name = "后端"; Path = $BackendLog },
        @{ Name = "后端错误"; Path = $BackendErrorLog },
        @{ Name = "前端"; Path = $FrontendLog },
        @{ Name = "前端错误"; Path = $FrontendErrorLog }
    )) {
        Write-Host "`n--- $($item.Name)：$($item.Path) ---"
        if (Test-Path -LiteralPath $item.Path) {
            Get-Content -LiteralPath $item.Path -Tail 30
        }
        else {
            Write-Host "暂无日志"
        }
    }
}

function Setup-AfterStory {
    $uv = Ensure-Command "uv"
    $npmCommand = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
    if (-not $npmCommand) { $npmCommand = Get-Command "npm" -ErrorAction SilentlyContinue }
    if (-not $npmCommand) { throw "找不到 npm。请先安装 Node.js。" }
    Ensure-Command "docker" | Out-Null

    $envPath = Join-Path $ProjectRoot ".env"
    if (-not (Test-Path -LiteralPath $envPath)) {
        Copy-Item -LiteralPath (Join-Path $ProjectRoot ".env.example") -Destination $envPath
        Write-Info "已从 .env.example 创建 .env；启动真实聊天前请填写模型密钥。"
    }
    else {
        Write-Info ".env 已存在，不会覆盖。"
    }

    Write-Info "正在安装后端依赖..."
    Invoke-Checked $uv @("sync", "--locked")
    Write-Info "正在安装前端依赖..."
    Invoke-Checked $npmCommand.Source @("ci") $FrontendRoot
    Start-Database
    Apply-Migrations
    Write-Info "正在导入幂等基础数据与正式角色版本..."
    Invoke-Checked $uv @("run", "python", "-m", "afterstory.seed")
    Write-Ok "首次设置完成。现在可以运行 '.\afterstory start'。"
}

function Show-Help {
    Write-Host @"
AfterStory 本地开发启动器

  .\afterstory start [-NoOpen]  启动数据库、后端和前端
  .\afterstory stop             停止启动器创建的前后端
  .\afterstory stop -All        同时停止 PostgreSQL，保留数据卷
  .\afterstory restart          重启前后端
  .\afterstory status           查看运行状态
  .\afterstory logs             查看最近日志
  .\afterstory setup            首次安装依赖、迁移并导入基础数据
  .\afterstory help             显示本帮助
"@
}

try {
    switch ($Command) {
        "start" { Start-AfterStory }
        "stop" { Stop-AfterStory }
        "restart" {
            Stop-AfterStory
            Start-AfterStory
        }
        "status" { Show-Status }
        "logs" { Show-Logs }
        "setup" { Setup-AfterStory }
        "help" { Show-Help }
    }
}
catch {
    Write-Host "[AfterStory] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
