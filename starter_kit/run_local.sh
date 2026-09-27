#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== [1/3] Configuration de l'environnement Gazebo ==="
export GZ_SIM_RESOURCE_PATH="${REPO_ROOT}/models:${REPO_ROOT}/worlds:${GZ_SIM_RESOURCE_PATH}"

echo "=== [2/3] Démarrage de Gazebo Sim (Monde d'entraînement 3D) ==="
cleanup() {
    echo "Arrêt de Gazebo..."
    if [ -n "${GZ_PID}" ]; then
        kill "${GZ_PID}" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

gz sim -v 3 -r "${REPO_ROOT}/worlds/practice_world.sdf" &
GZ_PID=$!

echo "Attente de l'initialisation (4s)..."
sleep 4

echo "=== [3/3] Lancement du contrôleur étudiant ==="
python3 "${REPO_ROOT}/starter_kit/student_controller.py"

wait ${GZ_PID}
