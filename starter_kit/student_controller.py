#!/usr/bin/env python3
"""
Ocean Regatta 2026
Starter Kit - Student Strategy Controller
Target: Blue Robotics BlueBoat Autonomous Surface Vessel (Differential Catamaran)

This is the ONLY file evaluated during the regatta.
Develop your autonomous navigation, perception, and control logic here.
"""

from blueboat_driver import BlueBoatDriver, Observation


class StudentController:
    """
    Autonomous navigation controller for the Blue Robotics BlueBoat USV.
    """

    def __init__(self, driver: BlueBoatDriver):
        self.driver = driver
        print("[StudentController] Initialized successfully. Ready for simulation.")

    def step(self, obs: Observation):
        """
        Executed periodically at 10 Hz by BlueBoatDriver.

        Args:
            obs: Observation dataclass containing fresh sensor telemetry:
                 - obs.buoys: Forward semantic buoy detections (name, type, range, bearing, x, y)
                 - obs.ping2: Port single-beam acoustic echosounder (distance, is_valid)
                 - obs.imu: Inertial measurements (yaw, yaw_rate, pitch, roll, linear accelerations)
                 - obs.gps: Metric GNSS Cartesian coordinates (x, y, z)
        """
        # TODO: Implement your perception, planning, and control algorithms here!
        # Set differential motor thrust commands in Newtons (range [-50.0 N, +50.0 N]):
        self.driver.set_thrust(0.0, 0.0)


def main():
    driver = BlueBoatDriver()
    controller = StudentController(driver)
    driver.run(controller.step, rate_hz=10.0)


if __name__ == "__main__":
    main()
