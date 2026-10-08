#ifndef REGATTA_WAVE_SIMULATION_SYSTEM_HH_
#define REGATTA_WAVE_SIMULATION_SYSTEM_HH_

#include <gz/sim/System.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/EventManager.hh>
#include <gz/transport/Node.hh>
#include <gz/math/Vector3.hh>
#include <gz/math/Pose3.hh>
#include <gz/math/Quaternion.hh>
#include <gz/msgs/vector3d.pb.h>

#include <string>
#include <vector>
#include <memory>
#include <chrono>

namespace regatta
{
  /// \brief Parameters for a single sinusoidal or Gerstner wave component
  struct WaveComponent
  {
    double amplitude{0.15};         // Wave amplitude in meters (half wave height)
    double period{4.0};             // Wave period in seconds
    double directionDeg{30.0};      // Propagation direction in degrees (0 = East/+X, 90 = North/+Y)
    double wavelength{0.0};         // Wavelength in meters (if <= 0, computed via dispersion relation)
    double steepness{0.8};          // Gerstner steepness parameter [0.0 = sine wave, 1.0 = trochoidal crest]
    double phase{0.0};              // Phase offset in radians

    // Precomputed internal wave parameters
    double omega{0.0};              // Angular frequency: 2*pi / T
    double k{0.0};                  // Wavenumber: 2*pi / lambda
    double kx{0.0};                 // k * cos(dir)
    double ky{0.0};                 // k * sin(dir)
    double dirRad{0.0};             // Direction in radians

    void ComputeDerivedProperties()
    {
      const double g = 9.80665;
      if (this->period <= 0.001)
        this->period = 4.0;

      this->omega = (2.0 * M_PI) / this->period;
      this->dirRad = this->directionDeg * M_PI / 180.0;

      if (this->wavelength <= 0.001)
      {
        // Deep water dispersion relation: omega^2 = g * k => k = omega^2 / g
        this->k = (this->omega * this->omega) / g;
        this->wavelength = (2.0 * M_PI) / this->k;
      }
      else
      {
        this->k = (2.0 * M_PI) / this->wavelength;
      }

      this->kx = this->k * std::cos(this->dirRad);
      this->ky = this->k * std::sin(this->dirRad);
    }
  };

  /// \brief Instantaneous ocean wave surface state at a horizontal coordinate (x, y)
  struct WaveSurfaceState
  {
    double elevation{0.0};          // Water surface elevation eta(x, y, t) in meters
    double slopeX{0.0};             // d(eta)/dx
    double slopeY{0.0};             // d(eta)/dy
    double velZ{0.0};               // Vertical water velocity d(eta)/dt in m/s
    double orbitalVelX{0.0};        // Horizontal orbital water velocity X in m/s
    double orbitalVelY{0.0};        // Horizontal orbital water velocity Y in m/s
    double roll{0.0};               // Local surface roll angle in radians (around world +X)
    double pitch{0.0};              // Local surface pitch angle in radians (around world +Y)
    gz::math::Vector3d normal{0, 0, 1}; // Unit surface normal vector
  };

  /// \brief State tracking for a floating buoy
  struct BuoyState
  {
    std::string name;
    gz::sim::Entity modelEntity{gz::sim::kNullEntity};
    gz::sim::Entity linkEntity{gz::sim::kNullEntity};

    gz::math::Pose3d initialPose;   // Anchor/nominal pose in world frame

    // Filtered / smoothed dynamic oscillation states
    double currentZ{0.0};
    double velZ{0.0};
    double currentRoll{0.0};
    double velRoll{0.0};
    double currentPitch{0.0};
    double velPitch{0.0};

    bool isDynamic{false};
  };

