```bash
xhost +local:

docker run --rm \
    -v "$(pwd):/workspace" \
    -w /workspace \
    ocean-regatta-student-local:2026 \
    bash -c "cmake -B plugins/build -S plugins && cmake --build plugins/build -j\$(nproc)"

export GZ_SIM_SYSTEM_PLUGIN_PATH="/workspace/plugins/build:${GZ_SIM_SYSTEM_PLUGIN_PATH}"

docker build -f "./Dockerfile" -t ocean-regatta-student-local:2026 ./
docker run -it --rm --name ocean-regatta-sim \
    -v "./:/workspace" \
    -w /workspace \
    --net=host \
    --gpus all \
    -e DISPLAY=$DISPLAY \
    -e NVIDIA_DRIVER_CAPABILITIES=all \
    -e GZ_SIM_SYSTEM_PLUGIN_PATH=/workspace/plugins/build \
    -e GZ_GUI_PLUGIN_PATH=/workspace/plugins/build \
    -e GZ_SIM_RESOURCE_PATH=/workspace/models:/workspace/worlds \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    --mount type=bind,source=/home/quentin.brateau/Bureau/,target=/home/program \
    ocean-regatta-student-local:2026
```