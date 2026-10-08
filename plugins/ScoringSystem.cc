#include "ScoringSystem.hh"

#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Link.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/Pose.hh>
#include <gz/sim/components/Inertial.hh>
#include <gz/sim/components/Visual.hh>
#include <gz/sim/components/VisualCmd.hh>
#include <gz/sim/components/Material.hh>
#include <gz/sim/components/ParentEntity.hh>
#include <gz/sim/components/World.hh>
#include <gz/sim/Model.hh>
#include <gz/sim/World.hh>
#include <gz/sim/Util.hh>

#include <gz/plugin/Register.hh>
#include <gz/msgs/visual.pb.h>
#include <gz/msgs/material_color.pb.h>
#include <gz/msgs/server_control.pb.h>
#include <gz/msgs/world_control.pb.h>
#include <gz/msgs/stringmsg.pb.h>
#include <gz/msgs/boolean.pb.h>

#include <iostream>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <cmath>
#include <algorithm>
#include <filesystem>
#include <thread>
#include <chrono>
#include <dirent.h>
#include <signal.h>
#include <sys/types.h>
#include <unistd.h>

namespace
{
  void killProcessesByName(const std::string &_procName, int _sig)
  {
    DIR *dir = opendir("/proc");
    if (!dir)
      return;

    pid_t myPid = getpid();
    struct dirent *entry;
    while ((entry = readdir(dir)) != nullptr)
    {
      if (entry->d_type != DT_DIR)
        continue;

      char *endptr = nullptr;
      long pid = strtol(entry->d_name, &endptr, 10);
      if (*endptr != '\0' || pid <= 1 || pid == myPid)
        continue;

      // Check /proc/<pid>/comm
      std::string commPath = std::string("/proc/") + entry->d_name + "/comm";
      std::ifstream commFile(commPath);
      std::string commName;
      if (commFile >> commName)
      {
        if (commName.find(_procName) != std::string::npos)
        {
          kill(static_cast<pid_t>(pid), _sig);
          continue;
        }
      }

      // Check /proc/<pid>/cmdline
      std::string cmdPath = std::string("/proc/") + entry->d_name + "/cmdline";
      std::ifstream cmdFile(cmdPath);
      std::string cmdLine;
      if (std::getline(cmdFile, cmdLine))
      {
        if (cmdLine.find(_procName) != std::string::npos)
        {
          kill(static_cast<pid_t>(pid), _sig);
        }
      }
    }
    closedir(dir);
  }
}

namespace regatta
{
  ScoringSystem::ScoringSystem()
  {
    this->lastBroadcastTime = std::chrono::steady_clock::now();
  }

  ScoringSystem::~ScoringSystem()
  {
    this->CleanupSharedMemory();
  }

  void ScoringSystem::Configure(
      const gz::sim::Entity &_entity,
      const std::shared_ptr<const sdf::Element> &_sdf,
      gz::sim::EntityComponentManager &_ecm,
      gz::sim::EventManager &)
  {
    // Determine world name
    if (auto worldNameComp = _ecm.Component<gz::sim::components::Name>(_entity))
    {
      this->worldName = worldNameComp->Data();
    }

    if (_sdf)
    {
      if (_sdf->HasElement("world_name"))
        this->worldName = _sdf->Get<std::string>("world_name");

      if (_sdf->HasElement("robot_name"))
        this->robotName = _sdf->Get<std::string>("robot_name");

      if (_sdf->HasElement("robot_link"))
        this->robotLinkName = _sdf->Get<std::string>("robot_link");

      if (_sdf->HasElement("output_file"))
        this->outputFile = _sdf->Get<std::string>("output_file");

      if (_sdf->HasElement("score_topic"))
        this->scoreTopic = _sdf->Get<std::string>("score_topic");

      if (_sdf->HasElement("timeout"))
        this->timeoutSec = _sdf->Get<double>("timeout");

      if (_sdf->HasElement("activation_radius"))
        this->activationRadius = _sdf->Get<double>("activation_radius");

      if (_sdf->HasElement("validation_radius"))
        this->validationRadius = _sdf->Get<double>("validation_radius");

      if (_sdf->HasElement("max_points_per_waypoint"))
        this->maxPointsPerWaypoint = _sdf->Get<double>("max_points_per_waypoint");

      if (_sdf->HasElement("cardinal_radius"))
        this->cardinalCircleRadius = _sdf->Get<double>("cardinal_radius");
      else if (_sdf->HasElement("cardinal_circle_radius"))
        this->cardinalCircleRadius = _sdf->Get<double>("cardinal_circle_radius");
      else if (_sdf->HasElement("cardinal_penalty_radius"))
        this->cardinalCircleRadius = _sdf->Get<double>("cardinal_penalty_radius");

      if (_sdf->HasElement("cardinal_penalty"))
        this->cardinalPenalty = _sdf->Get<double>("cardinal_penalty");
      else if (_sdf->HasElement("cardinal_penalty_points"))
        this->cardinalPenalty = _sdf->Get<double>("cardinal_penalty_points");
      else if (_sdf->HasElement("penalty_cardinal"))
        this->cardinalPenalty = _sdf->Get<double>("penalty_cardinal");

      if (_sdf->HasElement("finish_line_name"))
        this->finishLineName = _sdf->Get<std::string>("finish_line_name");

      if (_sdf->HasElement("finish_line_size"))
        this->configuredFinishLineSize = _sdf->Get<gz::math::Vector3d>("finish_line_size");

      if (_sdf->HasElement("waypoints"))
      {
        auto wpElem = _sdf->FindElement("waypoints");
        if (wpElem && wpElem->HasElement("waypoint"))
        {
          auto item = wpElem->FindElement("waypoint");
          while (item)
          {
            this->configuredWaypointNames.push_back(item->Get<std::string>());
            item = item->GetNextElement("waypoint");
          }
        }
      }
      if (_sdf->HasElement("exit_on_finish"))
        this->exitOnFinish = _sdf->Get<bool>("exit_on_finish");
      else if (_sdf->HasElement("exit_on_completion"))
        this->exitOnFinish = _sdf->Get<bool>("exit_on_completion");
      else if (_sdf->HasElement("auto_exit"))
        this->exitOnFinish = _sdf->Get<bool>("auto_exit");
      else if (_sdf->HasElement("exit_simulation"))
        this->exitOnFinish = _sdf->Get<bool>("exit_simulation");

      if (const char *envExit = std::getenv("REGATTA_EXIT_ON_FINISH"))
      {
        std::string envVal = envExit;
        std::transform(envVal.begin(), envVal.end(), envVal.begin(), ::tolower);
        if (envVal == "1" || envVal == "true" || envVal == "yes")
          this->exitOnFinish = true;
        else if (envVal == "0" || envVal == "false" || envVal == "no")
          this->exitOnFinish = false;
      }
    }

    // Initialize local shared memory for secure GUI score display without network broadcast
    this->InitSharedMemory();

    // Advertise topics
    std::string colorTopic = "/world/" + this->worldName + "/material_color";
    this->colorPub = this->node.Advertise<gz::msgs::MaterialColor>(colorTopic);
    if (!this->scoreTopic.empty())
    {
      this->scorePub = this->node.Advertise<gz::msgs::StringMsg>(this->scoreTopic);
    }

    std::cout << "========================================================\n"
              << " [ScoringSystem] Initialized Ocean Regatta Scoring System\n"
              << " - World: " << this->worldName << "\n"
              << " - Target Robot: " << this->robotName << " (" << this->robotLinkName << ")\n"
              << " - Target Finish Line: " << this->finishLineName << "\n"
              << " - Activation Radius: " << this->activationRadius << " m\n"
              << " - Validation Radius: " << this->validationRadius << " m\n"
              << " - Cardinal Circle Radius: " << this->cardinalCircleRadius << " m\n"
              << " - Cardinal Penalty: " << this->cardinalPenalty << " pts\n"
              << " - Max Points / Waypoint: " << this->maxPointsPerWaypoint << " pts\n"
              << " - Timeout: " << this->timeoutSec << " s\n"
              << " - Output JSON: " << this->outputFile << "\n"
              << " - Score Topic: " << this->scoreTopic << "\n"
              << " - Exit On Finish: " << (this->exitOnFinish ? "true" : "false") << "\n"
              << "========================================================" << std::endl;
  }

