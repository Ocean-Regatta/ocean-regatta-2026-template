# Ocean Regatta 2026 — Participant Starter Kit 🚤

Welcome to the official starter repository for the **Ocean Regatta 2026** autonomous marine robotics challenge!
This kit provides everything you need to develop, test, and visualize autonomous navigation algorithms for the **Blue Robotics BlueBoat** uncrewed surface vessel (USV) in the **Gazebo Jetty** simulator.

---

## 🎯 Challenge Objectives

Your goal is to program an autonomous Python controller capable of completing the full course within the **180-second** time limit:

1. **Navigate 3 Channel Gates:** Traverse pairs of buoys (red port, green starboard) while handling transverse ocean currents and differential motor dynamics.
2. **Round the Cardinal Buoy:** Comply with international IALA maritime regulations by rounding the marker on the required quadrant (North in the practice world).
3. **Traverse the Pier Entry Gate:** Line up accurately with the harbor pier structure.
4. **Precision Pier Wall Tracking:** Maintain a strict $5.0 \text{ m}$ standoff distance from the pier wall using the port-side Ping2 single-beam acoustic echosounder without colliding with the structure.
5. **Clear the Pier Exit Gate:** Cross the finish line to complete the regatta!

---

## 📁 Repository Structure

```
participant_template/
├── models/
│   └── blueboat/                # Authentic Blue Robotics BlueBoat 3D model & physics
│       ├── meshes/              # High-fidelity 3D meshes (hulls, frame, antenna, STL/OBJ)
│       ├── model.sdf            # Complete SDF specification (sensors, hydrodynamics, thrusters)
│       └── model.config         # Gazebo model metadata
├── worlds/
│   └── practice_world.sdf       # Official practice environment with ocean plane & buoys
├── starter_kit/
│   ├── student_controller.py    # ✏️ YOUR CODE GOES HERE (only file evaluated on server)
│   ├── blueboat_driver.py       # Hardware abstraction layer (HAL) for sensors and thrusters
│   ├── run_docker.ps1           # Turnkey Docker launcher for Windows PowerShell
│   ├── run_docker.bat           # Turnkey Docker launcher for Windows Command Prompt
│   ├── run_docker.sh            # Turnkey Docker launcher for Linux, macOS & Git Bash
│   ├── run_local.sh             # Native launcher (if Gazebo Jetty is installed locally)
│   ├── entrypoint_sim.sh        # Headless Gazebo & controller runner inside Docker
│   └── Dockerfile.local         # Development Docker container
└── .github/
    └── workflows/
        └── evaluate.yml         # Automated GitHub Actions evaluation workflow
```

> [!IMPORTANT]
> **Golden Rule of Evaluation:**
> During automated evaluation on the competition servers, **only your `starter_kit/student_controller.py` file is extracted and executed**.
> The evaluation container provides its own immutable copy of `blueboat_driver.py` and generates an unseen evaluation world with a secret pseudo-random seed.

---

## 🛥️ Blue Robotics BlueBoat 3D Model

The simulator features an authentic **Blue Robotics BlueBoat** catamaran representation:
* **True-to-Scale Geometry:** Catamaran hulls ($1.20\text{ m}$ length, $0.93\text{ m}$ beam) with anodized aluminum crossbars and telemetry mast.
* **Hydrodynamics:** Fossen nonlinear damping and added-mass simulation in 6 DOFs.
* **Propulsion:** Dual rear-mounted Blue Robotics T200 thrusters with independent differential thrust commands limited to $[-50.0\text{ N}, +50.0\text{ N}]$.
* **Collision Physics:** Optimized analytical collision capsules ensuring stable contacts and accurate pier collision detection.

---

## 👁️ Sensors & Observation API

At each step of the **$10\text{ Hz}$** control loop, your controller receives an `obs: Observation` dataclass from the `BlueBoatDriver`.

