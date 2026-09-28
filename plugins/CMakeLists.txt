cmake_minimum_required(VERSION 3.22)
project(regatta_plugins)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)

find_package(gz-sim REQUIRED)
find_package(gz-gui REQUIRED)
find_package(Qt6 COMPONENTS Core Quick Qml Widgets REQUIRED)
find_package(Protobuf REQUIRED)

# 1. Scoring System Plugin (System plugin running inside simulation server)
add_library(scoring_system SHARED
  ScoringSystem.cc
)
target_link_libraries(scoring_system
  gz-sim::gz-sim
)

# 2. Scoring Widget Plugin (GUI plugin running inside Gazebo GUI window)
add_library(ScoringWidget SHARED
  ScoringWidget.cc
  ScoringWidget.qrc
)
target_link_libraries(ScoringWidget
  gz-gui::gz-gui
  Qt6::Core
  Qt6::Quick
  Qt6::Qml
  Qt6::Widgets
)

# Ensure both libScoringWidget.so and libscoring_widget.so exist
add_custom_command(TARGET ScoringWidget POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E copy_if_different $<TARGET_FILE:ScoringWidget> ${CMAKE_CURRENT_BINARY_DIR}/libscoring_widget.so
)

# 3. Wave and Stream Simulation Plugin (System plugin running inside simulation server)
add_library(wave_simulation_system SHARED
  WaveSimulationSystem.cc
)
target_link_libraries(wave_simulation_system
  gz-sim::gz-sim
)

# 4. Semantic Buoy Perception Sensor System Plugin
set(PROTO_DIR ${CMAKE_CURRENT_SOURCE_DIR}/proto)
set(PROTO_FILE ${PROTO_DIR}/buoy.proto)
protobuf_generate_cpp(PROTO_SRCS PROTO_HDRS ${PROTO_FILE})

# Ensure Python Protobuf bindings are also kept up-to-date in starter_kit
set(PYTHON_PROTO_OUT ${CMAKE_CURRENT_SOURCE_DIR}/../starter_kit/buoy_pb2.py)
add_custom_command(
  OUTPUT ${PYTHON_PROTO_OUT}
  COMMAND ${Protobuf_PROTOC_EXECUTABLE} --proto_path=${PROTO_DIR} --python_out=${CMAKE_CURRENT_SOURCE_DIR}/../starter_kit ${PROTO_FILE}
  DEPENDS ${PROTO_FILE}
  COMMENT "Generating Python Protobuf bindings in starter_kit"
)
add_custom_target(generate_python_proto ALL DEPENDS ${PYTHON_PROTO_OUT})

add_library(semantic_buoy_sensor_system SHARED
  SemanticBuoySensorSystem.cc
  ${PROTO_SRCS}
  ${PROTO_HDRS}
)
target_include_directories(semantic_buoy_sensor_system PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}
  ${CMAKE_CURRENT_BINARY_DIR}
)
target_link_libraries(semantic_buoy_sensor_system
  gz-sim::gz-sim
  ${Protobuf_LIBRARIES}
)
add_dependencies(semantic_buoy_sensor_system generate_python_proto)

# Optional installation to system Gazebo plugin directory if available
if(EXISTS "/usr/lib/x86_64-linux-gnu/gz-sim-10/plugins")
  install(TARGETS wave_simulation_system scoring_system ScoringWidget semantic_buoy_sensor_system
    DESTINATION /usr/lib/x86_64-linux-gnu/gz-sim-10/plugins
  )
endif()
