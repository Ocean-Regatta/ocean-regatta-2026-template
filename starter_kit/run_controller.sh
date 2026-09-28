#!/usr/bin/env bash
set -e

CONTAINER=$(docker ps -q -f "name=ocean-regatta-sim")
if [ -z "${CONTAINER}" ]; then
    CONTAINER=$(docker ps -q -f "ancestor=ocean-regatta-student-local:2026" | head -n 1)
fi

if [ -z "${CONTAINER}" ]; then
    echo -e "\033[31m[Error] Simulation container 'ocean-regatta-sim' is not currently running.\033[0m"
    echo -e "\033[33mPlease start the Gazebo simulation first:\033[0m"
    echo -e "  ./starter_kit/run_docker.sh --server-only"
    exit 1
fi

echo -e "\033[36m=== Attaching interactive Student Controller to Gazebo Simulation ===\033[0m"
echo -e "\033[32mCode changes in starter_kit/student_controller.py apply immediately on each run.\033[0m"
echo -e "Press Ctrl+C to stop the controller without stopping Gazebo.\n"

DOCKER_FLAGS="-i"
if [ -t 0 ] && [ -t 1 ]; then
    DOCKER_FLAGS="-it"
fi

docker exec ${DOCKER_FLAGS} "${CONTAINER}" python3 /workspace/starter_kit/student_controller.py
