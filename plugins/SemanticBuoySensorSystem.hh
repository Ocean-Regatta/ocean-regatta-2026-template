#ifndef REGATTA_SEMANTIC_BUOY_SENSOR_SYSTEM_HH_
#define REGATTA_SEMANTIC_BUOY_SENSOR_SYSTEM_HH_

#include <gz/sim/System.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/EventManager.hh>
#include <gz/transport/Node.hh>
#include <gz/math/Pose3.hh>
#include <gz/math/Vector3.hh>
#include <gz/msgs/pose_v.pb.h>

#include "buoy.pb.h"

#include <string>
#include <vector>
#include <memory>
#include <random>

namespace regatta
{
  /// \brief Target buoy model detected by the perception system
  struct BuoyTarget
  {
    std::string name;
    std::string type;  // "red", "green", "cardinal_north", "cardinal_south", "cardinal_east", "cardinal_west"
    gz::sim::Entity entity{gz::sim::kNullEntity};
  };

  /// \brief Gazebo Sim System Plugin simulating a semantic perception sensor
  /// for buoys with a tunable observation cone (FOV, range) and measurement uncertainty.
  class SemanticBuoySensorSystem : public gz::sim::System,
                                   public gz::sim::ISystemConfigure,
                                   public gz::sim::ISystemPreUpdate
  {
    public: SemanticBuoySensorSystem();
    public: ~SemanticBuoySensorSystem() override;

    public: void Configure(
        const gz::sim::Entity &_entity,
        const std::shared_ptr<const sdf::Element> &_sdf,
        gz::sim::EntityComponentManager &_ecm,
        gz::sim::EventManager &_eventMgr) override;

    public: void PreUpdate(
        const gz::sim::UpdateInfo &_info,
        gz::sim::EntityComponentManager &_ecm) override;

    private: void DiscoverEntities(gz::sim::EntityComponentManager &_ecm);
    private: static std::string ClassifyBuoyType(const std::string &_nameLower);

    // Configuration parameters
    private: gz::sim::Entity configuredEntity{gz::sim::kNullEntity};
    private: std::string robotName{"blueboat"};
    private: std::string robotLinkName{"base_link"};
    private: gz::math::Pose3d sensorPose{0, 0, 0, 0, 0, 0};
    private: std::string topic{"/blueboat/buoy_observations"};
    private: std::string legacyTopic{"/blueboat/detected_buoys"};
    private: bool publishLegacyPoseV{true};

    private: double updateRate{1.0};           // Publishing frequency in Hz (default 1 Hz = once per second)
    private: double fovDeg{110.0};             // Horizontal observation cone FOV in degrees (+/- 55 deg)
    private: double verticalFovDeg{0.0};       // Vertical observation cone FOV in degrees (0 = unconstrained)
    private: double minRange{0.5};             // Minimum range in meters
    private: double maxRange{35.0};            // Maximum range in meters

    // Measurement uncertainty / noise
    private: bool enableNoise{true};
    private: std::string noiseType{"gaussian"};// "gaussian" or "uniform"
    private: double rangeNoiseStddev{0.25};     // Standard deviation for range noise in meters (~95% in +/-0.5m)
    private: double bearingNoiseDegStddev{1.5};// Standard deviation for bearing noise in degrees (~95% in +/-3 deg)
    private: double rangeNoiseMax{0.5};        // Maximum range noise for uniform distribution (+/-0.5m)
    private: double bearingNoiseMaxDeg{3.0};   // Maximum bearing noise for uniform distribution (+/-3 deg)

    // Explicitly configured buoys (optional)
    private: std::vector<std::pair<std::string, std::string>> configuredBuoys;

    // Runtime state
    private: gz::transport::Node node;
    private: gz::transport::Node::Publisher observationPub;
    private: gz::transport::Node::Publisher legacyPosePub;
    private: gz::sim::Entity robotEntity{gz::sim::kNullEntity};
    private: gz::sim::Entity robotLinkEntity{gz::sim::kNullEntity};
    private: std::vector<BuoyTarget> buoys;
    private: bool entitiesDiscovered{false};
    private: double lastPublishSimTime{-1.0};

    // Random number generation for noise
    private: std::default_random_engine rng;
    private: std::normal_distribution<double> normalDistRange{0.0, 0.25};
    private: std::normal_distribution<double> normalDistBearing{0.0, 0.02618};
    private: std::uniform_real_distribution<double> uniformDistRange{-0.5, 0.5};
    private: std::uniform_real_distribution<double> uniformDistBearing{-0.05236, 0.05236};
  };
}

#endif // REGATTA_SEMANTIC_BUOY_SENSOR_SYSTEM_HH_
