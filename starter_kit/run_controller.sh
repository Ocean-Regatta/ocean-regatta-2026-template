#!/usr/bin/env bash
set -e

CONTAINER="ocean-regatta-sim"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo -e "\033[31m[Error] Simulation container '${CONTAINER}' is not currently running.\033[0m"
    echo -e "\033[33mPlease start the Gazebo simulation first in another terminal:\033[0m"
    echo -e "  ./starter_kit/run_docker.sh"
    exit 1
fi

echo -e "\033[36m=== Launching Student Controller in Docker simulation ===\033[0m"
echo -e "\033[32mCode changes in starter_kit/student_controller.py apply immediately.\033[0m"
echo -e "Press Ctrl+C to terminate controller.\n"

DOCKER_FLAGS="-i"
if [ -t 0 ] && [ -t 1 ]; then
    DOCKER_FLAGS="-it"
fi

docker exec ${DOCKER_FLAGS} "${CONTAINER}" python3 /workspace/starter_kit/student_controller.py
