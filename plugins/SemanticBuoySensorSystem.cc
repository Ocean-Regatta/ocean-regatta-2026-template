#include "SemanticBuoySensorSystem.hh"

#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Link.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/Pose.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/Util.hh>

#include <gz/plugin/Register.hh>

#include <iostream>
#include <iomanip>
#include <cmath>
#include <algorithm>

namespace regatta
{
  SemanticBuoySensorSystem::SemanticBuoySensorSystem()
  {
    std::random_device rd;
    this->rng.seed(rd());
  }

  SemanticBuoySensorSystem::~SemanticBuoySensorSystem() = default;

  void SemanticBuoySensorSystem::Configure(
      const gz::sim::Entity &_entity,
      const std::shared_ptr<const sdf::Element> &_sdf,
      gz::sim::EntityComponentManager &,
      gz::sim::EventManager &)
  {
    this->configuredEntity = _entity;

    if (!_sdf)
      return;

    // 1. Robot identification & sensor mounting pose
    if (_sdf->HasElement("robot_name"))
      this->robotName = _sdf->Get<std::string>("robot_name");
    if (_sdf->HasElement("robot_link"))
      this->robotLinkName = _sdf->Get<std::string>("robot_link");
    if (_sdf->HasElement("sensor_pose"))
      this->sensorPose = _sdf->Get<gz::math::Pose3d>("sensor_pose");
    else if (_sdf->HasElement("pose"))
      this->sensorPose = _sdf->Get<gz::math::Pose3d>("pose");

    // 2. Gazebo Transport topics
    if (_sdf->HasElement("topic"))
      this->topic = _sdf->Get<std::string>("topic");
    if (_sdf->HasElement("legacy_topic"))
      this->legacyTopic = _sdf->Get<std::string>("legacy_topic");
    if (_sdf->HasElement("publish_legacy_pose_v"))
      this->publishLegacyPoseV = _sdf->Get<bool>("publish_legacy_pose_v");

    // 3. Publishing rate (default 1.0 Hz = once per second)
    if (_sdf->HasElement("update_rate"))
      this->updateRate = _sdf->Get<double>("update_rate");
    else if (_sdf->HasElement("rate_hz"))
      this->updateRate = _sdf->Get<double>("rate_hz");

    // 4. Observation cone field of view and range
    if (_sdf->HasElement("fov_deg"))
      this->fovDeg = _sdf->Get<double>("fov_deg");
    else if (_sdf->HasElement("fov"))
    {
      double val = _sdf->Get<double>("fov");
      // If val <= pi, assume radians; otherwise degrees
      this->fovDeg = (val <= M_PI + 1e-4) ? (val * 180.0 / M_PI) : val;
    }

    if (_sdf->HasElement("vertical_fov_deg"))
      this->verticalFovDeg = _sdf->Get<double>("vertical_fov_deg");

    if (_sdf->HasElement("min_range"))
      this->minRange = _sdf->Get<double>("min_range");
    if (_sdf->HasElement("max_range"))
      this->maxRange = _sdf->Get<double>("max_range");

    // 5. Measurement uncertainty (tunable noise)
    if (_sdf->HasElement("enable_noise"))
      this->enableNoise = _sdf->Get<bool>("enable_noise");
    if (_sdf->HasElement("noise_type"))
      this->noiseType = _sdf->Get<std::string>("noise_type");

    if (_sdf->HasElement("range_noise_stddev"))
      this->rangeNoiseStddev = _sdf->Get<double>("range_noise_stddev");
    if (_sdf->HasElement("bearing_noise_deg_stddev"))
      this->bearingNoiseDegStddev = _sdf->Get<double>("bearing_noise_deg_stddev");
    else if (_sdf->HasElement("bearing_noise_stddev"))
    {
      double bNoise = _sdf->Get<double>("bearing_noise_stddev");
      this->bearingNoiseDegStddev = (bNoise <= M_PI) ? (bNoise * 180.0 / M_PI) : bNoise;
    }

    if (_sdf->HasElement("range_noise_max"))
      this->rangeNoiseMax = _sdf->Get<double>("range_noise_max");
    if (_sdf->HasElement("bearing_noise_max_deg"))
      this->bearingNoiseMaxDeg = _sdf->Get<double>("bearing_noise_max_deg");

    if (_sdf->HasElement("random_seed"))
    {
      unsigned int seed = _sdf->Get<unsigned int>("random_seed");
      this->rng.seed(seed);
    }

    // Initialize random distributions
    this->normalDistRange = std::normal_distribution<double>(0.0, this->rangeNoiseStddev);
    double bearingRadStddev = this->bearingNoiseDegStddev * M_PI / 180.0;
    this->normalDistBearing = std::normal_distribution<double>(0.0, bearingRadStddev);

    this->uniformDistRange = std::uniform_real_distribution<double>(-this->rangeNoiseMax, this->rangeNoiseMax);
    double bearingRadMax = this->bearingNoiseMaxDeg * M_PI / 180.0;
    this->uniformDistBearing = std::uniform_real_distribution<double>(-bearingRadMax, bearingRadMax);

    // 6. Explicit buoys if provided in SDF
    if (_sdf->HasElement("buoys"))
    {
      auto buoysElem = _sdf->FindElement("buoys");
      auto bElem = buoysElem->FindElement("buoy");
      while (bElem)
      {
        std::string bName = bElem->Get<std::string>("name");
        std::string bType = "";
        if (bElem->HasAttribute("type"))
          bType = bElem->Get<std::string>("type");
        else if (bElem->HasElement("type"))
          bType = bElem->FindElement("type")->Get<std::string>();
        this->configuredBuoys.push_back({bName, bType});
        bElem = bElem->GetNextElement("buoy");
      }
    }

    // 7. Initialize Gazebo Transport publishers
    this->observationPub = this->node.Advertise<regatta::msgs::BuoyObservationArray>(this->topic);
    if (this->publishLegacyPoseV)
    {
      this->legacyPosePub = this->node.Advertise<gz::msgs::Pose_V>(this->legacyTopic);
    }

    std::cout << "========================================================\n"
              << " [SemanticBuoySensor] Initialized Semantic Buoy Perception System\n"
              << " - Target Robot: " << this->robotName << " (" << this->robotLinkName << ")\n"
              << " - Publishing Topic: " << this->topic << " (" << this->updateRate << " Hz / once per second)\n"
              << " - Observation Cone FOV: " << this->fovDeg << " deg (+/- " << (this->fovDeg * 0.5) << " deg)\n"
              << " - Range Limits: [" << this->minRange << " m, " << this->maxRange << " m]\n"
              << " - Measurement Uncertainty: " << (this->enableNoise ? this->noiseType : "DISABLED") << "\n";
    if (this->enableNoise)
    {
      if (this->noiseType == "uniform")
      {
        std::cout << "   * Range Noise: +/- " << this->rangeNoiseMax << " m\n"
                  << "   * Bearing Noise: +/- " << this->bearingNoiseMaxDeg << " deg\n";
      }
      else
      {
        std::cout << "   * Range Noise StdDev: " << this->rangeNoiseStddev << " m (approx +/- 2*sigma = +/-"
                  << (2.0 * this->rangeNoiseStddev) << " m)\n"
                  << "   * Bearing Noise StdDev: " << this->bearingNoiseDegStddev << " deg (approx +/- 2*sigma = +/-"
                  << (2.0 * this->bearingNoiseDegStddev) << " deg)\n";
      }
    }
    std::cout << "========================================================" << std::endl;
  }