  void ScoringSystem::DiscoverEntities(gz::sim::EntityComponentManager &_ecm)
  {
    // 1. Locate Robot
    this->robotEntity = _ecm.EntityByComponents(
        gz::sim::components::Model(),
        gz::sim::components::Name(this->robotName));

    if (this->robotEntity != gz::sim::kNullEntity)
    {
      gz::sim::Model robotModel(this->robotEntity);
      this->robotLinkEntity = robotModel.LinkByName(_ecm, this->robotLinkName);

      if (this->robotLinkEntity != gz::sim::kNullEntity)
      {
        if (auto inertialComp = _ecm.Component<gz::sim::components::Inertial>(this->robotLinkEntity))
        {
          this->robotCoGOffset = inertialComp->Data().Pose().Pos();
        }
        else
        {
          this->robotCoGOffset = gz::math::Vector3d(-0.3, 0.0, 0.0);
        }
      }
    }

    if (this->robotEntity == gz::sim::kNullEntity)
    {
      // Wait until robot model appears in ECM
      return;
    }

    // 2. Discover Waypoints
    this->waypoints.clear();

    if (!this->configuredWaypointNames.empty())
    {
      for (const auto &wpName : this->configuredWaypointNames)
      {
        auto entity = _ecm.EntityByComponents(
            gz::sim::components::Model(),
            gz::sim::components::Name(wpName));
        if (entity != gz::sim::kNullEntity)
        {
          WaypointInfo wp;
          wp.name = wpName;
          wp.modelEntity = entity;
          wp.maxScore = this->maxPointsPerWaypoint;
          this->waypoints.push_back(wp);
        }
      }
    }
    else
    {
      // Auto-discover all models containing "waypoint"
      _ecm.Each<gz::sim::components::Model, gz::sim::components::Name>(
          [&](const gz::sim::Entity &_entity,
              const gz::sim::components::Model *,
              const gz::sim::components::Name *_name) -> bool
          {
            std::string nameLower = _name->Data();
            std::transform(nameLower.begin(), nameLower.end(), nameLower.begin(), ::tolower);
            if (nameLower.find("waypoint") != std::string::npos)
            {
              WaypointInfo wp;
              wp.name = _name->Data();
              wp.modelEntity = _entity;
              wp.maxScore = this->maxPointsPerWaypoint;
              this->waypoints.push_back(wp);
            }
            return true;
          });
    }

    // Resolve visual entity and scoped names for waypoints
    for (auto &wp : this->waypoints)
    {
      gz::sim::Model wpModel(wp.modelEntity);
      auto linkEnt = wpModel.LinkByName(_ecm, "link");
      if (linkEnt == gz::sim::kNullEntity)
      {
        auto links = wpModel.Links(_ecm);
        if (!links.empty()) linkEnt = links[0];
      }

      std::string linkName = "link";
      if (linkEnt != gz::sim::kNullEntity)
      {
        if (auto lnComp = _ecm.Component<gz::sim::components::Name>(linkEnt))
          linkName = lnComp->Data();

        // Find visual entity
        _ecm.Each<gz::sim::components::Visual, gz::sim::components::Name, gz::sim::components::ParentEntity>(
            [&](const gz::sim::Entity &_vEntity,
                const gz::sim::components::Visual *,
                const gz::sim::components::Name *_vName,
                const gz::sim::components::ParentEntity *_parent) -> bool
            {
              if (_parent->Data() == linkEnt)
              {
                wp.visualEntity = _vEntity;
                wp.visualScopedName = wp.name + "::" + linkName + "::" + _vName->Data();
                return false; // found
              }
              return true;
            });
      }

      if (wp.visualScopedName.empty())
      {
        wp.visualScopedName = wp.name + "::" + linkName + "::capsule_visual";
      }

      auto p = gz::sim::worldPose(wp.modelEntity, _ecm);
      wp.position = p.Pos();

      std::cout << " [ScoringSystem] Discovered Waypoint '" << wp.name
                << "' at (" << wp.position.X() << ", " << wp.position.Y() << ", " << wp.position.Z() << ")"
                << " Visual: " << wp.visualScopedName << std::endl;

      // Set initial red color with emissive glow
      this->UpdateWaypointVisual(wp, 1.0, 0.0, 0.0, 0.45, _ecm);
    }

    // 3. Discover Finish Line (The world should only contain one finish line)
    this->finishLine = FinishLineInfo();
    this->finishLine.name = this->finishLineName;
    this->finishLine.size = this->configuredFinishLineSize;

    std::vector<gz::sim::Entity> discoveredFinishLines;
    std::vector<std::string> discoveredFinishLineNames;
    _ecm.Each<gz::sim::components::Model, gz::sim::components::Name>(
        [&](const gz::sim::Entity &_entity,
            const gz::sim::components::Model *,
            const gz::sim::components::Name *_name) -> bool
        {
          std::string name = _name->Data();
          std::string nameLower = name;
          std::transform(nameLower.begin(), nameLower.end(), nameLower.begin(), ::tolower);
          if (name == this->finishLineName || nameLower == "finish_line" || nameLower.find("finish_line") != std::string::npos)
          {
            discoveredFinishLines.push_back(_entity);
            discoveredFinishLineNames.push_back(name);
          }
          return true;
        });

    this->finishLineCount = static_cast<int>(discoveredFinishLines.size());

    if (this->finishLineCount == 0)
    {
      std::cerr << " [ScoringSystem] ⚠️ WARNING: No finish line found in world!" << std::endl;
      this->finishLine.isDiscovered = false;
    }
    else if (this->finishLineCount > 1)
    {
      std::cerr << "========================================================\n"
                << " [ScoringSystem] ⚠️ WARNING / VIOLATION: Multiple (" << this->finishLineCount
                << ") finish lines found in the world!\n"
                << " The world should only contain one finish line.\n"
                << " Discovered finish lines:";
      for (const auto &fn : discoveredFinishLineNames)
        std::cerr << " '" << fn << "'";
      std::cerr << "\n Using primary finish line: '" << discoveredFinishLineNames[0] << "'\n"
                << "========================================================" << std::endl;
    }

    if (this->finishLineCount >= 1)
    {
      size_t chosenIdx = 0;
      for (size_t i = 0; i < discoveredFinishLineNames.size(); ++i)
      {
        if (discoveredFinishLineNames[i] == this->finishLineName)
        {
          chosenIdx = i;
          break;
        }
      }

      this->finishLine.modelEntity = discoveredFinishLines[chosenIdx];
      this->finishLine.name = discoveredFinishLineNames[chosenIdx];

      gz::sim::Model flModel(this->finishLine.modelEntity);
      this->finishLine.linkEntity = flModel.LinkByName(_ecm, "base_link");
      if (this->finishLine.linkEntity == gz::sim::kNullEntity)
      {
        auto links = flModel.Links(_ecm);
        if (!links.empty())
          this->finishLine.linkEntity = links[0];
      }

      std::string linkName = "base_link";
      if (this->finishLine.linkEntity != gz::sim::kNullEntity)
      {
        if (auto lnComp = _ecm.Component<gz::sim::components::Name>(this->finishLine.linkEntity))
          linkName = lnComp->Data();

        _ecm.Each<gz::sim::components::Visual, gz::sim::components::Name, gz::sim::components::ParentEntity>(
            [&](const gz::sim::Entity &_vEntity,
                const gz::sim::components::Visual *,
                const gz::sim::components::Name *_vName,
                const gz::sim::components::ParentEntity *_parent) -> bool
            {
              if (_parent->Data() == this->finishLine.linkEntity)
              {
                this->finishLine.visualEntity = _vEntity;
                this->finishLine.visualScopedName = this->finishLine.name + "::" + linkName + "::" + _vName->Data();
                return false;
              }
              return true;
            });
      }

      if (this->finishLine.visualScopedName.empty())
      {
        this->finishLine.visualScopedName = this->finishLine.name + "::" + linkName + "::chassis_visual";
      }

      this->finishLine.pose = gz::sim::worldPose(
          this->finishLine.linkEntity != gz::sim::kNullEntity ? this->finishLine.linkEntity : this->finishLine.modelEntity,
          _ecm);

      this->finishLine.isDiscovered = true;

      std::cout << " [ScoringSystem] 🏁 Discovered unique Finish Line '" << this->finishLine.name
                << "' at (" << this->finishLine.pose.Pos().X() << ", "
                << this->finishLine.pose.Pos().Y() << ", "
                << this->finishLine.pose.Pos().Z() << ") with Yaw = "
                << (this->finishLine.pose.Rot().Yaw() * 180.0 / M_PI) << " deg"
                << " (Visual: " << this->finishLine.visualScopedName << ")" << std::endl;
    }

    // 4. Discover Cardinal Buoys
    this->cardinalBuoys.clear();
    _ecm.Each<gz::sim::components::Model, gz::sim::components::Name>(
        [&](const gz::sim::Entity &_entity,
            const gz::sim::components::Model *,
            const gz::sim::components::Name *_name) -> bool
        {
          std::string nameLower = _name->Data();
          std::transform(nameLower.begin(), nameLower.end(), nameLower.begin(), ::tolower);
          if (nameLower.find("cardinal") != std::string::npos)
          {
            CardinalBuoyInfo cb;
            cb.name = _name->Data();
            cb.modelEntity = _entity;

            if (nameLower.find("north") != std::string::npos)
            {
              cb.type = CardinalType::NORTH;
              cb.typeString = "cardinal_north";
            }
            else if (nameLower.find("south") != std::string::npos)
            {
              cb.type = CardinalType::SOUTH;
              cb.typeString = "cardinal_south";
            }
            else if (nameLower.find("east") != std::string::npos)
            {
              cb.type = CardinalType::EAST;
              cb.typeString = "cardinal_east";
            }
            else if (nameLower.find("west") != std::string::npos)
            {
              cb.type = CardinalType::WEST;
              cb.typeString = "cardinal_west";
            }
            else
            {
              cb.type = CardinalType::UNKNOWN;
              cb.typeString = "cardinal_unknown";
            }

            auto p = gz::sim::worldPose(cb.modelEntity, _ecm);
            cb.position = p.Pos();
            this->cardinalBuoys.push_back(cb);

            std::cout << " [ScoringSystem] 🧭 Discovered Cardinal Buoy '" << cb.name
                      << "' (" << cb.typeString << ") at ("
                      << cb.position.X() << ", " << cb.position.Y() << ", " << cb.position.Z() << ")"
                      << std::endl;
          }
          return true;
        });

    if (!this->waypoints.empty() || this->finishLine.isDiscovered || !this->cardinalBuoys.empty())
    {
      this->entitiesDiscovered = true;
      std::cout << " [ScoringSystem] Registered " << this->waypoints.size()
                << " waypoint(s), " << this->cardinalBuoys.size()
                << " cardinal buoy(s), and " << (this->finishLine.isDiscovered ? 1 : 0)
                << " finish line for scoring." << std::endl;
    }
  }

