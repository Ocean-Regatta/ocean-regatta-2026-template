#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Check if simulation container is running
CONTAINER=$(docker ps -q -f "name=ocean-regatta-sim" 2>/dev/null || true)
if [ -z "${CONTAINER}" ]; then
    CONTAINER=$(docker ps -q -f "ancestor=ocean-regatta-student-local:2026" 2>/dev/null | head -n 1 || true)
fi

if [ -n "${CONTAINER}" ]; then
    echo -e "\033[36m=== Launching BlueBoat Keyboard Teleop in Docker Simulation Container ===\033[0m"
    docker exec -it "${CONTAINER}" python3 /workspace/starter_kit/teleop_keyboard.py
else
    # Check if native python3 with gz is available
    if command -v gz &>/dev/null || python3 -c "import gz.transport" &>/dev/null; then
        echo -e "\033[36m=== Launching BlueBoat Keyboard Teleop Locally ===\033[0m"
        python3 "${REPO_ROOT}/starter_kit/teleop_keyboard.py"
    else
        echo -e "\033[31m[Error] Neither running simulation container 'ocean-regatta-sim' nor local Gazebo Transport was found.\033[0m"
        echo -e "\033[33mPlease start the Gazebo simulation first, for example:\033[0m"
        echo -e "  ./starter_kit/run_docker.sh --server-only"
        exit 1
    fi
fi