  std::string SemanticBuoySensorSystem::ClassifyBuoyType(const std::string &_nameLower)
  {
    // 1. Cardinal buoys (IALA conventions)
    if (_nameLower.find("cardinal_north") != std::string::npos ||
        (_nameLower.find("cardinal") != std::string::npos && _nameLower.find("north") != std::string::npos))
    {
      return "cardinal_north";
    }
    if (_nameLower.find("cardinal_south") != std::string::npos ||
        (_nameLower.find("cardinal") != std::string::npos && _nameLower.find("south") != std::string::npos))
    {
      return "cardinal_south";
    }
    if (_nameLower.find("cardinal_east") != std::string::npos ||
        (_nameLower.find("cardinal") != std::string::npos && _nameLower.find("east") != std::string::npos))
    {
      return "cardinal_east";
    }
    if (_nameLower.find("cardinal_west") != std::string::npos ||
        (_nameLower.find("cardinal") != std::string::npos && _nameLower.find("west") != std::string::npos))
    {
      return "cardinal_west";
    }

    // 2. Lateral marks (Port / Red cylinder vs Starboard / Green cone)
    if (_nameLower.find("red") != std::string::npos ||
        _nameLower.find("port") != std::string::npos ||
        _nameLower.find("cylinder") != std::string::npos)
    {
      return "red";
    }
    if (_nameLower.find("green") != std::string::npos ||
        _nameLower.find("starboard") != std::string::npos ||
        _nameLower.find("stbd") != std::string::npos ||
        _nameLower.find("cone") != std::string::npos)
    {
      return "green";
    }

    // General fallback for marks containing 'cardinal' or 'buoy'
    if (_nameLower.find("cardinal") != std::string::npos)
    {
      return "cardinal";
    }
    if (_nameLower.find("buoy") != std::string::npos)
    {
      return "generic_buoy";
    }

    return "";
  }