  /// \brief Gazebo Sim System Plugin for Waves and Ocean Stream Simulation
  class WaveSimulationSystem : public gz::sim::System,
                               public gz::sim::ISystemConfigure,
                               public gz::sim::ISystemPreUpdate
  {
    public: WaveSimulationSystem();
    public: ~WaveSimulationSystem() override;

    public: void Configure(
        const gz::sim::Entity &_entity,
        const std::shared_ptr<const sdf::Element> &_sdf,
        gz::sim::EntityComponentManager &_ecm,
        gz::sim::EventManager &_eventMgr) override;

    public: void PreUpdate(
        const gz::sim::UpdateInfo &_info,
        gz::sim::EntityComponentManager &_ecm) override;

    /// \brief Calculate wave elevation, slopes, and velocities at given position and time
    public: WaveSurfaceState GetWaveState(double _x, double _y, double _time) const;

    private: void DiscoverEntities(gz::sim::EntityComponentManager &_ecm);
    private: void UpdateBuoys(double _simTime, double _dt, gz::sim::EntityComponentManager &_ecm);
    private: void UpdateRobotForces(double _simTime, double _dt, gz::sim::EntityComponentManager &_ecm);

    // Stream / Current configuration
    private: double streamIntensity{0.5};        // Stream speed in m/s
    private: double streamDirectionDeg{45.0};    // Stream direction angle in degrees
    private: gz::math::Vector3d streamVelocity{0, 0, 0}; // Computed current velocity vector (m/s)
    private: double streamLinDrag{25.0};         // Linear stream drag coeff on boat (N / (m/s))
    private: double streamQuadDrag{35.0};        // Quadratic stream drag coeff on boat (N / (m/s)^2)

    // Wave configuration
    private: std::vector<WaveComponent> waves;
    private: double waveHeaveStiffness{100.0};   // Buoyancy heave stiffness on boat (N/m)
    private: double waveHeaveDamping{150.0};     // Heave damping on boat (N*s/m)
    private: double wavePitchStiffness{15.0};    // Wave pitch moment stiffness on boat (N*m/rad)
    private: double wavePitchDamping{30.0};      // Wave pitch damping on boat (N*m*s/rad)
    private: double waveRollStiffness{15.0};     // Wave roll moment stiffness on boat (N*m/rad)
    private: double waveRollDamping{30.0};       // Wave roll damping on boat (N*m*s/rad)
    private: double waveDriftCoeff{30.0};        // Wave drift force coefficient (N / m^2)

    // Buoy motion configuration
    private: double buoyHeaveScale{1.0};         // Scale factor for buoy heave (z) oscillation
    private: double buoyTiltScale{1.0};          // Scale factor for buoy roll/pitch (phi/theta) oscillation
    private: double buoyMooringCompliance{0.08}; // Compliant surge/sway displacement factor with waves
    private: double buoyNaturalFreq{5.5};        // Buoy natural heave/pitch frequency (rad/s)
    private: double buoyDampingRatio{0.75};      // Buoy oscillation damping ratio

    // Target Robot configuration
    private: std::string robotName{"blueboat"};
    private: std::string robotLinkName{"base_link"};
    private: gz::sim::Entity robotEntity{gz::sim::kNullEntity};
    private: gz::sim::Entity robotLinkEntity{gz::sim::kNullEntity};
    private: gz::math::Vector3d robotCoGOffset{0.0, 0.0, 0.0};

    // Buoys
    private: std::vector<std::string> configuredBuoyNames;
    private: std::vector<BuoyState> buoys;

    /// \brief State tracking for waypoints riding the wave surface
    struct WaypointFollowState
    {
      std::string name;
      gz::sim::Entity modelEntity{gz::sim::kNullEntity};
      gz::math::Pose3d initialPose;
      double currentZ{0.0};
      double velZ{0.0};
      double currentRoll{0.0};
      double velRoll{0.0};
      double currentPitch{0.0};
      double velPitch{0.0};
    };
    private: std::vector<WaypointFollowState> trackedWaypoints;
    private: void UpdateWaypoints(double _simTime, double _dt, gz::sim::EntityComponentManager &_ecm);

    // Gazebo Transport
    private: gz::transport::Node node;
    private: gz::transport::Node::Publisher currentPub;
    private: std::string currentTopic{"/ocean_current"};
    private: std::chrono::steady_clock::time_point lastCurrentPubTime;

    private: bool entitiesDiscovered{false};
    private: double prevSimTime{0.0};
  };
}

#endif // REGATTA_WAVE_SIMULATION_SYSTEM_HH_
