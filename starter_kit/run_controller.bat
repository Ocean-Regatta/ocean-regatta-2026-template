@echo off
setlocal enabledelayedexpansion

REM Look for running simulation container
set CONTAINER=
for /f "tokens=*" %%i in ('docker ps -q -f "name=ocean-regatta-sim"') do set CONTAINER=%%i
if "%CONTAINER%"=="" (
    for /f "tokens=*" %%i in ('docker ps -q -f "ancestor=ocean-regatta-student-local:2026"') do (
        set CONTAINER=%%i
        goto found
    )
)
:found

if "%CONTAINER%"=="" (
    echo [Error] Simulation container 'ocean-regatta-sim' is not currently running.
    echo Please start the Gazebo simulation first:
    echo   starter_kit\run_docker.bat --server-only
    exit /b 1
)

echo === Attaching interactive Student Controller to Gazebo Simulation ===
echo Code changes in starter_kit\student_controller.py apply immediately on each run.
echo Press Ctrl+C to stop the controller without stopping Gazebo.
echo.

docker exec -it %CONTAINER% python3 /workspace/starter_kit/student_controller.py