  void SemanticBuoySensorSystem::DiscoverEntities(gz::sim::EntityComponentManager &_ecm)
  {
    // 1. Locate Robot Model & Link
    if (_ecm.Component<gz::sim::components::Model>(this->configuredEntity))
    {
      this->robotEntity = this->configuredEntity;
    }
    else
    {
      this->robotEntity = _ecm.EntityByComponents(
          gz::sim::components::Model(),
          gz::sim::components::Name(this->robotName));
    }

    if (this->robotEntity != gz::sim::kNullEntity)
    {
      gz::sim::Model robotModel(this->robotEntity);
      this->robotLinkEntity = robotModel.LinkByName(_ecm, this->robotLinkName);
      if (this->robotLinkEntity == gz::sim::kNullEntity)
      {
        auto links = robotModel.Links(_ecm);
        if (!links.empty())
          this->robotLinkEntity = links[0];
      }
    }

    if (this->robotEntity == gz::sim::kNullEntity)
    {
      return; // Wait until robot appears in ECM
    }

    // 2. Discover Buoy entities
    this->buoys.clear();

    if (!this->configuredBuoys.empty())
    {
      for (const auto &item : this->configuredBuoys)
      {
        auto ent = _ecm.EntityByComponents(
            gz::sim::components::Model(),
            gz::sim::components::Name(item.first));
        if (ent != gz::sim::kNullEntity)
        {
          BuoyTarget target;
          target.name = item.first;
          target.type = !item.second.empty() ? item.second : ClassifyBuoyType(item.first);
          target.entity = ent;
          this->buoys.push_back(target);
        }
      }
    }
    else
    {
      _ecm.Each<gz::sim::components::Model, gz::sim::components::Name>(
          [&](const gz::sim::Entity &_ent,
              const gz::sim::components::Model *,
              const gz::sim::components::Name *_name) -> bool
          {
            std::string name = _name->Data();
            std::string nameLower = name;
            std::transform(nameLower.begin(), nameLower.end(), nameLower.begin(), ::tolower);

            // Filter out non-buoys
            if (nameLower == "blueboat" || nameLower == "waves" ||
                nameLower == "sun" || nameLower == "water_plane" ||
                nameLower == "finish_line" || nameLower.find("pier") != std::string::npos ||
                nameLower.find("waypoint") != std::string::npos)
            {
              return true;
            }

            std::string bType = ClassifyBuoyType(nameLower);
            if (!bType.empty())
            {
              BuoyTarget target;
              target.name = name;
              target.type = bType;
              target.entity = _ent;
              this->buoys.push_back(target);
            }
            return true;
          });
    }

    if (!this->buoys.empty())
    {
      this->entitiesDiscovered = true;
      std::cout << " [SemanticBuoySensor] Registered " << this->buoys.size()
                << " buoy target(s) for semantic perception tracking:\n";
      for (const auto &b : this->buoys)
      {
        std::cout << "   * " << b.name << " (type: " << b.type << ")\n";
      }
    }
  }

