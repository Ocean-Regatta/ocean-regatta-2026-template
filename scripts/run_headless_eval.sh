#!/usr/bin/env bash
set -e

# ==============================================================================
# Ocean Regatta 2026 — Headless Simulation & Evaluation Launcher
#
# Runs Gazebo Jetty headless (-s) with the automated scoring plugin, launches
# the student controller, monitors execution, and captures scoring_result.json
# and the 3D replay playback logs (state.tlog).
# ==============================================================================

WORLD_FILE="${1:-/workspace/worlds/evaluation_world.sdf}"
OUTPUT_DIR="${2:-/workspace/output}"
TIMEOUT_SECONDS="${3:-315}"

echo "===================================================================="
echo " 🌊 Ocean Regatta 2026 — Headless Evaluation Runner"
echo "===================================================================="
echo "World:           ${WORLD_FILE}"
echo "Output Dir:      ${OUTPUT_DIR}"
echo "Max Timeout:     ${TIMEOUT_SECONDS}s"
echo "===================================================================="

# Clean up any leftover artifacts from prior runs to ensure fresh data
rm -f /workspace/scoring_result.json "${OUTPUT_DIR}/scoring_result.json"
rm -rf "${OUTPUT_DIR}/replay" "${OUTPUT_DIR}/replay(1)"
mkdir -p "${OUTPUT_DIR}"
chmod -R 777 "${OUTPUT_DIR}" 2>/dev/null || true

# Gazebo plugin & resource paths
export GZ_SIM_RESOURCE_PATH="/workspace/models:/workspace/worlds:${GZ_SIM_RESOURCE_PATH}"
export GZ_SIM_SYSTEM_PLUGIN_PATH="/workspace/plugins/build:/workspace/build:${GZ_SIM_SYSTEM_PLUGIN_PATH}"
export GZ_GUI_PLUGIN_PATH="/workspace/plugins/build:/workspace/build:${GZ_GUI_PLUGIN_PATH}"
export REGATTA_EXIT_ON_FINISH=1
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

cleanup() {
    echo "[run_headless_eval] Cleaning up background processes..."
    if [ -n "${CONTROLLER_PID}" ]; then
        kill -TERM "${CONTROLLER_PID}" 2>/dev/null || true
    fi
    if [ -n "${GZ_PID}" ]; then
        kill -INT "${GZ_PID}" 2>/dev/null || true
        sleep 1
        kill -TERM "${GZ_PID}" 2>/dev/null || true
    fi
}
trap cleanup EXIT SIGINT SIGTERM

echo "=== [1/3] Starting Gazebo Headless Server with Recording ==="
# Notice: Do not pre-create ${OUTPUT_DIR}/replay so Gazebo creates it without appending '(1)'
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
        echo "::warning::Evaluation reached maximum safety timeout (${TIMEOUT_SECONDS}s). Forcing graceful shutdown..."
        # Send SIGINT first to let Gazebo and ScoringSystem finalize files and logs
        kill -INT "${GZ_PID}" 2>/dev/null || true
        sleep 3
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

# Normalize replay directory if Gazebo created replay(1)
if [ -d "${OUTPUT_DIR}/replay(1)" ]; then
    if [ ! -d "${OUTPUT_DIR}/replay" ] || [ ! -f "${OUTPUT_DIR}/replay/state.tlog" ]; then
        rm -rf "${OUTPUT_DIR}/replay"
        mv "${OUTPUT_DIR}/replay(1)" "${OUTPUT_DIR}/replay"
    fi
fi

if [ -f "${OUTPUT_DIR}/replay/state.tlog" ]; then
    REPLAY_SIZE=$(du -sh "${OUTPUT_DIR}/replay/state.tlog" 2>/dev/null | cut -f1 || echo "OK")
    echo "Gazebo 3D replay log successfully captured (${REPLAY_SIZE}) in ${OUTPUT_DIR}/replay"
else
    echo "::warning::Replay state.tlog not found in ${OUTPUT_DIR}/replay"
fi

# Locate generated scoring file (ScoringSystem outputs to /workspace, output, or current dir)
FOUND_SCORING=""
for candidate in \
    "${OUTPUT_DIR}/scoring_result.json" \
    "/workspace/scoring_result.json" \
    "scoring_result.json"; do
    if [ -f "${candidate}" ]; then
        FOUND_SCORING="${candidate}"
        break
    fi
done

if [ -n "${FOUND_SCORING}" ]; then
    echo "Found fresh scoring result at: ${FOUND_SCORING}"
    if [ "${FOUND_SCORING}" != "${OUTPUT_DIR}/scoring_result.json" ]; then
        cp "${FOUND_SCORING}" "${OUTPUT_DIR}/scoring_result.json"
    fi
    echo "Scoring output ready at ${OUTPUT_DIR}/scoring_result.json"
else
    echo "::warning::Scoring plugin did not write JSON (simulation stopped before finish/timeout). Generating fallback scorecard..."
    cat << EOF > "${OUTPUT_DIR}/scoring_result.json"
{
  "score": 2.0,
  "total_score": 2.0,
  "waypoint_score": 0.0,
  "max_score": 22.0,
  "sim_time": ${ELAPSED:-0.0},
  "reason": "TIMEOUT_OR_ABORTED",
  "success": false,
  "finish_line_crossed": false,
  "waypoints_cleared": 0,
  "total_waypoints": 11,
  "collision": false,
  "penalties": 0.0
}
EOF
    echo "Fallback scoring record written to ${OUTPUT_DIR}/scoring_result.json"
fi

# Ensure minimum floor score of 2.0 pts for any non-collision run
if [ -f "${OUTPUT_DIR}/scoring_result.json" ]; then
    python3 -c "
import json
try:
    with open('${OUTPUT_DIR}/scoring_result.json', 'r') as f:
        d = json.load(f)
    if not d.get('collision', False) and float(d.get('score', 0.0)) < 2.0:
        d['score'] = 2.0
        d['total_score'] = 2.0
        with open('${OUTPUT_DIR}/scoring_result.json', 'w') as f:
            json.dump(d, f, indent=2)
except Exception:
    pass
" 2>/dev/null || true
    cp "${OUTPUT_DIR}/scoring_result.json" "${OUTPUT_DIR}/result.json" 2>/dev/null || true
fi

# Make sure all output files can be read by runner and user
chmod -R 777 "${OUTPUT_DIR}" 2>/dev/null || true

echo "===================================================================="
echo " Headless evaluation finished successfully!"
echo "===================================================================="
