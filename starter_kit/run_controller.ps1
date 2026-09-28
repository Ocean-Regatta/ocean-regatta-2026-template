# PowerShell interactive student controller runner
$ErrorActionPreference = "Stop"

# Look for running simulation container
$container = docker ps -q -f "name=ocean-regatta-sim"
if (-not $container) {
    # Check by image name fallback
    $container = docker ps -q -f "ancestor=ocean-regatta-student-local:2026" | Select-Object -First 1
}

if (-not $container) {
    Write-Host "[Error] Simulation container 'ocean-regatta-sim' is not currently running." -ForegroundColor Red
    Write-Host "`nPlease start the Gazebo simulation first in another terminal:" -ForegroundColor Yellow
    Write-Host "  .\starter_kit\run_docker.ps1 -ServerOnly" -ForegroundColor Cyan
    exit 1
}

Write-Host "=== Attaching interactive Student Controller to Gazebo Simulation ===" -ForegroundColor Cyan
Write-Host "Code changes in starter_kit\student_controller.py apply immediately on each run." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the controller without stopping Gazebo.`n" -ForegroundColor Gray

$interactive = [System.Environment]::UserInteractive -and -not [Console]::IsInputRedirected
$ttyFlag = if ($interactive) { "-it" } else { "-i" }

docker exec $ttyFlag $container python3 /workspace/starter_kit/student_controller.py
