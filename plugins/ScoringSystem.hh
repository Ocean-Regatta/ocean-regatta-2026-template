#ifndef REGATTA_SCORING_SYSTEM_HH_
#define REGATTA_SCORING_SYSTEM_HH_

#include <gz/sim/System.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/EventManager.hh>
#include <gz/transport/Node.hh>
#include <gz/math/Vector3.hh>

#include <gz/math/Pose3.hh>

#include <string>
#include <vector>
#include <memory>
#include <chrono>

#include "RegattaScoreIPC.hh"

namespace regatta
{
  /// \brief Information tracked for a single waypoint
  struct WaypointInfo
  {
    std::string name;
    gz::sim::Entity modelEntity{gz::sim::kNullEntity};
    gz::sim::Entity visualEntity{gz::sim::kNullEntity};
    std::string visualScopedName;
    gz::math::Vector3d position{0, 0, 0};

    double currentDistance{999.0};
    double minDistance{999.0};
    double score{0.0};
    double maxScore{2.0};
    double bestRatio{0.0};
    double lastVisualRatio{-1.0};

    bool wasInside{false};
    bool validated{false};
    double validationTime{-1.0};
    bool isDone{false};
  };

  /// \brief Semantic category of cardinal buoy
  enum class CardinalType
  {
    NORTH,
    SOUTH,
    EAST,
    WEST,
    UNKNOWN
  };

  /// \brief Information tracked for a cardinal buoy
  struct CardinalBuoyInfo
  {
    std::string name;
    gz::sim::Entity modelEntity{gz::sim::kNullEntity};
    gz::math::Vector3d position{0, 0, 0};
    CardinalType type{CardinalType::UNKNOWN};
    std::string typeString{"unknown"};

    bool insideCircle{false};
    bool overpassed{false};
    bool penaltyApplied{false};
    double overpassTime{-1.0};
    double minDistance{999.0};
    double lastDeterminant{0.0};
    double trajectoryDeterminant{0.0};
    std::string overpassSide{"none"}; // "correct", "wrong", or "none"
  };

  /// \brief Information tracked for the finish line
  struct FinishLineInfo
  {
    std::string name{"finish_line"};
    gz::sim::Entity modelEntity{gz::sim::kNullEntity};
    gz::sim::Entity linkEntity{gz::sim::kNullEntity};
    gz::sim::Entity visualEntity{gz::sim::kNullEntity};
    std::string visualScopedName;
    gz::math::Pose3d pose{0, 0, 0, 0, 0, 0};
    gz::math::Vector3d size{1.0, 20.0, 0.4};

    bool isDiscovered{false};
    bool crossed{false};
    double crossingTime{-1.0};
    double robotHeadingRad{0.0};
    double robotHeadingDeg{0.0};
    double relativeHeadingRad{0.0};
    double relativeHeadingDeg{0.0};
    gz::math::Vector3d crossingPos{0, 0, 0};
    bool finishedBackwards{false};
  };

  /// \brief Gazebo Sim System Plugin for Ocean Regatta Scoring System
  class ScoringSystem : public gz::sim::System,
                        public gz::sim::ISystemConfigure,
                        public gz::sim::ISystemPreUpdate
  {
    public: ScoringSystem();
    public: ~ScoringSystem() override;

    public: void Configure(
        const gz::sim::Entity &_entity,
        const std::shared_ptr<const sdf::Element> &_sdf,
        gz::sim::EntityComponentManager &_ecm,
        gz::sim::EventManager &_eventMgr) override;

    public: void PreUpdate(
        const gz::sim::UpdateInfo &_info,
        gz::sim::EntityComponentManager &_ecm) override;

    private: void DiscoverEntities(gz::sim::EntityComponentManager &_ecm);
    private: void UpdateWaypointVisual(
        WaypointInfo &_wp, double _r, double _g, double _b, double _a,
        gz::sim::EntityComponentManager &_ecm);
    private: void UpdateFinishLineVisual(
        double _r, double _g, double _b, double _a,
        gz::sim::EntityComponentManager &_ecm);
    private: void ProcessCardinalBuoys(
        double _robotX, double _robotY,
        double _prevX, double _prevY,
        double _simTime,
        bool &_stateChanged);
    private: void BroadcastScore(double _simTime);
    private: void InitSharedMemory();
    private: void UpdateSharedMemory(double _totalScore, double _maxScore);
    private: void CleanupSharedMemory();
    private: void WriteJsonReport(double _simTime, const std::string &_statusReason);
    private: void StopSimulation();
    private: void TriggerShutdown();

    // Configuration parameters
    private: bool exitOnFinish{false};
    private: std::string worldName{"practice_world"};
    private: std::string robotName{"blueboat"};
    private: std::string robotLinkName{"base_link"};
    private: std::string finishLineName{"finish_line"};
    private: gz::math::Vector3d configuredFinishLineSize{1.0, 20.0, 0.4};
    private: std::string outputFile{"scoring_result.json"};
    private: std::string scoreTopic{"/regatta/score"};
    private: double timeoutSec{180.0};
    private: double activationRadius{1.5};
    private: double validationRadius{0.3};
    private: double maxPointsPerWaypoint{2.0};
    private: double cardinalCircleRadius{20.0};
    private: double cardinalPenalty{2.0};
    private: std::vector<std::string> configuredWaypointNames;

    // Runtime state
    private: gz::transport::Node node;
    private: gz::transport::Node::Publisher colorPub;
    private: gz::transport::Node::Publisher scorePub;
    private: gz::sim::Entity robotEntity{gz::sim::kNullEntity};
    private: gz::sim::Entity robotLinkEntity{gz::sim::kNullEntity};
    private: gz::math::Vector3d robotCoGOffset{-0.3, 0.0, 0.0};
    private: std::vector<WaypointInfo> waypoints;
    private: std::vector<CardinalBuoyInfo> cardinalBuoys;
    private: double totalPenalties{0.0};
    private: FinishLineInfo finishLine;
    private: int finishLineCount{0};
    private: bool entitiesDiscovered{false};
    private: bool simulationFinished{false};
    private: bool hasStartTime{false};
    private: double startSimTime{0.0};
    private: gz::math::Vector3d startRobotPos{0, 0, 0};
    private: bool hasPrevRobotPos{false};
    private: gz::math::Vector3d prevRobotPos{0, 0, 0};
    private: double prevSimTime{0.0};
    private: std::chrono::steady_clock::time_point lastBroadcastTime;
    private: ScoreData *shmPtr{nullptr};
    private: int shmFd{-1};
  };
}

#endif // REGATTA_SCORING_SYSTEM_HH_