### 1. Forward Semantic Perception Sensor (`obs.buoys`)
Simulates an on-board computer vision / semantic perception detector tracking buoys within an observation cone in front of the vehicle:
* **Update Rate:** $1\text{ Hz}$ (publishes once per second via native Gazebo Transport on `/blueboat/buoy_observations`).
* **Observation Cone (Tunable FOV):** Tunable forward cone (default $\pm 55^\circ$, $110^\circ$ total horizontal FOV, up to $35.0\text{ m}$ range).
* **Tunable Uncertainty:** Measurements include realistic sensor noise (e.g., Gaussian $\pm 0.5\text{ m}$ range uncertainty and $\pm 3^\circ$ bearing uncertainty).
* **Buoy Information Provided (`BuoyData`):**
  * `buoy.name`: Unique identifier (e.g., `"gate_port_1"`, `"gate_starboard_1"`, `"cardinal_north"`, `"gate_pier_entry_port"`).
  * `buoy.buoy_type` (or `buoy.type`): Semantic category string (`"red"` for port/cylinder buoys, `"green"` for starboard/cone buoys, `"cardinal_north"`, `"cardinal_south"`, `"cardinal_east"`, `"cardinal_west"`).
  * `buoy.range` (or `buoy.distance`): Direct Euclidean range in meters (with uncertainty).
  * `buoy.bearing`: Relative horizontal bearing to boat heading in radians ($-\pi$ to $+\pi$, $>0$ port / $<0$ starboard).
  * `buoy.bearing_deg`: Relative bearing in degrees ($-180^\circ$ to $+180^\circ$).
  * `buoy.x`: Forward body-frame relative coordinate (surge axis, meters).
  * `buoy.y`: Lateral body-frame relative coordinate (sway axis, meters, $>0$ port / $<0$ starboard).

#### Usage Example in Controller
```python
for name, buoy in obs.buoys.items():
    print(f"[{buoy.name}] Type: {buoy.buoy_type} | Range: {buoy.range:.2f}m | Bearing: {buoy.bearing_deg:.1f}°")
    if buoy.buoy_type == "red":
        # Pass to the starboard side of port mark
        ...
    elif buoy.buoy_type == "cardinal_north":
        # Round on the northern side
        ...
```

