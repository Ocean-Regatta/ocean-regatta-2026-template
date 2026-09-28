#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== [1/3] Configuring Gazebo environment ==="
export GZ_SIM_RESOURCE_PATH="${REPO_ROOT}/models:${REPO_ROOT}/worlds:${GZ_SIM_RESOURCE_PATH}"

MODE="gui"
for arg in "$@"; do
    case "$arg" in
        --web|--headless)
            MODE="headless"
            ;;
        --gui)
            MODE="gui"
            ;;
    esac
done

cleanup() {
    echo "Stopping simulation..."
    if [ -n "${STUDENT_PID}" ]; then
        kill -TERM "${STUDENT_PID}" 2>/dev/null || true
    fi
    if [ -n "${GZ_PID}" ]; then
        kill -TERM "${GZ_PID}" 2>/dev/null || true
    fi
    if [ -n "${HTTP_PID}" ]; then
        kill "${HTTP_PID}" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Start local web viewer HTTP server if webviewer directory exists
if [ -d "${REPO_ROOT}/starter_kit/webviewer" ]; then
    python3 -m http.server 8080 --directory "${REPO_ROOT}/starter_kit/webviewer" >/dev/null 2>&1 &
    HTTP_PID=$!
fi

if [ "$MODE" = "headless" ]; then
    echo "=== [2/3] Starting Gazebo Sim (Headless Server with Native WebSocket) ==="
    gz sim -s -r -v 2 "${REPO_ROOT}/worlds/practice_world.sdf" &
    GZ_PID=$!
else
    echo "=== [2/3] Starting Gazebo Sim (3D Practice World GUI + Native WebSocket) ==="
    gz sim -v 3 -r "${REPO_ROOT}/worlds/practice_world.sdf" &
    GZ_PID=$!
fi

echo "Waiting for initialization (4s)..."
sleep 4

echo "================================================================================"
echo " 🌐 Native Gazebo WebSocket Server: ws://localhost:9002"
echo " 🌐 Local 3D WebViewer:             http://localhost:8080"
echo " 🌐 Hosted Official Viewer:        https://app.gazebosim.org/visualization"
echo "================================================================================"

echo "=== [3/3] Launching student controller ==="
python3 "${REPO_ROOT}/starter_kit/student_controller.py" &
STUDENT_PID=$!

wait ${STUDENT_PID} || true
wait ${GZ_PID} || true

