#!/usr/bin/env bash
set -e

# ==============================================================================
# Ocean Regatta 2026 — Headless Simulation & Evaluation Launcher
#
# Runs Gazebo Jetty headless (-s) with the automated scoring plugin, launches
# the student controller, monitors execution, and captures scoring_result.json.
# ==============================================================================

WORLD_FILE="${1:-/workspace/worlds/evaluation_world.sdf}"
OUTPUT_DIR="${2:-/workspace/output}"
TIMEOUT_SECONDS="${3:-300}"

echo "===================================================================="
echo " 🌊 Ocean Regatta 2026 — Headless Evaluation Runner"
echo "===================================================================="
echo "World:           ${WORLD_FILE}"
echo "Output Dir:      ${OUTPUT_DIR}"
echo "Max Timeout:     ${TIMEOUT_SECONDS}s"
echo "===================================================================="

mkdir -p "${OUTPUT_DIR}/replay"
chmod -R 777 "${OUTPUT_DIR}" 2>/dev/null || true

# Gazebo plugin & resource paths
export GZ_SIM_RESOURCE_PATH="/workspace/models:/workspace/worlds:${GZ_SIM_RESOURCE_PATH}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="/workspace/plugins/build:/workspace/build:${GZ_SIM_SYSTEM_PLUGIN_PATH}"
export GZ_GUI_PLUGIN_PATH="/workspace/plugins/build:/workspace/build:${GZ_GUI_PLUGIN_PATH}"
export REGATTA_EXIT_ON_FINISH=1
export PYTHONUNBUFFERED=1

cleanup() {
    echo "[run_headless_eval] Cleaning up background processes..."
    if [ -n "${CONTROLLER_PID}" ]; then
        kill -TERM "${CONTROLLER_PID}" 2>/dev/null || true
    fi
    if [ -n "${GZ_PID}" ]; then
        kill -TERM "${GZ_PID}" 2>/dev/null || true
    fi
}
trap cleanup EXIT SIGINT SIGTERM

echo "=== [1/3] Starting Gazebo Headless Server ==="
gz sim -s -r -v 2 \
    --record \
    --record-path "${OUTPUT_DIR}/replay" \
    "${WORLD_FILE}" &
GZ_PID=$!

echo "Waiting for Gazebo simulation node to initialize (4s)..."
sleep 4

if ! kill -0 "${GZ_PID}" 2>/dev/null; then
    echo "::error::Gazebo failed to start. Check plugin builds and world SDF."
    exit 1
fi

echo "=== [2/3] Launching Student Controller ==="
if [ ! -f "/workspace/starter_kit/student_controller.py" ]; then
    echo "::error::student_controller.py not found at /workspace/starter_kit/student_controller.py"
    exit 1
fi

python3 /workspace/starter_kit/student_controller.py &
CONTROLLER_PID=$!

echo "=== [3/3] Monitoring simulation execution (max ${TIMEOUT_SECONDS}s) ==="
START_TIME=$(date +%s)
while kill -0 "${GZ_PID}" 2>/dev/null; do
    ELAPSED=$(( $(date +%s) - START_TIME ))
    if [ ${ELAPSED} -ge ${TIMEOUT_SECONDS} ]; then
        echo "::warning::Evaluation reached maximum timeout (${TIMEOUT_SECONDS}s). Forcing shutdown..."
        kill -INT "${GZ_PID}" 2>/dev/null || true
        sleep 2
        kill -TERM "${GZ_PID}" 2>/dev/null || true
        break
    fi
    sleep 2
done

# Wait for Gazebo process exit
wait "${GZ_PID}" 2>/dev/null || true

# Terminate controller if still running
if [ -n "${CONTROLLER_PID}" ] && kill -0 "${CONTROLLER_PID}" 2>/dev/null; then
    kill -TERM "${CONTROLLER_PID}" 2>/dev/null || true
fi

echo "Gazebo simulation terminated."

# Locate generated scoring file (ScoringSystem outputs to /workspace or current dir)
FOUND_SCORING=""
for candidate in \
    "/workspace/scoring_result.json" \
    "scoring_result.json" \
    "/output/result.json" \
    "${OUTPUT_DIR}/result.json" \
    "/output/scoring_result.json"; do
    if [ -f "${candidate}" ]; then
        FOUND_SCORING="${candidate}"
        break
    fi
done

if [ -n "${FOUND_SCORING}" ]; then
    echo "Found scoring result at: ${FOUND_SCORING}"
    cp "${FOUND_SCORING}" "${OUTPUT_DIR}/scoring_result.json"
    cp "${FOUND_SCORING}" "${OUTPUT_DIR}/result.json"
    echo "Scoring output normalized to ${OUTPUT_DIR}/scoring_result.json and ${OUTPUT_DIR}/result.json"
else
    echo "::error::Simulation finished but no scoring_result.json was found!"
    exit 1
fi

echo "===================================================================="
echo " Headless evaluation finished successfully!"
echo "===================================================================="