  void SemanticBuoySensorSystem::PreUpdate(
      const gz::sim::UpdateInfo &_info,
      gz::sim::EntityComponentManager &_ecm)
  {
    if (_info.paused)
      return;

    if (!this->entitiesDiscovered)
    {
      this->DiscoverEntities(_ecm);
      if (!this->entitiesDiscovered)
        return;
    }

    double simTime = std::chrono::duration<double>(_info.simTime).count();

    // Check update rate (1.0 Hz = once per second)
    double period = 1.0 / std::max(0.001, this->updateRate);
    if (this->lastPublishSimTime >= 0.0 && (simTime - this->lastPublishSimTime) < period - 1e-6)
    {
      return;
    }
    this->lastPublishSimTime = simTime;

    // 1. Compute Robot / Sensor World Pose
    gz::sim::Entity refEntity = (this->robotLinkEntity != gz::sim::kNullEntity)
                                    ? this->robotLinkEntity
                                    : this->robotEntity;
    auto robotPose = gz::sim::worldPose(refEntity, _ecm);
    gz::math::Pose3d sensorWorldPose = robotPose * this->sensorPose;

    // 2. Prepare message
    regatta::msgs::BuoyObservationArray msg;
    msg.set_timestamp(simTime);

    gz::msgs::Pose_V legacyPoseMsg;

    double halfFovRad = (this->fovDeg * M_PI / 180.0) * 0.5;
    double halfVertFovRad = (this->verticalFovDeg * M_PI / 180.0) * 0.5;

    // 3. Evaluate each buoy against observation cone
    for (const auto &buoy : this->buoys)
    {
      auto buoyPose = gz::sim::worldPose(buoy.entity, _ecm);

      // Relative vector in world frame
      gz::math::Vector3d relWorld = buoyPose.Pos() - sensorWorldPose.Pos();

      // Transform into sensor frame (+X: Surge/Forward, +Y: Sway/Port, +Z: Heave/Up)
      gz::math::Vector3d relSensor = sensorWorldPose.Rot().Inverse().RotateVector(relWorld);

      double x_true = relSensor.X();
      double y_true = relSensor.Y();
      double z_true = relSensor.Z();

      // 2D Euclidean range and relative bearing
      double range_true = std::hypot(x_true, y_true);
      double bearing_true = std::atan2(y_true, x_true); // [-pi, +pi]

      // Target must be ahead of the sensor (x > 0)
      if (x_true <= 0.0)
        continue;

      // Range limits check
      if (range_true < this->minRange || range_true > this->maxRange)
        continue;

      // Horizontal FOV observation cone check
      if (std::abs(bearing_true) > halfFovRad)
        continue;

      // Optional vertical FOV check
      if (this->verticalFovDeg > 0.0)
      {
        double vertAngle = std::abs(std::atan2(z_true, range_true));
        if (vertAngle > halfVertFovRad)
          continue;
      }

      // Add measurement uncertainty (noise)
      double range_meas = range_true;
      double bearing_meas = bearing_true;

      if (this->enableNoise)
      {
        if (this->noiseType == "uniform")
        {
          range_meas += this->uniformDistRange(this->rng);
          bearing_meas += this->uniformDistBearing(this->rng);
        }
        else // default: gaussian
        {
          range_meas += this->normalDistRange(this->rng);
          bearing_meas += this->normalDistBearing(this->rng);
        }
      }

      // Clamping and angular wrap-around
      range_meas = std::max(0.01, range_meas);
      bearing_meas = std::atan2(std::sin(bearing_meas), std::cos(bearing_meas));
      double bearing_deg = bearing_meas * 180.0 / M_PI;

      double x_meas = range_meas * std::cos(bearing_meas);
      double y_meas = range_meas * std::sin(bearing_meas);
      double z_meas = z_true;

      // Populate custom Protobuf message
      auto *bObs = msg.add_buoys();
      bObs->set_name(buoy.name);
      bObs->set_buoy_type(buoy.type);
      bObs->set_type(buoy.type);
      bObs->set_range(range_meas);
      bObs->set_bearing(bearing_meas);
      bObs->set_bearing_deg(bearing_deg);
      bObs->set_x(x_meas);
      bObs->set_y(y_meas);
      bObs->set_z(z_meas);
      bObs->set_range_true(range_true);
      bObs->set_bearing_true(bearing_true);

      // Legacy Pose_V message support
      if (this->publishLegacyPoseV)
      {
        auto *p = legacyPoseMsg.add_pose();
        p->set_name(buoy.name);
        p->mutable_position()->set_x(x_meas);
        p->mutable_position()->set_y(y_meas);
        p->mutable_position()->set_z(z_meas);
      }
    }

    // 4. Publish messages over Gazebo Transport
    this->observationPub.Publish(msg);

    if (this->publishLegacyPoseV)
    {
      this->legacyPosePub.Publish(legacyPoseMsg);
    }
  }
}

// Register the Gazebo Sim system plugin
GZ_ADD_PLUGIN(
    regatta::SemanticBuoySensorSystem,
    gz::sim::System,
    regatta::SemanticBuoySensorSystem::ISystemConfigure,
    regatta::SemanticBuoySensorSystem::ISystemPreUpdate)

GZ_ADD_PLUGIN_ALIAS(regatta::SemanticBuoySensorSystem, "regatta::SemanticBuoySensorSystem")
