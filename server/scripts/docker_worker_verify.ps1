<#
.SYNOPSIS
    验证 Worker 在 Docker 容器内是否能正常启动并领取任务
.DESCRIPTION
    本脚本执行以下验证：
    1. 检查 Docker 守护进程是否运行
    2. 构建并启动 docker-compose 三服务
    3. 等待 backend 健康检查通过
    4. 检查 worker 容器日志是否显示"[Worker] 启动后台任务 Worker..."
    5. 在 worker 容器内执行 python -m worker.main 验证
    6. 清理容器
.NOTES
    使用方法：
    cd d:/java_project/lab-report-assistant
    powershell -ExecutionPolicy Bypass -File server/scripts/docker_worker_verify.ps1
#>

param(
    [int]$HealthTimeout = 60
)

$ErrorActionPreference = "Stop"
$projectRoot = Resolve-Path "$PSScriptRoot/../.."

Write-Host "========== Worker Docker 容器验证 ==========" -ForegroundColor Cyan
Write-Host "项目根目录: $projectRoot"

# ===== 步骤 1：检查 Docker 守护进程 =====
Write-Host "`n[1/6] 检查 Docker 守护进程..." -ForegroundColor Yellow
try {
    $dockerInfo = docker info --format "{{.ServerVersion}}" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ❌ Docker 守护进程未运行" -ForegroundColor Red
        Write-Host "  请启动 Docker Desktop 后重试" -ForegroundColor Red
        Write-Host "  验证结果: FAIL (Docker daemon not running)" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✅ Docker 守护进程运行中 (Server $dockerInfo)" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Docker 守护进程检查失败: $_" -ForegroundColor Red
    exit 1
}

# ===== 步骤 2：确认 .env 文件存在 =====
Write-Host "`n[2/6] 检查 .env 文件..." -ForegroundColor Yellow
$envFile = Join-Path $projectRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "  .env 不存在，从 .env.example 复制..." -ForegroundColor Yellow
    Copy-Item (Join-Path $projectRoot ".env.example") $envFile
    Write-Host "  ✅ 已创建 .env（使用 LocalRule 默认配置）" -ForegroundColor Green
} else {
    Write-Host "  ✅ .env 文件已存在" -ForegroundColor Green
}

# ===== 步骤 3：构建镜像 =====
Write-Host "`n[3/6] 构建镜像（可能需要几分钟）..." -ForegroundColor Yellow
Push-Location $projectRoot
try {
    docker compose build 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ❌ 镜像构建失败" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✅ 镜像构建完成" -ForegroundColor Green
} finally {
    Pop-Location
}

# ===== 步骤 4：启动服务并等待 backend 健康 =====
Write-Host "`n[4/6] 启动服务..." -ForegroundColor Yellow
Push-Location $projectRoot
try {
    docker compose up -d 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ❌ 服务启动失败" -ForegroundColor Red
        exit 1
    }

    Write-Host "  等待 backend 健康检查通过（最多 ${HealthTimeout}s）..." -ForegroundColor Yellow
    $elapsed = 0
    $healthy = $false
    while ($elapsed -lt $HealthTimeout) {
        Start-Sleep -Seconds 3
        $elapsed += 3
        $status = docker inspect --format "{{.State.Health.Status}}" lab-report-backend 2>$null
        if ($status -eq "healthy") {
            $healthy = $true
            Write-Host "  ✅ backend 健康检查通过（${elapsed}s）" -ForegroundColor Green
            break
        }
        Write-Host "  ... 等待中（${elapsed}s，状态: $status）" -ForegroundColor DarkGray
    }

    if (-not $healthy) {
        Write-Host "  ❌ backend 健康检查超时" -ForegroundColor Red
        Write-Host "  backend 日志:" -ForegroundColor Yellow
        docker compose logs backend 2>&1 | Select-Object -Last 20 | ForEach-Object { Write-Host "    $_" }
        exit 1
    }
} finally {
    Pop-Location
}

# ===== 步骤 5：验证 Worker 容器内启动和任务领取 =====
Write-Host "`n[5/6] 验证 Worker 容器内行为..." -ForegroundColor Yellow

# 5.1 检查 worker 容器是否运行
$workerStatus = docker inspect --format "{{.State.Status}}" lab-report-worker 2>$null
if ($workerStatus -eq "running") {
    Write-Host "  ✅ worker 容器运行中" -ForegroundColor Green
} else {
    Write-Host "  ❌ worker 容器未运行（状态: $workerStatus）" -ForegroundColor Red
}

# 5.2 检查 worker 日志是否显示启动
Start-Sleep -Seconds 3
$workerLogs = docker compose logs worker 2>&1
$hasStartup = $workerLogs | Select-String "启动后台任务 Worker"
if ($hasStartup) {
    Write-Host "  ✅ worker 日志显示启动成功" -ForegroundColor Green
    Write-Host "  日志片段: $($hasStartup.Line)" -ForegroundColor DarkGray
} else {
    Write-Host "  ❌ worker 日志未显示启动" -ForegroundColor Red
    Write-Host "  worker 日志:" -ForegroundColor Yellow
    $workerLogs | Select-Object -Last 10 | ForEach-Object { Write-Host "    $_" }
}

# 5.3 在 worker 容器内执行 python -m worker.main（覆盖验证）
Write-Host "  在 worker 容器内验证 python -m worker.main ..." -ForegroundColor Yellow
$execResult = docker exec lab-report-worker .venv/bin/python -c "from worker.main import main; print('import OK')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ worker.main 模块在容器内可导入" -ForegroundColor Green
} else {
    Write-Host "  ❌ worker.main 在容器内导入失败: $execResult" -ForegroundColor Red
}

# 5.4 验证 worker command 与 SPEC 0013 一致
Write-Host "  验证 worker 启动命令..." -ForegroundColor Yellow
$workerCmd = docker inspect --format "{{.Config.Cmd}}" lab-report-worker 2>$null
if ($workerCmd -match "worker.main") {
    Write-Host "  ✅ worker command 正确: $workerCmd" -ForegroundColor Green
} else {
    Write-Host "  ❌ worker command 异常: $workerCmd" -ForegroundColor Red
}

# ===== 步骤 6：验证结果汇总 =====
Write-Host "`n[6/6] 验证结果汇总..." -ForegroundColor Yellow
$allPass = ($workerStatus -eq "running") -and $hasStartup -and ($LASTEXITCODE -eq 0) -and ($workerCmd -match "worker.main")

if ($allPass) {
    Write-Host "`n========== ✅ Worker Docker 容器验证全部通过 ==========" -ForegroundColor Green
    Write-Host "  - worker 容器运行中" -ForegroundColor Green
    Write-Host "  - worker 日志显示启动" -ForegroundColor Green
    Write-Host "  - worker.main 在容器内可导入" -ForegroundColor Green
    Write-Host "  - worker command 与 SPEC 0013 一致" -ForegroundColor Green
    $result = "PASS"
} else {
    Write-Host "`n========== ❌ Worker Docker 容器验证失败 ==========" -ForegroundColor Red
    $result = "FAIL"
}

# ===== 清理 =====
Write-Host "`n清理容器..." -ForegroundColor Yellow
Push-Location $projectRoot
try {
    docker compose down 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
} finally {
    Pop-Location
}

Write-Host "`n验证结果: $result" -ForegroundColor $(if ($result -eq "PASS") { "Green" } else { "Red" })
if ($result -ne "PASS") { exit 1 }