  void ScoringSystem::UpdateFinishLineVisual(
      double _r, double _g, double _b, double _a,
      gz::sim::EntityComponentManager &_ecm)
  {
    if (!this->finishLine.isDiscovered)
      return;

    // 1. Direct ECM command via components::VisualCmd for Gazebo Rendering / GUI
    if (this->finishLine.visualEntity != gz::sim::kNullEntity)
    {
      gz::msgs::Visual visualCmdMsg;
      visualCmdMsg.set_id(this->finishLine.visualEntity);
      if (!this->finishLine.visualScopedName.empty())
      {
        visualCmdMsg.set_name(this->finishLine.visualScopedName);
      }

      auto mat = visualCmdMsg.mutable_material();
      mat->mutable_ambient()->set_r(_r);
      mat->mutable_ambient()->set_g(_g);
      mat->mutable_ambient()->set_b(_b);
      mat->mutable_ambient()->set_a(_a);

      mat->mutable_diffuse()->set_r(_r);
      mat->mutable_diffuse()->set_g(_g);
      mat->mutable_diffuse()->set_b(_b);
      mat->mutable_diffuse()->set_a(_a);

      mat->mutable_specular()->set_r(0.8);
      mat->mutable_specular()->set_g(0.8);
      mat->mutable_specular()->set_b(0.8);
      mat->mutable_specular()->set_a(_a);

      mat->mutable_emissive()->set_r(_r * 0.5);
      mat->mutable_emissive()->set_g(_g * 0.5);
      mat->mutable_emissive()->set_b(_b * 0.5);
      mat->mutable_emissive()->set_a(1.0);

      if (!_ecm.Component<gz::sim::components::VisualCmd>(this->finishLine.visualEntity))
      {
        _ecm.CreateComponent(this->finishLine.visualEntity, gz::sim::components::VisualCmd(visualCmdMsg));
      }
      else
      {
        _ecm.SetComponentData<gz::sim::components::VisualCmd>(this->finishLine.visualEntity, visualCmdMsg);
      }
      _ecm.SetChanged(this->finishLine.visualEntity, gz::sim::components::VisualCmd::typeId, gz::sim::ComponentState::OneTimeChange);

      auto matComp = _ecm.Component<gz::sim::components::Material>(this->finishLine.visualEntity);
      if (matComp)
      {
        sdf::Material sdfMat = matComp->Data();
        sdfMat.SetAmbient(gz::math::Color(_r, _g, _b, _a));
        sdfMat.SetDiffuse(gz::math::Color(_r, _g, _b, _a));
        sdfMat.SetEmissive(gz::math::Color(_r * 0.5, _g * 0.5, _b * 0.5, 1.0));
        _ecm.SetComponentData<gz::sim::components::Material>(this->finishLine.visualEntity, sdfMat);
        _ecm.SetChanged(this->finishLine.visualEntity, gz::sim::components::Material::typeId, gz::sim::ComponentState::OneTimeChange);
      }
    }

    // 2. Publish MaterialColor message for UserCommands / GUI listeners
    gz::msgs::MaterialColor colorMsg;
    if (this->finishLine.visualEntity != gz::sim::kNullEntity)
    {
      colorMsg.mutable_entity()->set_id(this->finishLine.visualEntity);
    }
    colorMsg.mutable_entity()->set_name(this->finishLine.visualScopedName);
    colorMsg.mutable_entity()->set_type(gz::msgs::Entity::VISUAL);

    colorMsg.mutable_ambient()->set_r(_r);
    colorMsg.mutable_ambient()->set_g(_g);
    colorMsg.mutable_ambient()->set_b(_b);
    colorMsg.mutable_ambient()->set_a(_a);

    colorMsg.mutable_diffuse()->set_r(_r);
    colorMsg.mutable_diffuse()->set_g(_g);
    colorMsg.mutable_diffuse()->set_b(_b);
    colorMsg.mutable_diffuse()->set_a(_a);

    colorMsg.mutable_specular()->set_r(0.8);
    colorMsg.mutable_specular()->set_g(0.8);
    colorMsg.mutable_specular()->set_b(0.8);
    colorMsg.mutable_specular()->set_a(_a);

    colorMsg.mutable_emissive()->set_r(_r * 0.5);
    colorMsg.mutable_emissive()->set_g(_g * 0.5);
    colorMsg.mutable_emissive()->set_b(_b * 0.5);
    colorMsg.mutable_emissive()->set_a(1.0);

    colorMsg.set_entity_match(gz::msgs::MaterialColor::FIRST);
    this->colorPub.Publish(colorMsg);
  }