### 2. Ping2 Acoustic Echosounder (`obs.ping2`)
* Mounted at $+90^\circ$ (strictly perpendicular to the vessel's port / left flank).
* **Distance:** `obs.ping2.distance` (meters, active range $0.5\text{ m}$ to $30.0\text{ m}$).
* **Validity flag:** `obs.ping2.is_valid` is `True` when echoes are fresh ($< 0.5\text{ s}$) and within operational bounds.

### 3. Inertial Measurement Unit (`obs.imu`)
* `obs.imu.yaw`: Compass heading in radians ($-\pi$ to $+\pi$, $0 = \text{East}$).
* `obs.imu.yaw_rate`: Yaw angular velocity in rad/s ($r$, essential for rate damping and PID heading control).
* `obs.imu.roll`, `obs.imu.pitch`: Vessel attitude angles.
* `obs.imu.linear_accel_x`, `obs.imu.linear_accel_y`: Linear body accelerations.

### 4. GNSS / GPS Receiver (`obs.gps`)
* `obs.gps.x`, `obs.gps.y`: Metric Cartesian coordinates projected from the reference origin ($48.0^\circ\text{N}, -4.5^\circ\text{W}$).

---

## 🎯 Dynamic Waypoint Capsule Scoring

Each channel gate and pier alignment checkpoint features a semi-transparent 2.0-meter indicator capsule:
* **Initial State:** Red ($0\%$ score).
* **Perfect Precision:** If the boat center passes within **$0.50\text{ m}$** of the capsule midpoint, you receive **$100\%$ of points** and the capsule turns **Pure Green**!
* **Smooth Interpolation:** Between $0.50\text{ m}$ and $1.0\text{ m}$, score is linearly interpolated with a dynamic Red $\rightarrow$ Green color transition visible in Gazebo.
* **Cardinal Buoy:** Has no physical capsule to discourage dangerous close quarters. Compliance with the regulatory quadrant is checked geometrically (+250 pts).

---

## 🌊 Ocean Waves & Streams Simulation

The simulation features a dynamic ocean environment plugin (`libwave_simulation_system.so`) configurable directly within the world SDF (`worlds/practice_world.sdf`):

```xml
<plugin filename="libwave_simulation_system.so" name="regatta::WaveSimulationSystem">
  <!-- Ocean Stream / Current -->
  <stream_intensity>0.5</stream_intensity>        <!-- Flow speed in m/s -->
  <stream_direction_deg>45.0</stream_direction_deg> <!-- Direction: 0° = East (+X), 90° = North (+Y) -->

  <!-- Ocean Waves -->
  <wave_amplitude>0.15</wave_amplitude>           <!-- Wave amplitude in meters (crest height) -->
  <wave_period>4.0</wave_period>                  <!-- Wave period in seconds -->
  <wave_direction_deg>30.0</wave_direction_deg>   <!-- Propagation direction in degrees -->
  <wave_steepness>0.8</wave_steepness>            <!-- Gerstner steepness [0.0 = sine wave, 1.0 = sharp crest] -->

  <!-- Vessel & Buoys Interaction -->
  <robot_name>blueboat</robot_name>
  <robot_link>base_link</robot_link>
  <buoy_heave_amplitude_scale>1.0</buoy_heave_amplitude_scale> <!-- Buoy heave response (z) -->
  <buoy_tilt_scale>1.0</buoy_tilt_scale>                       <!-- Buoy pitch & roll response (theta, phi) -->
  <buoy_mooring_compliance>0.08</buoy_mooring_compliance>       <!-- Mooring compliance in waves -->
</plugin>
```

### Physical Dynamics & Buoy Motion
* **Stream Forces on BlueBoat:** Exerts realistic hydrodynamic drag on the hull according to stream velocity and direction, displacing the vessel downstream and requiring heading correction.
* **Wave Perturbations:** Induces dynamic heave forces and pitch/roll excitation moments onto the catamaran hulls as wave crests and troughs traverse the vessel.
* **Buoy Oscillation & Buoyancy:** All channel gate and cardinal buoys dynamically track the local wave elevation and slopes, oscillating in heave ($z$), roll ($\phi$), and pitch ($\theta$) while remaining moored at their geographic waypoint positions.

---


## 💻 Running the Simulation Locally

### Option A: Docker (Recommended — with Native WebSocket 3D WebViewer)
Works seamlessly on Windows, Linux, and macOS without requiring a local Gazebo or ROS installation.
**No X11 / X server export required**—the 3D simulation scene streams directly to your browser via WebSockets!

#### Mode 1: Complete Turnkey Simulation (Recommended)
Docker runs both Gazebo and `student_controller.py` in the container. Any code changes made in `starter_kit/student_controller.py` take effect immediately on each launch because your folder is mounted live into the container:
* **Windows (PowerShell):** `.\starter_kit\run_docker.ps1`
* **Windows (Command Prompt):** `starter_kit\run_docker.bat`
* **Linux / macOS / WSL:** `./starter_kit/run_docker.sh`

#### Mode 2: Interactive Controller Iteration (Two Terminals)
Keep Gazebo running in the background and start/stop/restart your Python controller in a separate terminal:
1. **Terminal 1: Start Gazebo Simulation Server**
   * **Windows (PowerShell):** `.\starter_kit\run_docker.ps1 -ServerOnly`
   * **Windows (Command Prompt):** `starter_kit\run_docker.bat --server-only`
   * **Linux / macOS / WSL:** `./starter_kit/run_docker.sh --server-only`
2. **Terminal 2: Run and debug your controller interactively**
   * **Windows (PowerShell):** `.\starter_kit\run_controller.ps1`
   * **Windows (Command Prompt):** `starter_kit\run_controller.bat`
   * **Linux / macOS / WSL:** `./starter_kit/run_controller.sh`
   *(Or manually: `docker exec -it ocean-regatta-sim python3 starter_kit/student_controller.py`)*

#### 🌐 Viewing the 3D Simulation in your Browser:
While the simulation runs inside Docker:
* **Option 1 (Local WebViewer):** Open [http://localhost:8080](http://localhost:8080) in your web browser.
* **Option 2 (Official Hosted Viewer):** Visit [https://app.gazebosim.org/visualization](https://app.gazebosim.org/visualization) and connect to `ws://localhost:9002`.

---

### Option B: Native Installation (Ubuntu 24.04 / 22.04 with Gazebo Jetty)

You can launch Gazebo either with its native Qt GUI window or in headless mode with WebSocket:

```bash
# Mode 1: Native 3D GUI Window (default)
./starter_kit/run_local.sh --gui

# Mode 2: Headless Gazebo Server with WebSocket (view in browser at http://localhost:8080)
./starter_kit/run_local.sh --web
```


---

## 📤 Submission & Automated Evaluation

1. Create a dedicated feature branch:
   ```bash
   git checkout -b feature/my-cool-strategy
   git add starter_kit/student_controller.py
   git commit -m "feat: improve Ping2 wall following and gate alignment"
   git push origin feature/my-cool-strategy
   ```
2. Open a **Pull Request** targeting the `master` branch on GitHub.
3. The automated evaluation workflow triggers immediately:
   * It provisions an isolated headless simulation container.
   * Tests your controller against a secret environmental seed with currents and wavelets.
   * Posts an evaluation report directly to your PR with your score and unlocked badges.
   * Submits your validated result to the official **Live Scoreboard**.

> [!NOTE]
> **Evaluation Cooldown:**
> To prevent over-optimizing to specific seeds, a **60-minute cooldown** is enforced between successive evaluation runs on the server.

### 🎥 3D Playback & Run Replay
Every evaluation run records a full physical trajectory log:
1. Download the `gz-replay-pr-*.zip` artifact from the GitHub Actions tab of your PR.
2. Extract the archive and launch the replay viewer:
   ```bash
   gz sim --playback ./output/replay
   ```
3. Watch your BlueBoat carve through the waves, observe indicator capsules shift color in real-time, and analyze your navigation profile!