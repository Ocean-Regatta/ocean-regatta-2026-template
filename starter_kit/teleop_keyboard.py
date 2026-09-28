#!/usr/bin/env python3
"""
Ocean Regatta 2026 — Keyboard Teleoperation for BlueBoat USV

Allows manual interactive piloting of the Blue Robotics BlueBoat in Gazebo Jetty
using the keyboard, while displaying live sensor telemetry (GPS, IMU, Ping2 Sonar, Buoys).

Controls:
  [W] / [Z] / [UP]    : Forward (+Surge Thrust)
  [S]       / [DOWN]  : Reverse (-Surge Thrust)
  [A] / [Q] / [LEFT]  : Steer Left / Port (-Steering)
  [D]       / [RIGHT] : Steer Right / Starboard (+Steering)
  [C]                 : Center Steering (Steer = 0 N)
  [SPACE]   / [X]     : EMERGENCY STOP (Surge = 0 N, Steer = 0 N)
  [1] / [2] / [3]     : Change step size (2 N, 5 N, 10 N)
  [+] / [-]           : Fine tune step size (+/- 1 N)
  [M]                 : Toggle Auto-centering Steering mode
  [Ctrl+C] / [ESC]    : Stop boat & Exit
"""

import os
import sys
import time
import math
import select
import termios
import tty
import atexit
import signal

# Ensure local starter_kit is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from blueboat_driver import BlueBoatDriver, Observation


class TerminalController:
    """Manages raw/cbreak terminal input and non-blocking key reads."""

    def __init__(self):
        self._fd = sys.stdin.fileno()
        self._is_tty = os.isatty(self._fd)
        self._old_settings = None
        if self._is_tty:
            self._old_settings = termios.tcgetattr(self._fd)

    def setup(self):
        if not self._is_tty:
            return
        # Put terminal in cbreak mode (unbuffered input, preserves signal keys and echo control)
        tty.setcbreak(self._fd)
        # Hide terminal cursor
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    def restore(self):
        if not self._is_tty or self._old_settings is None:
            return
        # Show terminal cursor
        sys.stdout.write("\033[?25h\033[0m\n")
        sys.stdout.flush()
        try:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
        except Exception:
            pass

    def get_key(self, timeout=0.0):
        """Non-blocking single key read with ANSI escape sequence parsing."""
        if not self._is_tty:
            return None

        rlist, _, _ = select.select([self._fd], [], [], timeout)
        if not rlist:
            return None

        try:
            ch1 = os.read(self._fd, 1).decode('utf-8', errors='ignore')
        except Exception:
            return None

        if ch1 == '\x1b':  # Escape sequence
            # Check if additional characters follow
            rlist2, _, _ = select.select([self._fd], [], [], 0.05)
            if not rlist2:
                return 'ESC'
            ch2 = os.read(self._fd, 1).decode('utf-8', errors='ignore')
            if ch2 == '[':
                rlist3, _, _ = select.select([self._fd], [], [], 0.05)
                if not rlist3:
                    return 'ESC['
                ch3 = os.read(self._fd, 1).decode('utf-8', errors='ignore')
                if ch3 == 'A':
                    return 'UP'
                elif ch3 == 'B':
                    return 'DOWN'
                elif ch3 == 'C':
                    return 'RIGHT'
                elif ch3 == 'D':
                    return 'LEFT'
                return f'ESC[{ch3}'
            return f'ESC{ch2}'
        elif ch1 == '\x03':  # Ctrl+C
            return 'CTRL_C'
        elif ch1 == '\x04':  # Ctrl+D
            return 'CTRL_D'
        return ch1


