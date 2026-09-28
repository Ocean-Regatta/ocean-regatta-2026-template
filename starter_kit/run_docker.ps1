param(
    [switch]$ServerOnly,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

# PowerShell launcher for Windows
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot = Split-Path -Parent $ScriptDir

Write-Host "=== [1/3] Building local Gazebo Jetty Docker image ===" -ForegroundColor Cyan
docker build `
    -f "$ScriptDir\Dockerfile.local" `
    -t ocean-regatta-student-local:2026 `
    "$ScriptDir"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker build failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "=== [2/3] Preparing local replay directory ===" -ForegroundColor Cyan
$ReplayDir = Join-Path $RepoRoot "local_output\replay"
if (-not (Test-Path $ReplayDir)) {
    New-Item -ItemType Directory -Path $ReplayDir -Force | Out-Null
}

Write-Host "=== [3/3] Executing local simulation sandbox ===" -ForegroundColor Cyan
# Allocate TTY only when attached to an interactive console
$interactive = [System.Environment]::UserInteractive -and -not [Console]::IsInputRedirected
$ttyFlag = if ($interactive) { "-it" } else { "-i" }

$simArgs = @()
if ($ServerOnly) { $simArgs += "--server-only" }
if ($ExtraArgs) { $simArgs += $ExtraArgs }

docker rm -f ocean-regatta-sim 2>$null | Out-Null

docker run --rm $ttyFlag `
    --name ocean-regatta-sim `
    -p 9002:9002 `
    -p 8080:8080 `
    -v "${RepoRoot}:/workspace" `
    -w /workspace `
    ocean-regatta-student-local:2026 `
    bash /workspace/starter_kit/entrypoint_sim.sh $simArgs

Write-Host "Simulation complete. Replay available: gz sim --playback ./local_output/replay" -ForegroundColor Green
