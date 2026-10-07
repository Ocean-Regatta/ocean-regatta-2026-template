#include "WaveSimulationSystem.hh"

#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Link.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/Pose.hh>
#include <gz/sim/components/PoseCmd.hh>
#include <gz/sim/components/LinearVelocity.hh>
#include <gz/sim/components/AngularVelocity.hh>
#include <gz/sim/components/ExternalWorldWrenchCmd.hh>
#include <gz/sim/components/Static.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/Link.hh>
#include <gz/sim/Util.hh>

#include <gz/plugin/Register.hh>
#include <gz/msgs/vector3d.pb.h>

#include <iostream>
#include <cmath>
#include <algorithm>

namespace regatta
{
  WaveSimulationSystem::WaveSimulationSystem()
  {
    this->lastCurrentPubTime = std::chrono::steady_clock::now();
  }

  WaveSimulationSystem::~WaveSimulationSystem() = default;

  void WaveSimulationSystem::Configure(
      const gz::sim::Entity &_entity,
      const std::shared_ptr<const sdf::Element> &_sdf,
      gz::sim::EntityComponentManager &_ecm,
      gz::sim::EventManager &)
  {
    // Default primary wave component
    WaveComponent primaryWave;
    primaryWave.amplitude = 0.15;
    primaryWave.period = 4.0;
    primaryWave.directionDeg = 30.0;
    primaryWave.steepness = 0.8;

    if (_sdf)
    {
      // 1. Stream / Current configuration
      if (_sdf->HasElement("stream_intensity"))
        this->streamIntensity = _sdf->Get<double>("stream_intensity");
      else if (_sdf->HasElement("stream") && _sdf->FindElement("stream")->HasElement("intensity"))
        this->streamIntensity = _sdf->FindElement("stream")->Get<double>("intensity");

      if (_sdf->HasElement("stream_direction_deg"))
        this->streamDirectionDeg = _sdf->Get<double>("stream_direction_deg");
      else if (_sdf->HasElement("stream_direction"))
        this->streamDirectionDeg = _sdf->Get<double>("stream_direction");
      else if (_sdf->HasElement("stream") && _sdf->FindElement("stream")->HasElement("direction_deg"))
        this->streamDirectionDeg = _sdf->FindElement("stream")->Get<double>("direction_deg");
      else if (_sdf->HasElement("stream") && _sdf->FindElement("stream")->HasElement("direction"))
        this->streamDirectionDeg = _sdf->FindElement("stream")->Get<double>("direction");

      if (_sdf->HasElement("stream_lin_drag"))
        this->streamLinDrag = _sdf->Get<double>("stream_lin_drag");
      if (_sdf->HasElement("stream_quad_drag"))
        this->streamQuadDrag = _sdf->Get<double>("stream_quad_drag");

      // 2. Wave configuration
      if (_sdf->HasElement("wave_amplitude"))
        primaryWave.amplitude = _sdf->Get<double>("wave_amplitude");
      if (_sdf->HasElement("wave_period"))
        primaryWave.period = _sdf->Get<double>("wave_period");
      if (_sdf->HasElement("wave_direction_deg"))
        primaryWave.directionDeg = _sdf->Get<double>("wave_direction_deg");
      else if (_sdf->HasElement("wave_direction"))
        primaryWave.directionDeg = _sdf->Get<double>("wave_direction");
      if (_sdf->HasElement("wave_steepness"))
        primaryWave.steepness = _sdf->Get<double>("wave_steepness");
      if (_sdf->HasElement("wave_wavelength"))
        primaryWave.wavelength = _sdf->Get<double>("wave_wavelength");

      // Multiple wave components if <wave> or <waves> specified
      if (_sdf->HasElement("waves"))
      {
        this->waves.clear();
        auto wavesElem = _sdf->FindElement("waves");
        auto waveElem = wavesElem->FindElement("wave");
        while (waveElem)
        {
          WaveComponent comp;
          if (waveElem->HasElement("amplitude"))
            comp.amplitude = waveElem->Get<double>("amplitude");
          if (waveElem->HasElement("period"))
            comp.period = waveElem->Get<double>("period");
          if (waveElem->HasElement("direction_deg"))
            comp.directionDeg = waveElem->Get<double>("direction_deg");
          else if (waveElem->HasElement("direction"))
            comp.directionDeg = waveElem->Get<double>("direction");
          if (waveElem->HasElement("wavelength"))
            comp.wavelength = waveElem->Get<double>("wavelength");
          if (waveElem->HasElement("steepness"))
            comp.steepness = waveElem->Get<double>("steepness");
          if (waveElem->HasElement("phase"))
            comp.phase = waveElem->Get<double>("phase");

          comp.ComputeDerivedProperties();
          this->waves.push_back(comp);
          waveElem = waveElem->GetNextElement("wave");
        }
      }
      else if (_sdf->HasElement("wave"))
      {
        this->waves.clear();
        auto waveElem = _sdf->FindElement("wave");
        while (waveElem)
        {
          WaveComponent comp;
          if (waveElem->HasElement("amplitude"))
            comp.amplitude = waveElem->Get<double>("amplitude");
          if (waveElem->HasElement("period"))
            comp.period = waveElem->Get<double>("period");
          if (waveElem->HasElement("direction_deg"))
            comp.directionDeg = waveElem->Get<double>("direction_deg");
          else if (waveElem->HasElement("direction"))
            comp.directionDeg = waveElem->Get<double>("direction");
          if (waveElem->HasElement("wavelength"))
            comp.wavelength = waveElem->Get<double>("wavelength");
          if (waveElem->HasElement("steepness"))
            comp.steepness = waveElem->Get<double>("steepness");
          if (waveElem->HasElement("phase"))
            comp.phase = waveElem->Get<double>("phase");

          comp.ComputeDerivedProperties();
          this->waves.push_back(comp);
          waveElem = waveElem->GetNextElement("wave");
        }
      }

      // 3. Robot target
      if (_sdf->HasElement("robot_name"))
        this->robotName = _sdf->Get<std::string>("robot_name");
      if (_sdf->HasElement("robot_link"))
        this->robotLinkName = _sdf->Get<std::string>("robot_link");
      if (_sdf->HasElement("robot_cog_offset"))
        this->robotCoGOffset = _sdf->Get<gz::math::Vector3d>("robot_cog_offset");

      if (_sdf->HasElement("wave_heave_stiffness"))
        this->waveHeaveStiffness = _sdf->Get<double>("wave_heave_stiffness");
      if (_sdf->HasElement("wave_heave_damping"))
        this->waveHeaveDamping = _sdf->Get<double>("wave_heave_damping");
      if (_sdf->HasElement("wave_pitch_stiffness"))
        this->wavePitchStiffness = _sdf->Get<double>("wave_pitch_stiffness");
      if (_sdf->HasElement("wave_pitch_damping"))
        this->wavePitchDamping = _sdf->Get<double>("wave_pitch_damping");
      if (_sdf->HasElement("wave_roll_stiffness"))
        this->waveRollStiffness = _sdf->Get<double>("wave_roll_stiffness");
      if (_sdf->HasElement("wave_roll_damping"))
        this->waveRollDamping = _sdf->Get<double>("wave_roll_damping");
      if (_sdf->HasElement("wave_drift_coeff"))
        this->waveDriftCoeff = _sdf->Get<double>("wave_drift_coeff");

      // 4. Buoy oscillation scaling
      if (_sdf->HasElement("buoy_heave_amplitude_scale"))
        this->buoyHeaveScale = _sdf->Get<double>("buoy_heave_amplitude_scale");
      if (_sdf->HasElement("buoy_tilt_scale"))
        this->buoyTiltScale = _sdf->Get<double>("buoy_tilt_scale");
      if (_sdf->HasElement("buoy_mooring_compliance"))
        this->buoyMooringCompliance = _sdf->Get<double>("buoy_mooring_compliance");
      if (_sdf->HasElement("buoy_natural_freq"))
        this->buoyNaturalFreq = _sdf->Get<double>("buoy_natural_freq");
      if (_sdf->HasElement("buoy_damping_ratio"))
        this->buoyDampingRatio = _sdf->Get<double>("buoy_damping_ratio");

      // 5. Explicitly specified buoys (optional)
      if (_sdf->HasElement("buoys"))
      {
        auto buoysElem = _sdf->FindElement("buoys");
        auto bElem = buoysElem->FindElement("buoy");
        while (bElem)
        {
          this->configuredBuoyNames.push_back(bElem->Get<std::string>());
          bElem = bElem->GetNextElement("buoy");
        }
      }
    }

    // If no multi-wave components were parsed, use primary wave
    if (this->waves.empty())
    {
      primaryWave.ComputeDerivedProperties();
      this->waves.push_back(primaryWave);
    }

    // Compute stream velocity vector from intensity and direction
    double dirRad = this->streamDirectionDeg * M_PI / 180.0;
    this->streamVelocity.X(this->streamIntensity * std::cos(dirRad));
    this->streamVelocity.Y(this->streamIntensity * std::sin(dirRad));
    this->streamVelocity.Z(0.0);

    // Advertise /ocean_current topic
    this->currentPub = this->node.Advertise<gz::msgs::Vector3d>(this->currentTopic);

    std::cout << "========================================================\n"
              << " [WaveSimulationSystem] Ocean Environment Initialized\n"
              << " - Stream Intensity: " << this->streamIntensity << " m/s\n"
              << " - Stream Direction: " << this->streamDirectionDeg << " deg (Vector: "
              << this->streamVelocity.X() << ", " << this->streamVelocity.Y() << ", 0.0)\n"
              << " - Number of Wave Components: " << this->waves.size() << "\n";
    for (size_t i = 0; i < this->waves.size(); ++i)
    {
      const auto &w = this->waves[i];
      std::cout << "   * Wave #" << (i + 1) << ": Amp=" << w.amplitude << "m, Period=" << w.period
                << "s (lambda=" << w.wavelength << "m), Dir=" << w.directionDeg << " deg\n";
    }
    std::cout << " - Target Robot: " << this->robotName << " (" << this->robotLinkName << ")\n"
              << " - Buoy Heave Scale: " << this->buoyHeaveScale
              << ", Tilt Scale: " << this->buoyTiltScale << "\n"
              << "========================================================" << std::endl;
  }