class BlueBoatTeleop:
    """Keyboard teleoperation and live telemetry dashboard for BlueBoat USV."""

    MAX_THRUST = 50.0   # Clamped by hardware driver
    MIN_THRUST = -50.0

    def __init__(self, driver: BlueBoatDriver):
        self.driver = driver
        self.term = TerminalController()

        # Motion control state (in Newtons)
        self.surge = 0.0          # Forward / Reverse surge force [-50, +50] N
        self.steer = 0.0          # Differential steering bias [-50, +50] N
        self.step_size = 5.0      # Force increment per keypress
        self.auto_center = False  # If True, steer decays back to 0 when not turning
        self.last_steer_time = time.time()

        self.last_action = "Ready (vessel stationary)"
        self.running = True

        # Register cleanup handlers
        atexit.register(self._cleanup)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _cleanup(self):
        try:
            self.driver.set_thrust(0.0, 0.0)
        except Exception:
            pass
        self.term.restore()

    def _signal_handler(self, sig, frame):
        self.running = False

    def _format_thrust_bar(self, val: float, length: int = 20) -> str:
        """Renders an ASCII thrust bar centered at zero: [-50 ... | ... +50]."""
        half = length // 2
        ratio = max(-1.0, min(1.0, val / self.MAX_THRUST))
        num_blocks = int(abs(ratio) * half)

        if ratio > 0:
            left_part = " " * half
            right_part = ("#" * num_blocks).ljust(half, "-")
        elif ratio < 0:
            left_part = ("#" * num_blocks).rjust(half, "-")
            right_part = " " * half
        else:
            left_part = " " * half
            right_part = " " * half

        return f"[{left_part}|{right_part}]"

    def _heading_cardinal(self, deg: float) -> str:
        """Converts heading in degrees to compass direction."""
        dirs = ["E", "ENE", "NE", "NNE", "N", "NNW", "NW", "WNW", "W", "WSW", "SW", "SSW", "S", "SSE", "SE", "ESE"]
        normalized = (deg % 360 + 360) % 360
        idx = int((normalized + 11.25) / 22.5) % 16
        return dirs[idx]

    def render_hud(self, obs: Observation, left_cmd: float, right_cmd: float):
        """Draws the teleoperation HUD directly in terminal without screen tearing."""
        lines = []
        lines.append("\033[H\033[2K" + "================================================================================")
        lines.append("\033[2K" + "        🚤  BLUE ROBOTICS BLUEBOAT — KEYBOARD TELEOPERATION  🚤        ")
        lines.append("\033[2K" + "================================================================================")
        lines.append("\033[2K" + " [Controls]")
        lines.append("\033[2K" + "   Forward (+Surge) : [W] / [Z] / [▲]       EMERGENCY STOP : [SPACE] / [X]")
        lines.append("\033[2K" + "   Reverse (-Surge) : [S]       / [▼]       Center Steer   : [C]")
        lines.append("\033[2K" + "   Port (Turn Left) : [A] / [Q] / [◀]       Step Presets   : [1]=2N [2]=5N [3]=10N")
        lines.append("\033[2K" + "   Stbd (Turn Right): [D]       / [▶]       Auto-Center    : [M] (Toggle)")
        lines.append("\033[2K" + "   Quit             : [Ctrl+C] or [ESC]     Fine Adjust    : [+] / [-]")
        lines.append("\033[2K" + "--------------------------------------------------------------------------------")

        # Propulsion status
        auto_center_str = "\033[32mON \033[0m" if self.auto_center else "\033[33mOFF\033[0m"
        lines.append("\033[2K" + f" COMMANDED PROPULSION:   Step: {self.step_size:4.1f} N  |  Auto-Center: {auto_center_str}")
        lines.append("\033[2K" + f"   Surge: {self.surge:+5.1f} N   |  Steering Offset: {self.steer:+5.1f} N")

        bar_l = self._format_thrust_bar(left_cmd, 22)
        bar_r = self._format_thrust_bar(right_cmd, 22)
        lines.append("\033[2K" + f"   Left  Thruster (Port) : {bar_l} {left_cmd:+5.1f} N")
        lines.append("\033[2K" + f"   Right Thruster (Stbd) : {bar_r} {right_cmd:+5.1f} N")
        lines.append("\033[2K" + "--------------------------------------------------------------------------------")

        # Telemetry
        gps_status = "\033[32mFIX\033[0m" if obs.gps.is_valid else "\033[31mNO FIX\033[0m"
        lines.append("\033[2K" + f" NAVIGATION TELEMETRY [{gps_status}]:")
        lines.append("\033[2K" + f"   GPS Position : X = {obs.gps.x:+7.2f} m , Y = {obs.gps.y:+7.2f} m  (Alt: {obs.gps.altitude:4.1f} m)")
        
        cardinal = self._heading_cardinal(obs.imu.yaw_deg)
        lines.append("\033[2K" + f"   IMU Heading  : {obs.imu.yaw_deg:+6.1f}° [{cardinal}]  |  Rate: {obs.imu.yaw_rate:+5.2f} rad/s")
        lines.append("\033[2K" + f"   IMU Attitude : Roll: {math.degrees(obs.imu.roll):+5.1f}°  |  Pitch: {math.degrees(obs.imu.pitch):+5.1f}°")

        sonar_status = f"\033[32m{obs.ping2.distance:5.2f} m [VALID]\033[0m" if obs.ping2.is_valid else "\033[33m--- (No echo)\033[0m"
        lines.append("\033[2K" + f"   Ping2 Sonar  : {sonar_status} (Port flank wall distance)")
        lines.append("\033[2K" + "--------------------------------------------------------------------------------")

        # Buoy Perception
        buoy_count = len(obs.buoys)
        lines.append("\033[2K" + f" SEMANTIC BUOYS DETECTED ({buoy_count} visible):")
        if buoy_count > 0:
            # Sort by ascending range and show up to 4
            sorted_buoys = sorted(obs.buoys.values(), key=lambda b: b.range)[:4]
            for b in sorted_buoys:
                lines.append("\033[2K" + f"   • {b.name:<25} Type: {b.buoy_type:<14} Range: {b.range:5.1f} m  Bearing: {b.bearing_deg:+5.1f}°")
            if buoy_count > 4:
                lines.append("\033[2K" + f"     ... and {buoy_count - 4} more buoys")
        else:
            lines.append("\033[2K" + "   (No buoys currently in forward 110° perception cone)")

        lines.append("\033[2K" + "================================================================================")
        lines.append("\033[2K" + f" [STATUS]: {self.last_action}")

        # Write whole frame in one go to prevent flickering
        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()

    def process_key(self, key: str):
        """Maps key input to surge/steer setpoints."""
        now = time.time()
        k = key.lower() if len(key) == 1 else key

        # Surge (Forward)
        if k in ('w', 'z', 'up'):
            self.surge = min(self.MAX_THRUST, self.surge + self.step_size)
            self.last_action = f"Forward thrust increased (+{self.step_size:.1f} N) -> Surge: {self.surge:+.1f} N"

        # Surge (Reverse)
        elif k in ('s', 'down'):
            self.surge = max(self.MIN_THRUST, self.surge - self.step_size)
            self.last_action = f"Reverse thrust applied (-{self.step_size:.1f} N) -> Surge: {self.surge:+.1f} N"

        # Steering (Port / Left)
        # Left turn requires: left motor less thrust, right motor more thrust
        # With T_left = surge + steer, T_right = surge - steer, steering LEFT is steer < 0
        elif k in ('a', 'q', 'left'):
            self.steer = max(self.MIN_THRUST, self.steer - self.step_size)
            self.last_steer_time = now
            self.last_action = f"Steering Port / Left (-{self.step_size:.1f} N) -> Steer: {self.steer:+.1f} N"

        # Steering (Starboard / Right)
        elif k in ('d', 'right'):
            self.steer = min(self.MAX_THRUST, self.steer + self.step_size)
            self.last_steer_time = now
            self.last_action = f"Steering Starboard / Right (+{self.step_size:.1f} N) -> Steer: {self.steer:+.1f} N"

        # Center Steering
        elif k == 'c':
            self.steer = 0.0
            self.last_action = "Steering centered (0.0 N)"

        # Emergency Stop
        elif k in (' ', 'x'):
            self.surge = 0.0
            self.steer = 0.0
            self.last_action = "EMERGENCY STOP — Motors neutralized (0.0 N)"

        # Step size presets
        elif k == '1':
            self.step_size = 2.0
            self.last_action = "Step size set to 2.0 N (Fine mode)"
        elif k == '2':
            self.step_size = 5.0
            self.last_action = "Step size set to 5.0 N (Normal mode)"
        elif k == '3':
            self.step_size = 10.0
            self.last_action = "Step size set to 10.0 N (Fast mode)"
        elif k in ('+', '='):
            self.step_size = min(25.0, self.step_size + 1.0)
            self.last_action = f"Step size increased to {self.step_size:.1f} N"
        elif k in ('-', '_'):
            self.step_size = max(1.0, self.step_size - 1.0)
            self.last_action = f"Step size decreased to {self.step_size:.1f} N"

        # Toggle auto-centering
        elif k == 'm':
            self.auto_center = not self.auto_center
            status = "ENABLED" if self.auto_center else "DISABLED"
            self.last_action = f"Auto-centering rudder {status}"

        # Quit
        elif k in ('esc', 'ctrl_c', 'ctrl_d'):
            self.last_action = "Exiting teleoperation..."
            self.running = False

    def run(self, rate_hz: float = 10.0):
        """Main teleoperation loop (defaults to 10 Hz matching simulation driver)."""
        dt = 1.0 / rate_hz
        self.term.setup()

        # Clear screen once initially
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

        try:
            while self.running:
                loop_start = time.time()

                # 1. Read all buffered keypresses
                while True:
                    key = self.term.get_key(timeout=0.0)
                    if not key:
                        break
                    self.process_key(key)
                    if not self.running:
                        break

                if not self.running:
                    break

                # 2. Auto-centering logic (if enabled)
                now = time.time()
                if self.auto_center and (now - self.last_steer_time > 0.35) and abs(self.steer) > 0.01:
                    decay = 15.0 * dt  # 15 N/s return-to-center rate
                    if self.steer > 0:
                        self.steer = max(0.0, self.steer - decay)
                    else:
                        self.steer = min(0.0, self.steer + decay)

                # 3. Compute differential thruster outputs
                # Left thruster pushes harder to turn right (steer > 0)
                # Right thruster pushes harder to turn left (steer < 0)
                left_cmd = max(self.MIN_THRUST, min(self.MAX_THRUST, self.surge + self.steer))
                right_cmd = max(self.MIN_THRUST, min(self.MAX_THRUST, self.surge - self.steer))

                # 4. Send motor commands to Gazebo
                self.driver.set_thrust(left_cmd, right_cmd)

                # 5. Fetch telemetry and render HUD
                obs = self.driver.get_observation()
                self.render_hud(obs, left_cmd, right_cmd)

                # 6. Sleep to maintain control rate
                elapsed = time.time() - loop_start
                sleep_time = max(0.001, dt - elapsed)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()
            print("\n[BlueBoatTeleop] Stopped vessel motors and exited cleanly.")


def main():
    print("[BlueBoatTeleop] Initializing Gazebo Transport connection...")
    driver = BlueBoatDriver()
    time.sleep(0.5)  # Allow subscriptions to establish
    teleop = BlueBoatTeleop(driver)
    teleop.run()


if __name__ == "__main__":
    main()
