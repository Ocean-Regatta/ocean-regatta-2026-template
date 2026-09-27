#!/usr/bin/env python3
"""
Ocean Regatta
Starter Kit - Autonomous USV Controller
Target: Blue Robotics BlueBoat (Differential Thrust Catamaran)
Framework: Pure Python with Gazebo Transport (No ROS 2 required)
"""

import math
import sys
import time
import signal
from typing import Dict, List, Optional

try:
    from gz.transport13 import Node
except ImportError:
    try:
        from gz.transport12 import Node
    except ImportError:
        try:
            from gz.transport import Node
        except ImportError:
            raise ImportError("Gazebo Transport not found. Please install python3-gz-transport.")

try:
    from gz.msgs10.double_pb2 import Double
    from gz.msgs10.imu_pb2 import IMU
    from gz.msgs10.navsat_pb2 import NavSat
    from gz.msgs10.laserscan_pb2 import LaserScan
    from gz.msgs10.pose_v_pb2 import Pose_V
except ImportError:
    try:
        from gz.msgs9.double_pb2 import Double
        from gz.msgs9.imu_pb2 import IMU
        from gz.msgs9.navsat_pb2 import NavSat
        from gz.msgs9.laserscan_pb2 import LaserScan
        from gz.msgs9.pose_v_pb2 import Pose_V
    except ImportError:
        from gz.msgs.double_pb2 import Double
        from gz.msgs.imu_pb2 import IMU
        from gz.msgs.navsat_pb2 import NavSat
        from gz.msgs.laserscan_pb2 import LaserScan
        from gz.msgs.pose_v_pb2 import Pose_V


