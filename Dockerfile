FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

ARG PROXY="http://proxy.ecole-navale.fr:8080"
ENV http_proxy=${PROXY} \
    https_proxy=${PROXY} \
    HTTP_PROXY=${PROXY} \
    HTTPS_PROXY=${PROXY} \
    no_proxy="localhost,127.0.0.1" \
    NO_PROXY="localhost,127.0.0.1"
    
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    build-essential \
    python3 \
    python3-pip \
    xvfb \
    procps \
    && rm -rf /var/lib/apt/lists/*

RUN curl https://packages.osrfoundation.org/gazebo.gpg --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null

RUN apt-get update && apt-get install -y --no-install-recommends \
    gz-jetty \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

ENV GZ_SIM_RESOURCE_PATH=/workspace/models:/workspace/worlds
ENV GZ_SIM_SYSTEM_PLUGIN_PATH=/workspace/plugins/build:/workspace/build
ENV GZ_GUI_PLUGIN_PATH=/workspace/plugins/build:/workspace/build
ENV PYTHONUNBUFFERED=1

EXPOSE 9002 8080

CMD ["bash"]