  void WaveSimulationSystem::DiscoverEntities(gz::sim::EntityComponentManager &_ecm)
  {
    // 1. Locate Robot
    this->robotEntity = _ecm.EntityByComponents(
        gz::sim::components::Model(),
        gz::sim::components::Name(this->robotName));

    if (this->robotEntity != gz::sim::kNullEntity)
    {
      gz::sim::Model robotModel(this->robotEntity);
      this->robotLinkEntity = robotModel.LinkByName(_ecm, this->robotLinkName);
    }

    if (this->robotEntity == gz::sim::kNullEntity || this->robotLinkEntity == gz::sim::kNullEntity)
    {
      // Wait until robot model and base link appear in ECM
      return;
    }

    // 2. Discover Buoys
    this->buoys.clear();

    if (!this->configuredBuoyNames.empty())
    {
      for (const auto &name : this->configuredBuoyNames)
      {
        auto ent = _ecm.EntityByComponents(
            gz::sim::components::Model(),
            gz::sim::components::Name(name));
        if (ent != gz::sim::kNullEntity)
        {
          BuoyState b;
          b.name = name;
          b.modelEntity = ent;
          gz::sim::Model m(ent);
          auto links = m.Links(_ecm);
          if (!links.empty()) b.linkEntity = links[0];
          b.initialPose = gz::sim::worldPose(ent, _ecm);
          b.currentZ = b.initialPose.Pos().Z();
          b.currentRoll = b.initialPose.Rot().Roll();
          b.currentPitch = b.initialPose.Rot().Pitch();

          if (auto staticComp = _ecm.Component<gz::sim::components::Static>(ent))
            b.isDynamic = !staticComp->Data();

          this->buoys.push_back(b);
        }
      }
    }
    else
    {
      // Auto-discover models representing buoys
      _ecm.Each<gz::sim::components::Model, gz::sim::components::Name>(
          [&](const gz::sim::Entity &_entity,
              const gz::sim::components::Model *,
              const gz::sim::components::Name *_name) -> bool
          {
            std::string nameLower = _name->Data();
            std::transform(nameLower.begin(), nameLower.end(), nameLower.begin(), ::tolower);

            // Filter out non-buoys
            if (nameLower == "blueboat" || nameLower == "water_plane" ||
                nameLower == "finish_line" || nameLower.find("pier") != std::string::npos ||
                nameLower.find("waypoint") != std::string::npos)
            {
              return true;
            }

            // Match buoys, channel gates, and cardinal markers
            if (nameLower.find("buoy") != std::string::npos ||
                nameLower.find("gate_port") != std::string::npos ||
                nameLower.find("gate_starboard") != std::string::npos ||
                nameLower.find("cardinal") != std::string::npos)
            {
              BuoyState b;
              b.name = _name->Data();
              b.modelEntity = _entity;
              gz::sim::Model m(_entity);
              auto links = m.Links(_ecm);
              if (!links.empty()) b.linkEntity = links[0];
              b.initialPose = gz::sim::worldPose(_entity, _ecm);
              b.currentZ = b.initialPose.Pos().Z();
              b.currentRoll = b.initialPose.Rot().Roll();
              b.currentPitch = b.initialPose.Rot().Pitch();

              if (auto staticComp = _ecm.Component<gz::sim::components::Static>(_entity))
                b.isDynamic = !staticComp->Data();

              this->buoys.push_back(b);
            }
            return true;
          });
    }

    std::cout << " [WaveSimulationSystem] Successfully registered " << this->buoys.size()
              << " buoy(s) for wave oscillation & buoyancy tracking:\n";
    for (const auto &b : this->buoys)
    {
      std::cout << "   - '" << b.name << "' at ("
                << b.initialPose.Pos().X() << ", "
                << b.initialPose.Pos().Y() << ", "
                << b.initialPose.Pos().Z() << ")\n";
    }

    // 3. Discover Waypoints to ride wave surface
    this->trackedWaypoints.clear();
    _ecm.Each<gz::sim::components::Model, gz::sim::components::Name>(
        [&](const gz::sim::Entity &_entity,
            const gz::sim::components::Model *,
            const gz::sim::components::Name *_name) -> bool
        {
          std::string nameLower = _name->Data();
          std::transform(nameLower.begin(), nameLower.end(), nameLower.begin(), ::tolower);

          if (nameLower.find("waypoint") != std::string::npos)
          {
            WaypointFollowState wp;
            wp.name = _name->Data();
            wp.modelEntity = _entity;
            wp.initialPose = gz::sim::worldPose(_entity, _ecm);
            wp.currentZ = wp.initialPose.Pos().Z();
            wp.currentRoll = wp.initialPose.Rot().Roll();
            wp.currentPitch = wp.initialPose.Rot().Pitch();
            this->trackedWaypoints.push_back(wp);
          }
          return true;
        });

    if (!this->trackedWaypoints.empty())
    {
      std::cout << " [WaveSimulationSystem] Successfully registered " << this->trackedWaypoints.size()
                << " waypoint(s) to ride wave surface:\n";
      for (const auto &w : this->trackedWaypoints)
      {
        std::cout << "   - '" << w.name << "' at ("
                  << w.initialPose.Pos().X() << ", "
                  << w.initialPose.Pos().Y() << ", "
                  << w.initialPose.Pos().Z() << ")\n";
      }
    }

    this->entitiesDiscovered = true;
  }