class BlueBoatController:
    STATE_GATES = "NAVIGATE_GATES"
    STATE_CARDINAL = "ROUND_CARDINAL"
    STATE_PIER = "FOLLOW_PIER"

    def __init__(self):
        self.node = Node()
        self.running = True

        self.pub_thrust_left = self.node.advertise("/blueboat/cmd_thrust_left", Double)
        self.pub_thrust_right = self.node.advertise("/blueboat/cmd_thrust_right", Double)

        self.current_yaw: float = 0.0
        self.current_yaw_rate: float = 0.0
        self.current_pos_x: float = 0.0
        self.current_pos_y: float = 0.0
        self.current_pos_z: float = 0.0
        self.gps_received: bool = False

        self.ping2_port_range: float = 999.0
        self.ping2_last_valid_time: float = 0.0
        self.detected_buoys: Dict[str, tuple] = {}

        self.state = self.STATE_GATES
        self.current_gate_idx: int = 1
        self.total_gates: int = 3

        self.target_pier_distance = 3.0
        self.prev_distance_error = 0.0
        self.kp_pier = 18.0
        self.kd_pier = 8.5
        self.base_thrust = 32.0

        self.node.subscribe(IMU, "/blueboat/imu", self.on_imu)
        self.node.subscribe(NavSat, "/blueboat/gps", self.on_gps)
        self.node.subscribe(LaserScan, "/blueboat/ping2_port", self.on_ping2)
        self.node.subscribe(Pose_V, "/blueboat/detected_buoys", self.on_buoys)

        print("[BlueBoatController] Contrôleur prêt (10 Hz).")

    def on_imu(self, msg: IMU):
        q = msg.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        self.current_yaw = math.atan2(siny_cosp, cosy_cosp)
        self.current_yaw_rate = msg.angular_velocity.z

    def on_gps(self, msg: NavSat):
        lat_origin = 48.0
        lon_origin = -4.5
        meters_per_lat = 111139.0
        meters_per_lon = 111139.0 * math.cos(math.radians(lat_origin))
        self.current_pos_x = (msg.latitude - lat_origin) * meters_per_lat
        self.current_pos_y = (msg.longitude - lon_origin) * meters_per_lon
        self.current_pos_z = msg.altitude
        self.gps_received = True

    def on_ping2(self, msg: LaserScan):
        if len(msg.ranges) > 0:
            val = msg.ranges[0]
            if 0.5 <= val <= 30.0:
                self.ping2_port_range = val
                self.ping2_last_valid_time = time.time()

    def on_buoys(self, msg: Pose_V):
        new_buoys = {}
        for p in msg.pose:
            new_buoys[p.name] = (p.position.x, p.position.y, p.position.z)
        self.detected_buoys = new_buoys

    def set_thrusters(self, left_thrust: float, right_thrust: float):
        left_thrust = max(-50.0, min(50.0, left_thrust))
        right_thrust = max(-50.0, min(50.0, right_thrust))

        msg_l = Double()
        msg_l.data = float(left_thrust)
        self.pub_thrust_left.publish(msg_l)

        msg_r = Double()
        msg_r.data = float(right_thrust)
        self.pub_thrust_right.publish(msg_r)

    def step(self):
        now = time.time()
        sonar_active = (now - self.ping2_last_valid_time < 0.5)

        if self.state == self.STATE_GATES:
            port_name = f"gate_port_{self.current_gate_idx}"
            stbd_name = f"gate_starboard_{self.current_gate_idx}"
            target_angle = 0.0
            surge = self.base_thrust

            if port_name in self.detected_buoys and stbd_name in self.detected_buoys:
                px, py, _ = self.detected_buoys[port_name]
                sx, sy, _ = self.detected_buoys[stbd_name]
                mid_x = (px + sx) * 0.5
                mid_y = (py + sy) * 0.5
                target_angle = math.atan2(mid_y, mid_x)
                if math.hypot(mid_x, mid_y) < 2.0:
                    print(f"[Controller] Porte {self.current_gate_idx} franchie !")
                    self.current_gate_idx += 1
                    if self.current_gate_idx > self.total_gates:
                        self.state = self.STATE_CARDINAL

            yaw_error = target_angle
            steering = 15.0 * yaw_error - 4.0 * self.current_yaw_rate
            self.set_thrusters(surge - steering, surge + steering)

        elif self.state == self.STATE_CARDINAL:
            cardinal_entry = None
            cardinal_name = None
            for name, coords in self.detected_buoys.items():
                if "cardinal" in name:
                    cardinal_name = name
                    cardinal_entry = coords
                    break

            if cardinal_entry is not None:
                cx, cy, _ = cardinal_entry
                target_offset_y = 5.0
                if "south" in cardinal_name:
                    target_offset_y = -5.0
                target_angle = math.atan2(cy + target_offset_y, cx)
                surge = self.base_thrust * 0.9
                steering = 12.0 * target_angle - 3.5 * self.current_yaw_rate
                self.set_thrusters(surge - steering, surge + steering)
                if cx < -1.0 or math.hypot(cx, cy) < 2.5:
                    self.state = self.STATE_PIER
            else:
                self.set_thrusters(self.base_thrust, self.base_thrust)
                if sonar_active and self.ping2_port_range < 10.0:
                    self.state = self.STATE_PIER

        elif self.state == self.STATE_PIER:
            surge = self.base_thrust * 0.85
            if sonar_active:
                current_dist = self.ping2_port_range
                dist_error = current_dist - self.target_pier_distance
                d_error = (dist_error - self.prev_distance_error) / 0.1
                self.prev_distance_error = dist_error
                steering = max(-20.0, min(20.0, (self.kp_pier * dist_error) + (self.kd_pier * d_error)))
                self.set_thrusters(surge - steering, surge + steering)
            else:
                self.set_thrusters(surge * 0.9, surge * 1.1)

    def stop(self):
        self.running = False
        self.set_thrusters(0.0, 0.0)


def main():
    controller = BlueBoatController()

    def signal_handler(sig, frame):
        controller.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    rate_hz = 10.0
    dt = 1.0 / rate_hz

    while controller.running:
        t0 = time.time()
        try:
            controller.step()
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
        time.sleep(max(0.0, dt - (time.time() - t0)))


if __name__ == "__main__":
    main()
