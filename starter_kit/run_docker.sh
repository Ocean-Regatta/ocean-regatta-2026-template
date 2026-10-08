#!/usr/bin/env bash
set -e

# Prevent Git Bash / MSYS from translating Linux paths like /workspace to Windows host paths
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# For Git Bash on Windows, convert host paths to native Windows paths for Docker CLI
if pwd -W >/dev/null 2>&1; then
    SCRIPT_DIR="$(cd "${SCRIPT_DIR}" && pwd -W)"
    REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -W)"
fi

IMAGE_NAME="ocean-regatta-sim:2026"

echo "=== [1/3] Preparing Gazebo Jetty Docker image (${IMAGE_NAME}) ==="
if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
    docker build \
        -f "${REPO_ROOT}/Dockerfile" \
        -t "${IMAGE_NAME}" \
        "${REPO_ROOT}"
else
    echo "Image ${IMAGE_NAME} already exists. Skipping build."
fi

echo "=== [2/3] Checking simulation plugins ==="
if [ ! -f "${REPO_ROOT}/plugins/build/libscoring_system.so" ]; then
    echo "Building C++ plugins inside Docker container..."
    mkdir -p "${REPO_ROOT}/plugins/build"
    docker run --rm \
        -v "${REPO_ROOT}:/workspace" \
        -w /workspace \
        "${IMAGE_NAME}" \
        bash -c "cmake -B plugins/build -S plugins && cmake --build plugins/build -j\$(nproc)"
fi

echo "=== [3/3] Starting Gazebo simulation container ==="
mkdir -p "${REPO_ROOT}/output/replay"
chmod -R 777 "${REPO_ROOT}/output" 2>/dev/null || true

docker rm -f ocean-regatta-sim >/dev/null 2>&1 || true

DOCKER_FLAGS="-i"
if [ -t 0 ] && [ -t 1 ]; then
    DOCKER_FLAGS="-it"
fi

WORLD_FILE="${1:-/workspace/worlds/evaluation_world.sdf}"

echo "Launching simulation with world: ${WORLD_FILE}"
echo "In another terminal, run: ./starter_kit/run_controller.sh"
echo "Press Ctrl+C to terminate the simulation."

docker run --rm ${DOCKER_FLAGS} \
    --name ocean-regatta-sim \
    -p 9002:9002 \
    -v "${REPO_ROOT}:/workspace" \
    -w /workspace \
    "${IMAGE_NAME}" \
    gz sim -s -r -v 2 "${WORLD_FILE}"