  WaveSurfaceState WaveSimulationSystem::GetWaveState(double _x, double _y, double _time) const
  {
    WaveSurfaceState state;
    state.elevation = 0.0;
    state.slopeX = 0.0;
    state.slopeY = 0.0;
    state.velZ = 0.0;
    state.orbitalVelX = 0.0;
    state.orbitalVelY = 0.0;

    for (const auto &w : this->waves)
    {
      // Phase phi = kx * x + ky * y - omega * t + phase0
      double phase = w.kx * _x + w.ky * _y - w.omega * _time + w.phase;
      double cosP = std::cos(phase);
      double sinP = std::sin(phase);

      // Gerstner / Airy wave elevation: eta = A * cos(phi)
      state.elevation += w.amplitude * cosP;

      // Spatial slopes: d(eta)/dx and d(eta)/dy
      state.slopeX -= w.amplitude * w.kx * sinP;
      state.slopeY -= w.amplitude * w.ky * sinP;

      // Vertical water particle velocity: d(eta)/dt = A * omega * sin(phi)
      state.velZ += w.amplitude * w.omega * sinP;

      // Horizontal water particle velocities
      state.orbitalVelX += w.amplitude * w.omega * std::cos(w.dirRad) * cosP;
      state.orbitalVelY += w.amplitude * w.omega * std::sin(w.dirRad) * cosP;
    }

    // Local wave surface pitch and roll angles
    state.pitch = -std::atan(state.slopeX);
    state.roll = std::atan(state.slopeY);

    // Surface normal vector
    double normDenom = std::sqrt(1.0 + state.slopeX * state.slopeX + state.slopeY * state.slopeY);
    state.normal.Set(-state.slopeX / normDenom, -state.slopeY / normDenom, 1.0 / normDenom);

    return state;
  }