  void ScoringSystem::UpdateWaypointVisual(
      WaypointInfo &_wp, double _r, double _g, double _b, double _a,
      gz::sim::EntityComponentManager &_ecm)
  {
    // 1. Direct ECM command via components::VisualCmd for Gazebo Rendering / GUI
    if (_wp.visualEntity != gz::sim::kNullEntity)
    {
      gz::msgs::Visual visualCmdMsg;
      visualCmdMsg.set_id(_wp.visualEntity);
      if (!_wp.visualScopedName.empty())
      {
        visualCmdMsg.set_name(_wp.visualScopedName);
      }

      auto mat = visualCmdMsg.mutable_material();
      mat->mutable_ambient()->set_r(_r);
      mat->mutable_ambient()->set_g(_g);
      mat->mutable_ambient()->set_b(_b);
      mat->mutable_ambient()->set_a(_a);

      mat->mutable_diffuse()->set_r(_r);
      mat->mutable_diffuse()->set_g(_g);
      mat->mutable_diffuse()->set_b(_b);
      mat->mutable_diffuse()->set_a(_a);

      mat->mutable_specular()->set_r(0.6);
      mat->mutable_specular()->set_g(0.6);
      mat->mutable_specular()->set_b(0.6);
      mat->mutable_specular()->set_a(_a);

      mat->mutable_emissive()->set_r(_r * 0.25);
      mat->mutable_emissive()->set_g(_g * 0.25);
      mat->mutable_emissive()->set_b(_b * 0.25);
      mat->mutable_emissive()->set_a(1.0);

      if (!_ecm.Component<gz::sim::components::VisualCmd>(_wp.visualEntity))
      {
        _ecm.CreateComponent(_wp.visualEntity, gz::sim::components::VisualCmd(visualCmdMsg));
      }
      else
      {
        _ecm.SetComponentData<gz::sim::components::VisualCmd>(_wp.visualEntity, visualCmdMsg);
      }
      _ecm.SetChanged(_wp.visualEntity, gz::sim::components::VisualCmd::typeId, gz::sim::ComponentState::OneTimeChange);

      // 2. Also directly update components::Material in ECM with SetChanged
      auto matComp = _ecm.Component<gz::sim::components::Material>(_wp.visualEntity);
      if (matComp)
      {
        sdf::Material sdfMat = matComp->Data();
        sdfMat.SetAmbient(gz::math::Color(_r, _g, _b, _a));
        sdfMat.SetDiffuse(gz::math::Color(_r, _g, _b, _a));
        sdfMat.SetEmissive(gz::math::Color(_r * 0.25, _g * 0.25, _b * 0.25, 1.0));
        _ecm.SetComponentData<gz::sim::components::Material>(_wp.visualEntity, sdfMat);
        _ecm.SetChanged(_wp.visualEntity, gz::sim::components::Material::typeId, gz::sim::ComponentState::OneTimeChange);
      }
    }

    // 3. Publish MaterialColor message for UserCommands / GUI listeners
    gz::msgs::MaterialColor colorMsg;
    if (_wp.visualEntity != gz::sim::kNullEntity)
    {
      colorMsg.mutable_entity()->set_id(_wp.visualEntity);
    }
    colorMsg.mutable_entity()->set_name(_wp.visualScopedName);
    colorMsg.mutable_entity()->set_type(gz::msgs::Entity::VISUAL);

    colorMsg.mutable_ambient()->set_r(_r);
    colorMsg.mutable_ambient()->set_g(_g);
    colorMsg.mutable_ambient()->set_b(_b);
    colorMsg.mutable_ambient()->set_a(_a);

    colorMsg.mutable_diffuse()->set_r(_r);
    colorMsg.mutable_diffuse()->set_g(_g);
    colorMsg.mutable_diffuse()->set_b(_b);
    colorMsg.mutable_diffuse()->set_a(_a);

    colorMsg.mutable_specular()->set_r(0.6);
    colorMsg.mutable_specular()->set_g(0.6);
    colorMsg.mutable_specular()->set_b(0.6);
    colorMsg.mutable_specular()->set_a(_a);

    colorMsg.mutable_emissive()->set_r(_r * 0.25);
    colorMsg.mutable_emissive()->set_g(_g * 0.25);
    colorMsg.mutable_emissive()->set_b(_b * 0.25);
    colorMsg.mutable_emissive()->set_a(1.0);

    colorMsg.set_entity_match(gz::msgs::MaterialColor::FIRST);
    this->colorPub.Publish(colorMsg);
  }

  void ScoringSystem::ProcessCardinalBuoys(
      double _robotX, double _robotY,
      double _prevX, double _prevY,
      double _simTime,
      bool &_stateChanged)
  {
    for (auto &cb : this->cardinalBuoys)
    {
      double cbX = cb.position.X();
      double cbY = cb.position.Y();

      // Horizontal 2D distance
      double dist = std::hypot(_robotX - cbX, _robotY - cbY);
      cb.minDistance = std::min(cb.minDistance, dist);

      bool insideNow = (dist <= this->cardinalCircleRadius);

      // Check if robot is inside the tunable circle (default 20m)
      if (insideNow)
      {
        cb.insideCircle = true;

        // Vector from buoy to robot: r = (rx, ry)
        double rx = _robotX - cbX;
        double ry = _robotY - cbY;

        // Robot displacement vector: v = (vx, vy)
        double vx = _robotX - _prevX;
        double vy = _robotY - _prevY;

        // Vector from previous robot position to buoy: d = (dx, dy)
        double dx = cbX - _prevX;
        double dy = cbY - _prevY;

        // Trajectory cross product determinant: det(v, d) = vx * dy - vy * dx
        // If > 0: buoy is to vessel's port (left)
        // If < 0: buoy is to vessel's starboard (right)
        double trajDet = vx * dy - vy * dx;
        cb.trajectoryDeterminant = trajDet;

        // Cardinal reference axis determinant:
        // - For North/South: dividing axis is East vector u_EW = (1, 0)
        //   det(u_EW, r) = 1 * ry - 0 * rx = ry = (robotY - cbY)
        //   det > 0 => robot is North of buoy
        //   det < 0 => robot is South of buoy
        // - For East/West: dividing axis is North vector u_NS = (0, 1)
        //   det(r, u_NS) = rx * 1 - ry * 0 = rx = (robotX - cbX)
        //   det > 0 => robot is East of buoy
        //   det < 0 => robot is West of buoy
        double cardDet = 0.0;
        if (cb.type == CardinalType::SOUTH || cb.type == CardinalType::NORTH)
        {
          cardDet = ry;
        }
        else if (cb.type == CardinalType::EAST || cb.type == CardinalType::WEST)
        {
          cardDet = rx;
        }
        cb.lastDeterminant = cardDet;

        // Check if robot overpassed the buoy during this step:
        // Case 1: Crossing abreast of the buoy (meridian for N/S, parallel for E/W)
        bool crossedAbreast = false;
        double abreastDet = cardDet;

        if (cb.type == CardinalType::SOUTH || cb.type == CardinalType::NORTH)
        {
          // Crossing the meridian line x = cbX
          double prevRx = _prevX - cbX;
          if ((prevRx <= 0.0 && rx > 0.0) || (prevRx >= 0.0 && rx < 0.0))
          {
            double denom = rx - prevRx;
            if (std::abs(denom) > 1e-9)
            {
              double alpha = -prevRx / denom;
              if (alpha >= 0.0 && alpha <= 1.0)
              {
                double yCross = _prevY + alpha * (_robotY - _prevY);
                double dCross = std::abs(yCross - cbY);
                if (dCross <= this->cardinalCircleRadius)
                {
                  crossedAbreast = true;
                  abreastDet = yCross - cbY;
                }
              }
            }
          }
        }
        else if (cb.type == CardinalType::EAST || cb.type == CardinalType::WEST)
        {
          // Crossing the parallel line y = cbY
          double prevRy = _prevY - cbY;
          if ((prevRy <= 0.0 && ry > 0.0) || (prevRy >= 0.0 && ry < 0.0))
          {
            double denom = ry - prevRy;
            if (std::abs(denom) > 1e-9)
            {
              double alpha = -prevRy / denom;
              if (alpha >= 0.0 && alpha <= 1.0)
              {
                double xCross = _prevX + alpha * (_robotX - _prevX);
                double dCross = std::abs(xCross - cbX);
                if (dCross <= this->cardinalCircleRadius)
                {
                  crossedAbreast = true;
                  abreastDet = xCross - cbX;
                }
              }
            }
          }
        }

        // Case 2: CPA reached (radial projection velocity changes from negative to positive)
        bool cpaReached = false;
        double rDotV = rx * vx + ry * vy;
        double prevRDotV = (_prevX - cbX) * vx + (_prevY - cbY) * vy;
        if (prevRDotV < -1e-4 && rDotV >= 0.0 && (vx * vx + vy * vy > 1e-6))
        {
          cpaReached = true;
        }

        if ((crossedAbreast || cpaReached) && !cb.overpassed)
        {
          cb.overpassed = true;
          cb.overpassTime = _simTime;

          // Evaluate wrong side using determinant at crossing / CPA:
          // South cardinal: safe water is SOUTH (abreastDet < 0), danger is NORTH (abreastDet > 0)
          // North cardinal: safe water is NORTH (abreastDet > 0), danger is SOUTH (abreastDet < 0)
          // East cardinal: safe water is EAST (abreastDet > 0), danger is WEST (abreastDet < 0)
          // West cardinal: safe water is WEST (abreastDet < 0), danger is EAST (abreastDet > 0)
          bool wrongSideAtOverpass = false;
          if (cb.type == CardinalType::SOUTH)
            wrongSideAtOverpass = (abreastDet > 0.0);
          else if (cb.type == CardinalType::NORTH)
            wrongSideAtOverpass = (abreastDet < 0.0);
          else if (cb.type == CardinalType::EAST)
            wrongSideAtOverpass = (abreastDet < 0.0);
          else if (cb.type == CardinalType::WEST)
            wrongSideAtOverpass = (abreastDet > 0.0);

          if (wrongSideAtOverpass)
          {
            cb.overpassSide = "wrong";
            if (!cb.penaltyApplied)
            {
              cb.penaltyApplied = true;
              _stateChanged = true;
              std::cout << "\n========================================================\n"
                        << " [ScoringSystem] ⚠️ PENALTY: Robot overpassed cardinal buoy '"
                        << cb.name << "' (" << cb.typeString << ") on the WRONG side!\n"
                        << " - Buoy Position: (" << cbX << ", " << cbY << ")\n"
                        << " - Robot Position: (" << _robotX << ", " << _robotY << ")\n"
                        << " - Determinant: " << abreastDet << "\n"
                        << " - Distance: " << dist << " m (within circle of "
                        << this->cardinalCircleRadius << " m)\n"
                        << " - Incurred Penalty: -" << this->cardinalPenalty << " pts\n"
                        << "========================================================\n" << std::endl;
            }
          }
          else
          {
            cb.overpassSide = "correct";
            std::cout << " [ScoringSystem] ✅ Robot correctly passed cardinal buoy '"
                      << cb.name << "' (" << cb.typeString << ") on the safe side "
                      << "(Determinant: " << abreastDet << ", Distance: " << dist << " m)" << std::endl;
          }
        }
      }
      else
      {
        // Outside the circle
        if (cb.insideCircle)
        {
          cb.insideCircle = false;
          // Vessel was inside the circle and now exited it
          if (!cb.overpassed && cb.minDistance < this->cardinalCircleRadius * 0.95)
          {
            cb.overpassed = true;
            cb.overpassTime = _simTime;

            bool wrongSide = false;
            if (cb.type == CardinalType::SOUTH) wrongSide = (cb.lastDeterminant > 0.0);
            else if (cb.type == CardinalType::NORTH) wrongSide = (cb.lastDeterminant < 0.0);
            else if (cb.type == CardinalType::EAST) wrongSide = (cb.lastDeterminant < 0.0);
            else if (cb.type == CardinalType::WEST) wrongSide = (cb.lastDeterminant > 0.0);

            if (wrongSide)
            {
              cb.overpassSide = "wrong";
              if (!cb.penaltyApplied)
              {
                cb.penaltyApplied = true;
                _stateChanged = true;
                std::cout << "\n========================================================\n"
                          << " [ScoringSystem] ⚠️ PENALTY (circle exit): Robot passed cardinal buoy '"
                          << cb.name << "' on the WRONG side! (-" << this->cardinalPenalty << " pts)\n"
                          << "========================================================\n" << std::endl;
              }
            }
            else
            {
              cb.overpassSide = "correct";
            }
          }
        }
      }
    }
  }

