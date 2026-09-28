@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..") do set "REPO_ROOT=%%~fI"

echo === [1/3] Building local Gazebo Jetty Docker image ===
docker build -f "%SCRIPT_DIR%\Dockerfile.local" -t ocean-regatta-student-local:2026 "%SCRIPT_DIR%"
if errorlevel 1 (
    echo Error: Docker build failed.
    exit /b %errorlevel%
)

echo === [2/3] Preparing local replay directory ===
if not exist "%REPO_ROOT%\local_output\replay" (
    mkdir "%REPO_ROOT%\local_output\replay"
)

echo === [3/3] Executing local simulation sandbox ===
docker rm -f ocean-regatta-sim >nul 2>&1
docker run --rm -i --name ocean-regatta-sim -p 9002:9002 -p 8080:8080 -v "%REPO_ROOT%:/workspace" -w /workspace ocean-regatta-student-local:2026 bash /workspace/starter_kit/entrypoint_sim.sh %*

echo Simulation complete. Replay available: gz sim --playback ./local_output/replay