  void WaveSimulationSystem::PreUpdate(
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
    double dt = std::chrono::duration<double>(_info.dt).count();
    if (dt <= 0.0) dt = 0.002;

    // 1. Update wave buoyancy and oscillations for all buoys
    this->UpdateBuoys(simTime, dt, _ecm);

    // 2. Apply stream and wave excitation forces to the boat
    this->UpdateRobotForces(simTime, dt, _ecm);

    // 3. Update waypoint elevation and tilt to ride wave surface
    this->UpdateWaypoints(simTime, dt, _ecm);

    // 3. Publish stream velocity to /ocean_current for Hydrodynamics plugin compatibility
    auto now = std::chrono::steady_clock::now();
    if (std::chrono::duration<double>(now - this->lastCurrentPubTime).count() >= 0.1)
    {
      gz::msgs::Vector3d currentMsg;
      currentMsg.set_x(this->streamVelocity.X());
      currentMsg.set_y(this->streamVelocity.Y());
      currentMsg.set_z(this->streamVelocity.Z());
      this->currentPub.Publish(currentMsg);
      this->lastCurrentPubTime = now;
    }

    this->prevSimTime = simTime;
  }

  void WaveSimulationSystem::UpdateBuoys(
      double _simTime, double _dt,
      gz::sim::EntityComponentManager &_ecm)
  {
    for (auto &buoy : this->buoys)
    {
      double x0 = buoy.initialPose.Pos().X();
      double y0 = buoy.initialPose.Pos().Y();
      double z0 = buoy.initialPose.Pos().Z();

      // Compute local wave surface properties at buoy anchor position
      WaveSurfaceState state = this->GetWaveState(x0, y0, _simTime);

      // Desired vertical oscillation (heave) following wave surface elevation
      double targetZ = z0 + state.elevation * this->buoyHeaveScale;

      // Desired angular tilts (roll and pitch) following local wave slope
      double targetRoll = buoy.initialPose.Rot().Roll() + state.roll * this->buoyTiltScale;
      double targetPitch = buoy.initialPose.Rot().Pitch() + state.pitch * this->buoyTiltScale;

      // Zero-lag analytical buoyant tracking strictly sticking to the wave surface
      buoy.currentZ = targetZ;
      buoy.currentRoll = targetRoll;
      buoy.currentPitch = targetPitch;

      // Keep fixed moored position in horizontal plane
      double targetX = x0;
      double targetY = y0;

      // Build updated 6-DOF world pose
      gz::math::Pose3d newPose(
          targetX,
          targetY,
          buoy.currentZ,
          buoy.currentRoll,
          buoy.currentPitch,
          buoy.initialPose.Rot().Yaw());

      // 1. Command model world pose through Gazebo Sim physics API
      gz::sim::Model model(buoy.modelEntity);
      model.SetWorldPoseCmd(_ecm, newPose);

      // 2. Directly update components::Pose on the model entity
      if (auto poseComp = _ecm.Component<gz::sim::components::Pose>(buoy.modelEntity))
      {
        *poseComp = gz::sim::components::Pose(newPose);
      }
      else
      {
        _ecm.CreateComponent(buoy.modelEntity, gz::sim::components::Pose(newPose));
      }

      // 3. If model contains a link, update link's Pose component if needed
      if (buoy.linkEntity != gz::sim::kNullEntity)
      {
        // Relative pose of canonical link is identity (0,0,0) so it follows model
      }
    }
  }