  void ScoringSystem::PreUpdate(
      const gz::sim::UpdateInfo &_info,
      gz::sim::EntityComponentManager &_ecm)
  {
    if (_info.paused || this->simulationFinished)
      return;

    if (!this->entitiesDiscovered)
    {
      this->DiscoverEntities(_ecm);
      if (!this->entitiesDiscovered)
        return;
    }

    double simTime = std::chrono::duration<double>(_info.simTime).count();

    // 0. Record simulation start time on first unpaused PreUpdate
    if (!this->hasStartTime)
    {
      this->startSimTime = simTime;
      this->hasStartTime = true;
    }

    // 1. Calculate Robot Center of Gravity (CoG) in World Frame
    auto robotPose = gz::sim::worldPose(
        this->robotLinkEntity != gz::sim::kNullEntity ? this->robotLinkEntity : this->robotEntity,
        _ecm);

    gz::math::Vector3d robotCoG = robotPose.Pos() + robotPose.Rot().RotateVector(this->robotCoGOffset);
    double robotX = robotCoG.X();
    double robotY = robotCoG.Y();

    if (!this->hasPrevRobotPos)
    {
      this->startRobotPos = robotCoG;
      this->prevRobotPos = robotCoG;
      this->hasPrevRobotPos = true;
      this->prevSimTime = simTime;
    }

    // 2. Process distance and score for each waypoint
    bool stateChanged = false;

    for (auto &wp : this->waypoints)
    {
      auto wpPose = gz::sim::worldPose(wp.modelEntity, _ecm);
      double wpX = wpPose.Pos().X();
      double wpY = wpPose.Pos().Y();

      // Horizontal 2D Euclidean distance (ignoring Z)
      double dist = std::hypot(robotX - wpX, robotY - wpY);
      wp.currentDistance = dist;
      wp.minDistance = std::min(wp.minDistance, dist);

      double ratio = 0.0;
      double currentScore = 0.0;

      if (dist >= this->activationRadius)
      {
        ratio = 0.0;
        currentScore = 0.0;

        // If vessel was inside the activation circle (3m) and now left it without reaching <= 0.3m
        if (wp.wasInside && !wp.isDone)
        {
          wp.isDone = true;
          if (wp.score > 0.0 && !wp.validated)
          {
            wp.validated = true;
            wp.validationTime = simTime;
          }
          stateChanged = true;
          std::cout << " [ScoringSystem] ⏩ Vessel exited waypoint '" << wp.name
                    << "' circle. Final waypoint score: " << wp.score << " / "
                    << wp.maxScore << " pts (min dist: " << wp.minDistance << "m)" << std::endl;
        }
      }
      else if (dist <= this->validationRadius)
      {
        // Inside perfect precision zone (<= 0.3m) -> Exactly 2.0 points!
        ratio = 1.0;
        currentScore = this->maxPointsPerWaypoint;
        wp.wasInside = true;

        if (!wp.validated)
        {
          wp.validated = true;
          wp.validationTime = simTime;
          wp.score = this->maxPointsPerWaypoint;
          wp.isDone = true;
          stateChanged = true;

          std::cout << " [ScoringSystem] 🎯 Waypoint '" << wp.name
                    << "' PERFECT VALIDATION! Awarded " << wp.score << " / "
                    << wp.maxScore << " pts at t = " << std::fixed << std::setprecision(2)
                    << simTime << " s (dist: " << dist << "m)" << std::endl;
        }
      }
      else
      {
        // Linear transition between activationRadius (3.0m) and validationRadius (0.3m):
        ratio = (this->activationRadius - dist) / (this->activationRadius - this->validationRadius);
        ratio = std::clamp(ratio, 0.0, 1.0);
        currentScore = this->maxPointsPerWaypoint * ratio;
        wp.wasInside = true;

        if (currentScore > wp.score)
        {
          wp.score = currentScore;
          stateChanged = true;
        }
      }

      // Real-time waypoint color actualisation based on attributed score ratio
      double scoreRatio = (wp.maxScore > 0.0) ? std::clamp(wp.score / wp.maxScore, 0.0, 1.0) : 0.0;
      if (std::abs(scoreRatio - wp.lastVisualRatio) >= 0.005 || (wp.isDone && wp.lastVisualRatio != scoreRatio))
      {
        wp.lastVisualRatio = scoreRatio;
        wp.bestRatio = scoreRatio;
        double r = 1.0 - scoreRatio;
        double g = scoreRatio;
        double b = 0.0;
        double a = 0.45;
        this->UpdateWaypointVisual(wp, r, g, b, a, _ecm);
      }
    }

    // 2b. Process cardinal buoys: penalize if overpassed on the wrong side within the 20m circle
    this->ProcessCardinalBuoys(
        robotX, robotY,
        this->prevRobotPos.X(), this->prevRobotPos.Y(),
        simTime,
        stateChanged);

    // 3. Periodic real-time broadcast (at 10 Hz or on state change)
    auto now = std::chrono::steady_clock::now();
    if (stateChanged || std::chrono::duration<double>(now - this->lastBroadcastTime).count() >= 0.1)
    {
      this->BroadcastScore(simTime);
      this->lastBroadcastTime = now;
    }

    // Check waypoint clearing state
    bool allWaypointsDone = !this->waypoints.empty();
    for (const auto &wp : this->waypoints)
    {
      if (!wp.isDone)
      {
        allWaypointsDone = false;
        break;
      }
    }

    // 4. Check Finish Line Crossing: Simulation finishes when robot goes through finish line
    if (this->finishLine.isDiscovered && !this->finishLine.crossed)
    {
      this->finishLine.pose = gz::sim::worldPose(
          this->finishLine.linkEntity != gz::sim::kNullEntity ? this->finishLine.linkEntity : this->finishLine.modelEntity,
          _ecm);

      gz::math::Vector3d dWorld = robotCoG - this->finishLine.pose.Pos();
      gz::math::Vector3d pLoc = this->finishLine.pose.Rot().Inverse().RotateVector(dWorld);

      double halfX = this->finishLine.size.X() * 0.5;
      double halfY = this->finishLine.size.Y() * 0.5;

      // 1) Inside 2D bounding box
      bool insideBox = (std::abs(pLoc.X()) <= halfX) && (std::abs(pLoc.Y()) <= halfY);

      // 2) Segment crossing between consecutive physics frames
      bool crossedSegment = false;
      if (this->hasPrevRobotPos)
      {
        gz::math::Vector3d prevDWorld = this->prevRobotPos - this->finishLine.pose.Pos();
        gz::math::Vector3d prevPLoc = this->finishLine.pose.Rot().Inverse().RotateVector(prevDWorld);

        double x1 = prevPLoc.X();
        double x2 = pLoc.X();
        if ((x1 <= 0.0 && x2 > 0.0) || (x1 >= 0.0 && x2 < 0.0))
        {
          double denom = x2 - x1;
          if (std::abs(denom) > 1e-9)
          {
            double alpha = -x1 / denom;
            if (alpha >= 0.0 && alpha <= 1.0)
            {
              double yCross = prevPLoc.Y() + alpha * (pLoc.Y() - prevPLoc.Y());
              if (std::abs(yCross) <= halfY)
              {
                crossedSegment = true;
              }
            }
          }
        }
      }

      double distFromStart = (robotCoG - this->startRobotPos).Length();
      if ((insideBox || crossedSegment) && (distFromStart > 1.0 || simTime > 1.0))
      {
        this->finishLine.crossed = true;
        this->finishLine.crossingTime = simTime;
        this->finishLine.crossingPos = robotCoG;

        double robotYaw = robotPose.Rot().Yaw();
        while (robotYaw > M_PI) robotYaw -= 2.0 * M_PI;
        while (robotYaw <= -M_PI) robotYaw += 2.0 * M_PI;
        double robotYawDeg = robotYaw * 180.0 / M_PI;

        double flYaw = this->finishLine.pose.Rot().Yaw();
        while (flYaw > M_PI) flYaw -= 2.0 * M_PI;
        while (flYaw <= -M_PI) flYaw += 2.0 * M_PI;
        double flYawDeg = flYaw * 180.0 / M_PI;

        double relYaw = robotYaw - flYaw;
        while (relYaw > M_PI) relYaw -= 2.0 * M_PI;
        while (relYaw <= -M_PI) relYaw += 2.0 * M_PI;
        double relYawDeg = relYaw * 180.0 / M_PI;

        // Motion displacement
        gz::math::Vector3d moveVec = robotCoG - this->prevRobotPos;
        moveVec.Z(0.0);
        gz::math::Vector3d headingVec(std::cos(robotYaw), std::sin(robotYaw), 0.0);

        // Robot finishing backwards badge detection:
        // A robot qualifies for backwards badge if:
        // - Heading relative to finish line is backwards (|relYaw| > 90 deg), OR
        // - Robot motion direction is in reverse relative to heading (heading dot moveVec < 0)
        bool backwardsRelOrientation = (std::abs(relYawDeg) > 90.0);
        bool backwardsMovement = (moveVec.Length() > 0.005 && headingVec.Dot(moveVec.Normalized()) < 0.0);
        bool finishedBackwards = backwardsRelOrientation || backwardsMovement;

        this->finishLine.robotHeadingRad = robotYaw;
        this->finishLine.robotHeadingDeg = robotYawDeg;
        this->finishLine.relativeHeadingRad = relYaw;
        this->finishLine.relativeHeadingDeg = relYawDeg;
        this->finishLine.finishedBackwards = finishedBackwards;

        // Visual feedback: green glow on finish line
        this->UpdateFinishLineVisual(0.1, 1.0, 0.2, 0.9, _ecm);

        double totalRunTime = simTime - this->startSimTime;

        std::cout << "\n========================================================\n"
                  << " [ScoringSystem] 🏁 ROBOT CROSSED THE FINISH LINE!\n"
                  << " - Finish Time: " << std::fixed << std::setprecision(3) << simTime << " s\n"
                  << " - Total Run Time: " << totalRunTime << " s (from start to finish line)\n"
                  << " - Robot Heading: " << robotYawDeg << " deg (" << robotYaw << " rad)\n"
                  << " - Relative Heading to Finish Line: " << relYawDeg << " deg\n"
                  << " - Finishing Backwards: " << (finishedBackwards ? "YES 🎖️ (Backwards Badge Earned!)" : "NO (Forward)") << "\n"
                  << "========================================================" << std::endl;

        this->simulationFinished = true;
        this->BroadcastScore(simTime);
        this->WriteJsonReport(simTime, "FINISH_LINE_CROSSED");
        this->StopSimulation();
        return;
      }
    }

    // 5. Update previous robot pose
    this->prevRobotPos = robotCoG;
    this->hasPrevRobotPos = true;
    this->prevSimTime = simTime;

    // 6. Fallback if no finish line is present in world
    if (!this->finishLine.isDiscovered && allWaypointsDone)
    {
      this->simulationFinished = true;
      std::cout << "\n========================================================\n"
                << " [ScoringSystem] 🏁 ALL WAYPOINTS COMPLETED (No Finish Line)!\n"
                << " Total simulation time: " << std::fixed << std::setprecision(2) << simTime << " s\n"
                << "========================================================" << std::endl;
      this->BroadcastScore(simTime);
      this->WriteJsonReport(simTime, "ALL_WAYPOINTS_CLEARED");
      this->StopSimulation();
      return;
    }

    // 7. Timeout check
    if (simTime >= this->timeoutSec)
    {
      this->simulationFinished = true;
      std::cout << "\n========================================================\n"
                << " [ScoringSystem] ⏰ SIMULATION TIMEOUT REACHED (" << this->timeoutSec << " s)!\n"
                << "========================================================" << std::endl;
      for (auto &wp : this->waypoints)
      {
        if (!wp.isDone)
        {
          wp.isDone = true;
          if (wp.score > 0.0 && !wp.validated)
          {
            wp.validated = true;
            wp.validationTime = simTime;
          }
        }
      }
      this->BroadcastScore(simTime);
      this->WriteJsonReport(simTime, "TIMEOUT");
      this->StopSimulation();
    }
  }

