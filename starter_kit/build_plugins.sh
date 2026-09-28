#!/usr/bin/env bash
set -e

# Prevent Git Bash / MSYS from translating Linux paths like /workspace to Windows host paths
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# For Git Bash on Windows, convert host paths to native Windows paths for Docker CLI
if pwd -W >/dev/null 2>&1; then
    REPO_ROOT="$(cd "${REPO_ROOT}" && pwd -W)"
fi

IMAGE_NAME="ocean-regatta-student-local:2026"

echo "=== Compiling Gazebo plugins inside Docker (${IMAGE_NAME}) ==="
docker run --rm \
    -v "${REPO_ROOT}:/workspace" \
    -w /workspace \
    "${IMAGE_NAME}" \
    bash -c "cmake -B plugins/build -S plugins && cmake --build plugins/build -j\$(nproc)"

echo "=== Build successful! Artifacts in plugins/build/ ==="
ls -lh "${REPO_ROOT}/plugins/build/"*.so
