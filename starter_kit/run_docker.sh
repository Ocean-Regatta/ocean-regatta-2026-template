#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== [1/3] Construction de l'image locale Gazebo Jetty ==="
docker build \
    -f "${SCRIPT_DIR}/Dockerfile.local" \
    -t ocean-regatta-student-local:2026 \
    "${SCRIPT_DIR}"

echo "=== [2/3] Préparation du dossier de replay local ==="
mkdir -p "${REPO_ROOT}/local_output/replay"
chmod -R 777 "${REPO_ROOT}/local_output"

echo "=== [3/3] Exécution de la simulation locale en sandbox ==="
docker run --rm -it \
    -v "${REPO_ROOT}:/workspace" \
    -w /workspace \
    ocean-regatta-student-local:2026 \
    bash -c '
        export DISPLAY=:99
        Xvfb :99 -screen 0 1024x768x24 &
        
        gz sim -s -r -v 2 \
            --headless-rendering \
            worlds/practice_world.sdf \
            --log-record \
            --log-record-path /workspace/local_output/replay &
        GZ_PID=$!
        
        sleep 4
        python3 starter_kit/student_controller.py &
        STUDENT_PID=$!
        
        echo "Simulation en cours (Ctrl+C pour arrêter)..."
        wait $STUDENT_PID || true
        kill $GZ_PID 2>/dev/null || true
    '

echo "Simulation terminée. Replay disponible : gz sim --playback ./local_output/replay"