  void ScoringSystem::BroadcastScore(double _simTime)
  {
    double waypointScore = 0.0;
    double maxScore = 0.0;

    for (const auto &wp : this->waypoints)
    {
      waypointScore += wp.score;
      maxScore += wp.maxScore;
    }

    double currentPenalties = 0.0;
    int penaltyCount = 0;
    for (const auto &cb : this->cardinalBuoys)
    {
      if (cb.penaltyApplied)
      {
        currentPenalties += this->cardinalPenalty;
        penaltyCount++;
      }
    }
    this->totalPenalties = currentPenalties;
    double totalScore = waypointScore - this->totalPenalties;
    if (totalScore < 2.0)
    {
      totalScore = 2.0;
    }

    // Update shared memory for ScoringWidget GUI (no network msgs)
    this->UpdateSharedMemory(totalScore, maxScore);

    // Only publish on Gazebo Transport if explicitly requested by SDF
    if (!this->scoreTopic.empty())
    {
      int waypointsCleared = 0;
      for (const auto &wp : this->waypoints)
      {
        if (wp.validated || wp.isDone)
          waypointsCleared++;
      }

      std::ostringstream json;
      json << std::fixed << std::setprecision(3);
      json << "{";
      json << "\"sim_time\":" << _simTime << ",";
      json << "\"total_score\":" << totalScore << ",";
      json << "\"waypoint_score\":" << waypointScore << ",";
      json << "\"total_penalties\":" << this->totalPenalties << ",";
      json << "\"penalty_count\":" << penaltyCount << ",";
      json << "\"max_score\":" << maxScore << ",";
      json << "\"waypoints_cleared\":" << waypointsCleared << ",";
      json << "\"total_waypoints\":" << this->waypoints.size() << ",";
      json << "\"waypoints\":[";
      for (size_t i = 0; i < this->waypoints.size(); ++i)
      {
        const auto &wp = this->waypoints[i];
        if (i > 0) json << ",";
        json << "{"
             << "\"name\":\"" << wp.name << "\","
             << "\"score\":" << wp.score << ","
             << "\"max_score\":" << wp.maxScore << ","
             << "\"min_distance\":" << wp.minDistance << ","
             << "\"current_distance\":" << wp.currentDistance << ","
             << "\"validated\":" << (wp.validated ? "true" : "false") << ","
             << "\"is_done\":" << (wp.isDone ? "true" : "false")
             << "}";
      }
      json << "],";
      json << "\"finished\":" << (this->simulationFinished ? "true" : "false") << ",";
      json << "\"finish_line_crossed\":" << (this->finishLine.crossed ? "true" : "false") << ",";
      json << "\"heading\":" << (this->finishLine.crossed ? this->finishLine.robotHeadingRad : 0.0) << ",";
      json << "\"heading_deg\":" << (this->finishLine.crossed ? this->finishLine.robotHeadingDeg : 0.0) << ",";
      json << "\"finished_backwards\":" << (this->finishLine.finishedBackwards ? "true" : "false");
      json << "}";

      gz::msgs::StringMsg msg;
      msg.set_data(json.str());
      this->scorePub.Publish(msg);
    }
  }

