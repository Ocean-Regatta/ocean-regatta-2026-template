#!/usr/bin/env bash
set -e

# Prevent Git Bash / MSYS from translating Linux paths like /workspace to Windows host paths
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# For Git Bash on Windows, convert host paths to native Windows paths for the Docker CLI
if pwd -W >/dev/null 2>&1; then
    SCRIPT_DIR="$(cd "${SCRIPT_DIR}" && pwd -W)"
    REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -W)"
fi

echo "=== [1/3] Building local Gazebo Jetty Docker image ==="
docker build \
    -f "${SCRIPT_DIR}/Dockerfile.local" \
    -t ocean-regatta-student-local:2026 \
    "${SCRIPT_DIR}"

echo "=== [2/3] Preparing local replay directory ==="
mkdir -p "${REPO_ROOT}/local_output/replay"
chmod -R 777 "${REPO_ROOT}/local_output" 2>/dev/null || true

echo "=== [3/3] Executing local simulation sandbox ==="
if [ -t 0 ] && [ -t 1 ]; then
    DOCKER_FLAGS="-it"
else
    DOCKER_FLAGS="-i"
fi

docker rm -f ocean-regatta-sim >/dev/null 2>&1 || true

docker run --rm ${DOCKER_FLAGS} \
    --name ocean-regatta-sim \
    -p 9002:9002 \
    -p 8080:8080 \
    -v "${REPO_ROOT}:/workspace" \
    -w /workspace \
    ocean-regatta-student-local:2026 \
    bash /workspace/starter_kit/entrypoint_sim.sh "$@"

echo "Simulation complete. Replay available: gz sim --playback ./local_output/replay"