  void WaveSimulationSystem::UpdateWaypoints(
      double _simTime, double _dt,
      gz::sim::EntityComponentManager &_ecm)
  {
    for (auto &wp : this->trackedWaypoints)
    {
      double x0 = wp.initialPose.Pos().X();
      double y0 = wp.initialPose.Pos().Y();
      double z0 = wp.initialPose.Pos().Z();

      // Compute local wave surface properties at waypoint fixed anchor coordinate
      WaveSurfaceState state = this->GetWaveState(x0, y0, _simTime);

      // Target elevation rides the wave surface directly
      double targetZ = z0 + state.elevation * this->buoyHeaveScale;
      double targetRoll = wp.initialPose.Rot().Roll() + state.roll * 0.4;
      double targetPitch = wp.initialPose.Rot().Pitch() + state.pitch * 0.4;

      // Zero-lag analytical buoyant tracking strictly sticking to the wave surface
      wp.currentZ = targetZ;
      wp.currentRoll = targetRoll;
      wp.currentPitch = targetPitch;

      // Build 6-DOF world pose: KEEP (x0, y0) strictly fixed, only oscillate Z and wave tilt!
      gz::math::Pose3d newPose(
          x0,
          y0,
          wp.currentZ,
          wp.currentRoll,
          wp.currentPitch,
          wp.initialPose.Rot().Yaw());

      // 1. Command model world pose through Gazebo Sim physics API
      gz::sim::Model model(wp.modelEntity);
      model.SetWorldPoseCmd(_ecm, newPose);

      // 2. Directly update components::Pose on the model entity
      if (auto poseComp = _ecm.Component<gz::sim::components::Pose>(wp.modelEntity))
      {
        *poseComp = gz::sim::components::Pose(newPose);
      }
      else
      {
        _ecm.CreateComponent(wp.modelEntity, gz::sim::components::Pose(newPose));
      }
    }
  }