  void ScoringSystem::InitSharedMemory()
  {
    std::string path = GetScoreShmPath();
    this->shmFd = open(path.c_str(), O_RDWR | O_CREAT | O_TRUNC, 0666);
    if (this->shmFd >= 0)
    {
      fchmod(this->shmFd, 0666);
      if (ftruncate(this->shmFd, sizeof(ScoreData)) == 0)
      {
        void *ptr = mmap(nullptr, sizeof(ScoreData), PROT_READ | PROT_WRITE, MAP_SHARED, this->shmFd, 0);
        if (ptr != MAP_FAILED)
        {
          this->shmPtr = static_cast<ScoreData*>(ptr);
          this->shmPtr->magic = kScoreMagic;
          this->shmPtr->totalScore = 0.0;
          this->shmPtr->maxScore = 0.0;
          this->shmPtr->finished = 0;
          this->shmPtr->exitOnFinish = this->exitOnFinish ? 1 : 0;
        }
      }
    }
  }

  void ScoringSystem::UpdateSharedMemory(double _totalScore, double _maxScore)
  {
    if (this->shmPtr && this->shmPtr != MAP_FAILED)
    {
      this->shmPtr->totalScore = _totalScore;
      this->shmPtr->maxScore = _maxScore;
      this->shmPtr->finished = this->simulationFinished ? 1 : 0;
      this->shmPtr->exitOnFinish = this->exitOnFinish ? 1 : 0;
      this->shmPtr->magic = kScoreMagic;
    }
  }

  void ScoringSystem::CleanupSharedMemory()
  {
    if (this->shmPtr && this->shmPtr != MAP_FAILED)
    {
      munmap(this->shmPtr, sizeof(ScoreData));
      this->shmPtr = nullptr;
    }
    if (this->shmFd >= 0)
    {
      close(this->shmFd);
      this->shmFd = -1;
    }
  }

  void ScoringSystem::WriteJsonReport(double _simTime, const std::string &_statusReason)
  {
    double waypointScore = 0.0;
    double maxScore = 0.0;
    int clearedCount = 0;

    for (const auto &wp : this->waypoints)
    {
      waypointScore += wp.score;
      maxScore += wp.maxScore;
      if (wp.validated) clearedCount++;
    }

    double currentPenalties = 0.0;
    int penaltyCount = 0;
    for (const auto &cb : this->cardinalBuoys)
    {
      if (cb.penaltyApplied)
      {
        currentPenalties += this->cardinalPenalty;
        penaltyCount++;
      }
    }
    this->totalPenalties = currentPenalties;
    double totalScore = waypointScore - this->totalPenalties;

    // Minimum floor score: keep standard waypoint points, but ensure at least 2.0 pts on non-collision runs
    if (totalScore < 2.0)
    {
      totalScore = 2.0;
    }

    double totalRunTime = (this->finishLine.crossed ? this->finishLine.crossingTime : _simTime) - this->startSimTime;
    if (totalRunTime < 0.0) totalRunTime = 0.0;

    std::ostringstream json;
    json << std::fixed << std::setprecision(3);
    json << "{\n";
    json << "  \"score\": " << totalScore << ",\n";
    json << "  \"total_score\": " << totalScore << ",\n";
    json << "  \"waypoint_score\": " << waypointScore << ",\n";
    json << "  \"total_penalties\": " << this->totalPenalties << ",\n";
    json << "  \"penalties\": " << this->totalPenalties << ",\n";
    json << "  \"penalty_count\": " << penaltyCount << ",\n";
    json << "  \"cardinal_penalty_rate\": " << this->cardinalPenalty << ",\n";
    json << "  \"cardinal_radius\": " << this->cardinalCircleRadius << ",\n";
    json << "  \"max_score\": " << maxScore << ",\n";
    json << "  \"sim_time\": " << _simTime << ",\n";
    json << "  \"total_time\": " << totalRunTime << ",\n";
    json << "  \"total_run_time\": " << totalRunTime << ",\n";
    json << "  \"run_time\": " << totalRunTime << ",\n";
    json << "  \"start_time\": " << this->startSimTime << ",\n";
    if (this->finishLine.crossed)
      json << "  \"finish_time\": " << this->finishLine.crossingTime << ",\n";
    else
      json << "  \"finish_time\": null,\n";
    json << "  \"timeout\": " << this->timeoutSec << ",\n";
    json << "  \"reason\": \"" << _statusReason << "\",\n";
    json << "  \"success\": " << (this->finishLine.crossed ? "true" : "false") << ",\n";
    json << "  \"finish_line_crossed\": " << (this->finishLine.crossed ? "true" : "false") << ",\n";

    if (this->finishLine.crossed)
    {
      json << "  \"heading\": " << this->finishLine.robotHeadingRad << ",\n";
      json << "  \"heading_deg\": " << this->finishLine.robotHeadingDeg << ",\n";
      json << "  \"heading_rad\": " << this->finishLine.robotHeadingRad << ",\n";
      json << "  \"robot_heading\": " << this->finishLine.robotHeadingRad << ",\n";
      json << "  \"robot_heading_deg\": " << this->finishLine.robotHeadingDeg << ",\n";
      json << "  \"robot_heading_rad\": " << this->finishLine.robotHeadingRad << ",\n";
      json << "  \"finish_heading\": " << this->finishLine.robotHeadingRad << ",\n";
      json << "  \"finish_heading_deg\": " << this->finishLine.robotHeadingDeg << ",\n";
      json << "  \"finish_heading_rad\": " << this->finishLine.robotHeadingRad << ",\n";
      json << "  \"relative_heading_deg\": " << this->finishLine.relativeHeadingDeg << ",\n";
      json << "  \"relative_heading_rad\": " << this->finishLine.relativeHeadingRad << ",\n";
      json << "  \"finished_backwards\": " << (this->finishLine.finishedBackwards ? "true" : "false") << ",\n";
    }
    else
    {
      json << "  \"heading\": null,\n";
      json << "  \"heading_deg\": null,\n";
      json << "  \"heading_rad\": null,\n";
      json << "  \"robot_heading\": null,\n";
      json << "  \"robot_heading_deg\": null,\n";
      json << "  \"robot_heading_rad\": null,\n";
      json << "  \"finish_heading\": null,\n";
      json << "  \"finish_heading_deg\": null,\n";
      json << "  \"finish_heading_rad\": null,\n";
      json << "  \"relative_heading_deg\": null,\n";
      json << "  \"relative_heading_rad\": null,\n";
      json << "  \"finished_backwards\": false,\n";
    }

    json << "  \"finish_line_count\": " << this->finishLineCount << ",\n";
    json << "  \"finish_line\": {\n";
    json << "    \"name\": \"" << this->finishLine.name << "\",\n";
    json << "    \"crossed\": " << (this->finishLine.crossed ? "true" : "false") << ",\n";
    if (this->finishLine.crossed)
    {
      json << "    \"crossing_time\": " << this->finishLine.crossingTime << ",\n";
      json << "    \"heading\": " << this->finishLine.robotHeadingRad << ",\n";
      json << "    \"heading_deg\": " << this->finishLine.robotHeadingDeg << ",\n";
      json << "    \"heading_rad\": " << this->finishLine.robotHeadingRad << ",\n";
      json << "    \"robot_heading_deg\": " << this->finishLine.robotHeadingDeg << ",\n";
      json << "    \"robot_heading_rad\": " << this->finishLine.robotHeadingRad << ",\n";
      json << "    \"finish_line_yaw_deg\": " << (this->finishLine.pose.Rot().Yaw() * 180.0 / M_PI) << ",\n";
      json << "    \"relative_heading_deg\": " << this->finishLine.relativeHeadingDeg << ",\n";
      json << "    \"relative_heading_rad\": " << this->finishLine.relativeHeadingRad << ",\n";
      json << "    \"finished_backwards\": " << (this->finishLine.finishedBackwards ? "true" : "false") << ",\n";
      json << "    \"position\": {\"x\": " << this->finishLine.crossingPos.X() << ", \"y\": " << this->finishLine.crossingPos.Y() << ", \"z\": " << this->finishLine.crossingPos.Z() << "}\n";
    }
    else
    {
      json << "    \"crossing_time\": null,\n";
      json << "    \"heading\": null,\n";
      json << "    \"heading_deg\": null,\n";
      json << "    \"heading_rad\": null,\n";
      json << "    \"robot_heading_deg\": null,\n";
      json << "    \"robot_heading_rad\": null,\n";
      json << "    \"finish_line_yaw_deg\": " << (this->finishLine.isDiscovered ? (this->finishLine.pose.Rot().Yaw() * 180.0 / M_PI) : 0.0) << ",\n";
      json << "    \"relative_heading_deg\": null,\n";
      json << "    \"relative_heading_rad\": null,\n";
      json << "    \"finished_backwards\": false,\n";
      json << "    \"position\": null\n";
    }
    json << "  },\n";

    json << "  \"all_waypoints_done\": " << (clearedCount == static_cast<int>(this->waypoints.size()) ? "true" : "false") << ",\n";
    json << "  \"waypoints_cleared\": " << clearedCount << ",\n";
    json << "  \"total_waypoints\": " << this->waypoints.size() << ",\n";

    // Detailed array of waypoints
    json << "  \"waypoints\": [\n";
    for (size_t i = 0; i < this->waypoints.size(); ++i)
    {
      const auto &wp = this->waypoints[i];
      json << "    {\n";
      json << "      \"name\": \"" << wp.name << "\",\n";
      json << "      \"score\": " << wp.score << ",\n";
      json << "      \"max_score\": " << wp.maxScore << ",\n";
      json << "      \"validated\": " << (wp.validated ? "true" : "false") << ",\n";
      json << "      \"validation_time\": " << (wp.validated ? std::to_string(wp.validationTime) : "null") << ",\n";
      json << "      \"min_distance\": " << wp.minDistance << ",\n";
      json << "      \"position\": {\"x\": " << wp.position.X() << ", \"y\": " << wp.position.Y() << ", \"z\": " << wp.position.Z() << "}\n";
      json << "    }" << (i + 1 < this->waypoints.size() ? ",\n" : "\n");
    }
    json << "  ],\n";

    // Also include dictionary by waypoint name for direct key lookup
    json << "  \"waypoint_details\": {\n";
    for (size_t i = 0; i < this->waypoints.size(); ++i)
    {
      const auto &wp = this->waypoints[i];
      json << "    \"" << wp.name << "\": {\n";
      json << "      \"score\": " << wp.score << ",\n";
      json << "      \"max_score\": " << wp.maxScore << ",\n";
      json << "      \"validated\": " << (wp.validated ? "true" : "false") << ",\n";
      json << "      \"validation_time\": " << (wp.validated ? std::to_string(wp.validationTime) : "null") << ",\n";
      json << "      \"min_distance\": " << wp.minDistance << "\n";
      json << "    }" << (i + 1 < this->waypoints.size() ? ",\n" : "\n");
    }
    json << "  },\n";

    // Detailed array of cardinal buoys and overpass status
    json << "  \"cardinal_buoys\": [\n";
    for (size_t i = 0; i < this->cardinalBuoys.size(); ++i)
    {
      const auto &cb = this->cardinalBuoys[i];
      json << "    {\n";
      json << "      \"name\": \"" << cb.name << "\",\n";
      json << "      \"type\": \"" << cb.typeString << "\",\n";
      json << "      \"overpassed\": " << (cb.overpassed ? "true" : "false") << ",\n";
      json << "      \"overpass_side\": \"" << cb.overpassSide << "\",\n";
      json << "      \"penalty_applied\": " << (cb.penaltyApplied ? "true" : "false") << ",\n";
      json << "      \"penalty_points\": " << (cb.penaltyApplied ? this->cardinalPenalty : 0.0) << ",\n";
      json << "      \"overpass_time\": " << (cb.overpassed ? std::to_string(cb.overpassTime) : "null") << ",\n";
      json << "      \"min_distance\": " << cb.minDistance << "\n";
      json << "    }" << (i + 1 < this->cardinalBuoys.size() ? ",\n" : "\n");
    }
    json << "  ]\n";
    json << "}\n";

    std::string content = json.str();

    // List of target destinations to write
    std::vector<std::string> targetPaths;
    targetPaths.push_back(this->outputFile);
    if (this->outputFile != "scoring_result.json")
      targetPaths.push_back("scoring_result.json");
    targetPaths.push_back("/workspace/scoring_result.json");

    if (std::filesystem::exists("/workspace/output"))
      targetPaths.push_back("/workspace/output/scoring_result.json");
    else if (std::filesystem::exists("output"))
      targetPaths.push_back("output/scoring_result.json");
    else if (std::filesystem::exists("/output"))
      targetPaths.push_back("/output/scoring_result.json");

    for (const auto &path : targetPaths)
    {
      try
      {
        std::filesystem::path p(path);
        if (p.has_parent_path())
        {
          std::filesystem::create_directories(p.parent_path());
        }
        std::ofstream out(path);
        if (out.is_open())
        {
          out << content;
          out.flush();
          out.close();
          std::cout << " [ScoringSystem] 📄 Wrote scoring report to: " << path << std::endl;
        }
      }
      catch (...)
      {
        // ignore write failures for optional fallback paths
      }
    }
    sync();
  }

