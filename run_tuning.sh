#!/usr/bin/env bash
set -e

# Ocean Regatta 2026 — Flat World & BlueBoat Tuning Launcher
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

USE_DOCKER=false
MODE="gui"

for arg in "$@"; do
    case "$arg" in
        --docker)
            USE_DOCKER=true
            ;;
        --local)
            USE_DOCKER=false
            ;;
        --headless|--server-only)
            MODE="headless"
            ;;
        --gui)
            MODE="gui"
            ;;
        -h|--help)
            echo "Usage: ./run_tuning.sh [options]"
            echo ""
            echo "Options:"
            echo "  --docker       Run Gazebo simulation inside the Docker container (default if local 'gz' not found)"
            echo "  --local        Run Gazebo simulation locally using host binaries"
            echo "  --headless     Run headless (server-only)"
            echo "  --gui          Run with full Gazebo GUI (default)"
            echo "  -h, --help     Show this help message"
            echo ""
            echo "Keyboard teleop:"
            echo "  In a second terminal, run: ./run_teleop.sh"
            exit 0
            ;;
    esac
done

# If local 'gz' command not found, default to Docker
if ! command -v gz &>/dev/null; then
    USE_DOCKER=true
fi

echo -e "\033[36m====================================================================\033[0m"
echo -e "\033[36m Ocean Regatta 2026 — Flat World BlueBoat Parameter Tuning \033[0m"
echo -e "\033[36m====================================================================\033[0m"
echo -e "World:     \033[33mworlds/flat_world.sdf\033[0m (Flat ocean, no waves, no ocean stream)"
echo -e "Target:    \033[33mBlueBoat USV (models/blueboat/model.sdf)\033[0m"
echo -e "Teleop:    Run \033[32m./run_teleop.sh\033[0m in another terminal to pilot"
echo -e "\033[36m--------------------------------------------------------------------\033[0m"

if [ "$USE_DOCKER" = true ]; then
    echo -e "Starting Gazebo inside Docker container \033[32mocean-regatta-sim\033[0m..."
    xhost +local: 2>/dev/null || true

    docker rm -f ocean-regatta-sim >/dev/null 2>&1 || true

    DOCKER_CMD="gz sim -v 3 -r /workspace/worlds/flat_world.sdf"
    if [ "$MODE" = "headless" ]; then
        DOCKER_CMD="gz sim -s -v 2 -r /workspace/worlds/flat_world.sdf"
    fi

    docker run -it --rm --name ocean-regatta-sim \
        -v "${SCRIPT_DIR}:/workspace" \
        -w /workspace \
        --net=host \
        --gpus all \
        -e DISPLAY="${DISPLAY:-:0}" \
        -e NVIDIA_DRIVER_CAPABILITIES=all \
        -e GZ_SIM_SYSTEM_PLUGIN_PATH=/workspace/plugins/build \
        -e GZ_GUI_PLUGIN_PATH=/workspace/plugins/build \
        -e GZ_SIM_RESOURCE_PATH=/workspace/models:/workspace/worlds \
        -v /tmp/.X11-unix:/tmp/.X11-unix \
        ocean-regatta-student-local:2026 \
        ${DOCKER_CMD}
else
    echo -e "Starting Gazebo Sim locally..."
    export GZ_SIM_RESOURCE_PATH="${SCRIPT_DIR}/models:${SCRIPT_DIR}/worlds:${GZ_SIM_RESOURCE_PATH}"
    export GZ_SIM_SYSTEM_PLUGIN_PATH="${SCRIPT_DIR}/plugins/build:${GZ_SIM_SYSTEM_PLUGIN_PATH}"
    export GZ_GUI_PLUGIN_PATH="${SCRIPT_DIR}/plugins/build:${GZ_GUI_PLUGIN_PATH}"

    if [ "$MODE" = "headless" ]; then
        gz sim -s -v 2 -r "${SCRIPT_DIR}/worlds/flat_world.sdf"
    else
        gz sim -v 3 -r "${SCRIPT_DIR}/worlds/flat_world.sdf"
    fi
fi