  void WaveSimulationSystem::UpdateRobotForces(
      double _simTime, double _dt,
      gz::sim::EntityComponentManager &_ecm)
  {
    if (this->robotLinkEntity == gz::sim::kNullEntity)
      return;

    // 1. Get current world pose of the vessel base link
    auto boatPose = gz::sim::worldPose(this->robotLinkEntity, _ecm);
    gz::math::Vector3d worldCoG = boatPose.Pos() + boatPose.Rot().RotateVector(this->robotCoGOffset);
    double boatX = worldCoG.X();
    double boatY = worldCoG.Y();
    double boatZ = worldCoG.Z();
    double boatYaw = boatPose.Rot().Yaw();

    // 2. Get current velocity of the vessel
    gz::math::Vector3d linVel = gz::math::Vector3d::Zero;
    if (auto velComp = _ecm.Component<gz::sim::components::LinearVelocity>(this->robotLinkEntity))
      linVel = velComp->Data();

    gz::math::Vector3d angVel = gz::math::Vector3d::Zero;
    if (auto aVelComp = _ecm.Component<gz::sim::components::AngularVelocity>(this->robotLinkEntity))
      angVel = aVelComp->Data();

    // 3. Calculate local wave surface state at boat center of gravity
    WaveSurfaceState waveState = this->GetWaveState(boatX, boatY, _simTime);

    // 4. Wave-induced dynamic buoyant heave force
    // Baseline water line is at z ~ 0.05 m
    double deltaZ = waveState.elevation - (boatZ - 0.05);
    double relVelZ = waveState.velZ - linVel.Z();
    double heaveForce = this->waveHeaveStiffness * deltaZ + this->waveHeaveDamping * relVelZ;
    heaveForce = std::clamp(heaveForce, -50.0, 50.0);

    // 5. Wave-induced pitch and roll excitation moments (heading-aware in body frame)
    gz::math::Quaterniond waveRot = gz::math::Quaterniond::EulerToQuaternion(
        waveState.roll, waveState.pitch, boatYaw);
    gz::math::Quaterniond errRot = boatPose.Rot().Inverse() * waveRot;
    double deltaRoll = errRot.Roll();
    double deltaPitch = errRot.Pitch();

    // Angular velocity in body frame
    gz::math::Vector3d bodyAngVel = boatPose.Rot().Inverse().RotateVector(angVel);

    double rollTorqueBody = this->waveRollStiffness * deltaRoll - this->waveRollDamping * bodyAngVel.X();
    rollTorqueBody = std::clamp(rollTorqueBody, -20.0, 20.0);

    double pitchTorqueBody = this->wavePitchStiffness * deltaPitch - this->wavePitchDamping * bodyAngVel.Y();
    pitchTorqueBody = std::clamp(pitchTorqueBody, -20.0, 20.0);

    // Rotate body moments into world coordinates for application
    gz::math::Vector3d totalTorque = boatPose.Rot().RotateVector(
        gz::math::Vector3d(rollTorqueBody, pitchTorqueBody, 0.0));

    // 6. Wave second-order drift force
    gz::math::Vector3d driftForce(0, 0, 0);
    for (const auto &w : this->waves)
    {
      double dForceMag = this->waveDriftCoeff * (w.amplitude * w.amplitude);
      driftForce.X(driftForce.X() + dForceMag * std::cos(w.dirRad));
      driftForce.Y(driftForce.Y() + dForceMag * std::sin(w.dirRad));
    }

    // 7. Stream / Ocean Current hydrodynamic drag force
    // Stream pushes the vessel along streamVelocity relative to vessel velocity
    gz::math::Vector3d relCurrentVel(
        this->streamVelocity.X() - linVel.X(),
        this->streamVelocity.Y() - linVel.Y(),
        0.0);

    double relSpeed = relCurrentVel.Length();
    gz::math::Vector3d streamForce =
        this->streamLinDrag * relCurrentVel +
        this->streamQuadDrag * relSpeed * relCurrentVel;

    // Clamp stream force to safe physical bounds
    streamForce.X(std::clamp(streamForce.X(), -180.0, 180.0));
    streamForce.Y(std::clamp(streamForce.Y(), -180.0, 180.0));

    // 8. Total wrench applied to vessel base_link in world coordinates at CoG offset
    gz::math::Vector3d totalForce(
        streamForce.X() + driftForce.X(),
        streamForce.Y() + driftForce.Y(),
        heaveForce);

    // Apply via Link AddWorldWrench at vessel CoG offset
    gz::sim::Link link(this->robotLinkEntity);
    link.AddWorldWrench(_ecm, totalForce, totalTorque, this->robotCoGOffset);
  }
}

// Register the plugin with Gazebo Sim
GZ_ADD_PLUGIN(
    regatta::WaveSimulationSystem,
    gz::sim::System,
    regatta::WaveSimulationSystem::ISystemConfigure,
    regatta::WaveSimulationSystem::ISystemPreUpdate)

GZ_ADD_PLUGIN_ALIAS(regatta::WaveSimulationSystem, "regatta::WaveSimulationSystem")