  void ScoringSystem::StopSimulation()
  {
    std::cout << " [ScoringSystem] Requesting simulation server termination..." << std::endl;

    // 1. Send ServerControl request to /server_control with stop = true
    gz::msgs::ServerControl req;
    req.set_stop(true);

    this->node.Request<gz::msgs::ServerControl, gz::msgs::Boolean>(
        "/server_control", req,
        [](const gz::msgs::Boolean &_rep, const bool _result)
        {
          if (_result && _rep.data())
          {
            std::cout << " [ScoringSystem] Server stop acknowledged." << std::endl;
          }
        });

    // 2. Also publish WorldControl with pause = true to immediately pause physics
    gz::msgs::WorldControl pauseMsg;
    pauseMsg.set_pause(true);
    auto worldControlPub = this->node.Advertise<gz::msgs::WorldControl>("/world/" + this->worldName + "/control");
    worldControlPub.Publish(pauseMsg);

    // 3. If exit_on_finish is enabled, trigger complete shutdown of Gazebo
    if (this->exitOnFinish)
    {
      this->TriggerShutdown();
    }
  }

  void ScoringSystem::TriggerShutdown()
  {
    std::cout << " [ScoringSystem] 🚪 Exit on finish enabled: initiating Gazebo shutdown sequence..." << std::endl;

    std::thread([this]() {
      // 1. Grace period for file sync and GUI IPC event loop
      std::this_thread::sleep_for(std::chrono::milliseconds(400));

      // 2. Request GUI client to quit gracefully via SIGINT if still running
      killProcessesByName("gz-sim-gui-client", SIGINT);
      system("pkill -INT -f gz-sim-gui-client >/dev/null 2>&1");

      // 3. Wait up to 1.5s for graceful shutdown of GUI
      std::this_thread::sleep_for(std::chrono::milliseconds(1200));

      // 4. Send SIGINT to our own server process to trigger Gazebo Server's graceful SIGINT handler
      std::cout << " [ScoringSystem] Terminating Gazebo Sim server process..." << std::endl;
      kill(getpid(), SIGINT);
      system("pkill -INT -f gz-sim-main >/dev/null 2>&1");

      // 5. If still alive after 1 second, send SIGTERM
      std::this_thread::sleep_for(std::chrono::milliseconds(1000));
      killProcessesByName("gz-sim-gui-client", SIGTERM);
      killProcessesByName("gz-sim-main", SIGTERM);
      kill(getpid(), SIGTERM);
      system("pkill -TERM -f gz-sim >/dev/null 2>&1");

      // 6. Final safety fallback
      std::this_thread::sleep_for(std::chrono::milliseconds(500));
      std::_Exit(0);
    }).detach();
  }
}

// Register the system plugin
GZ_ADD_PLUGIN(
    regatta::ScoringSystem,
    gz::sim::System,
    regatta::ScoringSystem::ISystemConfigure,
    regatta::ScoringSystem::ISystemPreUpdate)

GZ_ADD_PLUGIN_ALIAS(regatta::ScoringSystem, "regatta::ScoringSystem")
