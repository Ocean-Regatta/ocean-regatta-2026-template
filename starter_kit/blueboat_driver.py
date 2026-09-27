#!/usr/bin/env python3
"""
Ocean Regatta
Official BlueBoat Communication Driver & Hardware Abstraction Layer (HAL)

This module handles:
- Connection to Gazebo Transport (gz.transport)
- Protobuf message serialization/deserialization for IMU, GPS, Ping2 (Sonar), and Semantic Buoys
- Safe motor commands with strict physical clamping [-50.0 N, +50.0 N]
- Normalized, clean Python dataclasses for observation data

NOTE FOR PARTICIPANTS:
During automated evaluation on the server, your local copy of this file is NOT used.
The evaluation container loads its own official, immutable version of this driver.
Put all your control and perception algorithms in 'student_controller.py'.
"""

import sys
import math
import time
import signal
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable

# Gazebo Transport binding resolution (Gazebo Jetty -> Harmonic -> Garden)
try:
    from gz.transport14 import Node
except ImportError:
    try:
        from gz.transport13 import Node
    except ImportError:
        try:
            from gz.transport12 import Node
        except ImportError:
            try:
                from gz.transport import Node
            except ImportError:
                raise ImportError(
                    "Gazebo Transport Python bindings not found.
"
                    "Please install 'python3-gz-transport14' (Gazebo Jetty) or run within the provided Docker container."
                )

# Gazebo Protobuf message types resolution (Gazebo Jetty -> Harmonic -> Garden)
try:
    from gz.msgs11.double_pb2 import Double
    from gz.msgs11.imu_pb2 import IMU
    from gz.msgs11.navsat_pb2 import NavSat
    from gz.msgs11.laserscan_pb2 import LaserScan
    from gz.msgs11.pose_v_pb2 import Pose_V
except ImportError:
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


@dataclass
class IMUData:
    """Mesures de la centrale inertielle embarquée (50 Hz)."""
    yaw: float = 0.0              # Cap du drone en radians (-pi à +pi, 0 = Est / Axe X)
    yaw_deg: float = 0.0          # Cap en degrés (-180 à +180)
    yaw_rate: float = 0.0         # Vitesse angulaire de lacet en rad/s (r)
    roll: float = 0.0             # Roulis en radians (phi)
    pitch: float = 0.0            # Tangage en radians (theta)
    linear_accel_x: float = 0.0   # Accélération longitudinale en m/s² (surge)
    linear_accel_y: float = 0.0   # Accélération transversale en m/s² (sway)
    timestamp: float = 0.0


@dataclass
class GPSData:
    """Données du récepteur GNSS/GPS embarqué (5 Hz)."""
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0
    x: float = 0.0                # Position X locale cartésienne (mètres, projetée depuis l'origine 48°N, 4.5°W)
    y: float = 0.0                # Position Y locale cartésienne (mètres)
    is_valid: bool = False
    timestamp: float = 0.0


@dataclass
class Ping2Data:
    """Données de l'échosondeur monofaisceau Ping2 orienté à 90° bâbord (gauche)."""
    distance: float = 999.0       # Distance mesurée à l'obstacle bâbord (mètres, 0.5m à 30m)
    is_valid: bool = False        # Vrai si la mesure est récente (< 0.5s) et dans la portée valide
    timestamp: float = 0.0


@dataclass
class BuoyData:
    """Balise ou marqueur détecté par le capteur sémantique de l'arbitre."""
    name: str
    x: float                      # Coordonnée X relative au BlueBoat (mètres devant si > 0)
    y: float                      # Coordonnée Y relative au BlueBoat (mètres à gauche si > 0, droite si < 0)
    z: float                      # Coordonnée Z relative (mètres)
    distance: float               # Distance euclidienne directe (mètres)
    bearing: float                # Gisement angulaire relatif au cap du bateau (-pi à +pi)


@dataclass
class Observation:
    """État instantané complet perçu par les capteurs du drone."""
    imu: IMUData = field(default_factory=IMUData)
    gps: GPSData = field(default_factory=GPSData)
    ping2: Ping2Data = field(default_factory=Ping2Data)
    buoys: Dict[str, BuoyData] = field(default_factory=dict)
    time: float = 0.0


class BlueBoatDriver:
    """
    Pilote de communication matériel / simulateur pour le BlueBoat.
    Assure les abonnements Gazebo Transport, la conversion des trames Protobuf
    et le bridage de sécurité physique des propulseurs différentiels.
    """
    MAX_THRUST = 50.0  # Force maximale par propulseur en Newtons
    MIN_THRUST = -50.0

    LAT_ORIGIN = 48.0
    LON_ORIGIN = -4.5
    METERS_PER_LAT = 111139.0

    def __init__(self):
        self._node = Node()
        self._running = True

        # Données capteurs internes
        self._imu = IMUData()
        self._gps = GPSData()
        self._ping2 = Ping2Data()
        self._buoys: Dict[str, BuoyData] = {}

        # Facteur de conversion longitude selon la latitude d'origine
        self._meters_per_lon = self.METERS_PER_LAT * math.cos(math.radians(self.LAT_ORIGIN))

        # Éditeurs de commande moteurs
        self._pub_thrust_left = self._node.advertise("/blueboat/cmd_thrust_left", Double)
        self._pub_thrust_right = self._node.advertise("/blueboat/cmd_thrust_right", Double)

        # Abonnements aux topics Gazebo
        self._node.subscribe(IMU, "/blueboat/imu", self._on_imu)
        self._node.subscribe(NavSat, "/blueboat/gps", self._on_gps)
        self._node.subscribe(LaserScan, "/blueboat/ping2_port", self._on_ping2)
        self._node.subscribe(Pose_V, "/blueboat/detected_buoys", self._on_buoys)

        print("[BlueBoatDriver] Connecté aux topics Gazebo Transport (/blueboat/*).")

    # --- Callbacks internes de conversion Protobuf ---

    def _on_imu(self, msg: IMU):
        q = msg.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        sinr_cosp = 2.0 * (q.w * q.x + q.y * q.z)
        cosr_cosp = 1.0 - 2.0 * (q.x * q.x + q.y * q.y)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        sinp = 2.0 * (q.w * q.y - q.z * q.x)
        pitch = math.copysign(math.pi / 2.0, sinp) if abs(sinp) >= 1.0 else math.asin(sinp)

        self._imu = IMUData(
            yaw=yaw,
            yaw_deg=math.degrees(yaw),
            yaw_rate=msg.angular_velocity.z,
            roll=roll,
            pitch=pitch,
            linear_accel_x=msg.linear_acceleration.x,
            linear_accel_y=msg.linear_acceleration.y,
            timestamp=time.time()
        )

    def _on_gps(self, msg: NavSat):
        x = (msg.latitude - self.LAT_ORIGIN) * self.METERS_PER_LAT
        y = (msg.longitude - self.LON_ORIGIN) * self._meters_per_lon
        self._gps = GPSData(
            latitude=msg.latitude,
            longitude=msg.longitude,
            altitude=msg.altitude,
            x=x,
            y=y,
            is_valid=True,
            timestamp=time.time()
        )

    def _on_ping2(self, msg: LaserScan):
        now = time.time()
        if len(msg.ranges) > 0:
            val = float(msg.ranges[0])
            if 0.5 <= val <= 30.0:
                self._ping2 = Ping2Data(distance=val, is_valid=True, timestamp=now)
                return
        # Mesure hors portée
        self._ping2 = Ping2Data(distance=999.0, is_valid=False, timestamp=now)

    def _on_buoys(self, msg: Pose_V):
        new_buoys = {}
        for p in msg.pose:
            bx = p.position.x
            by = p.position.y
            bz = p.position.z
            dist = math.hypot(bx, by)
            bearing = math.atan2(by, bx)
            new_buoys[p.name] = BuoyData(
                name=p.name,
                x=bx,
                y=by,
                z=bz,
                distance=dist,
                bearing=bearing
            )
        self._buoys = new_buoys

    # --- API Utilisateur / Étudiant ---

    def get_observation(self) -> Observation:
        """
        Retourne l'instantané actuel des données capteurs.
        """
        now = time.time()
        ping_valid = self._ping2.is_valid and (now - self._ping2.timestamp < 0.5)
        ping_data = Ping2Data(
            distance=self._ping2.distance if ping_valid else 999.0,
            is_valid=ping_valid,
            timestamp=self._ping2.timestamp
        )

        return Observation(
            imu=self._imu,
            gps=self._gps,
            ping2=ping_data,
            buoys=dict(self._buoys),
            time=now
        )

    def set_thrust(self, left_thrust: float, right_thrust: float):
        """
        Envoie les consignes de poussée différentielle en Newtons.
        Les valeurs sont strictement bridées entre -50.0 N et +50.0 N.
        Toute valeur non numérique (NaN / Inf) est automatiquement neutralisée à 0.0.
        """
        if math.isnan(left_thrust) or math.isinf(left_thrust):
            left_thrust = 0.0
        if math.isnan(right_thrust) or math.isinf(right_thrust):
            right_thrust = 0.0

        clamped_left = max(self.MIN_THRUST, min(self.MAX_THRUST, float(left_thrust)))
        clamped_right = max(self.MIN_THRUST, min(self.MAX_THRUST, float(right_thrust)))

        msg_l = Double()
        msg_l.data = clamped_left
        self._pub_thrust_left.publish(msg_l)

        msg_r = Double()
        msg_r.data = clamped_right
        self._pub_thrust_right.publish(msg_r)

    def stop(self):
        """Coupe immédiatement la poussée des deux moteurs."""
        self._running = False
        self.set_thrust(0.0, 0.0)
        print("[BlueBoatDriver] Arrêt d'urgence des propulseurs.")

    def run(self, step_callback: Callable[[Observation], None], rate_hz: float = 10.0):
        """
        Exécute la boucle principale de contrôle à la fréquence spécifiée (par défaut 10 Hz).
        Gère automatiquement les signaux d'arrêt (SIGINT/SIGTERM) et la coupure moteur.
        
        :param step_callback: Fonction prenant un objet Observation en argument unique.
        :param rate_hz: Fréquence de la boucle de contrôle (Hz).
        """
        dt = 1.0 / rate_hz

        def handle_signal(sig, frame):
            print("\n[BlueBoatDriver] Signal d'arrêt reçu. Arrêt propre du robot...")
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        print(f"[BlueBoatDriver] Démarrage de la boucle de contrôle ({rate_hz} Hz)...")

        while self._running:
            t_start = time.time()
            obs = self.get_observation()

            try:
                step_callback(obs)
            except Exception as e:
                print(f"[BlueBoatDriver] Erreur dans le contrôleur étudiant : {e}", file=sys.stderr)

            elapsed = time.time() - t_start
            sleep_duration = max(0.0, dt - elapsed)
            time.sleep(sleep_duration)
