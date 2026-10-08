#ifndef REGATTA_SCORING_WIDGET_HH_
#define REGATTA_SCORING_WIDGET_HH_

#include <gz/gui/Plugin.hh>
#include <QTimer>
#include "RegattaScoreIPC.hh"

namespace regatta
{
  class ScoringWidget : public gz::gui::Plugin
  {
    Q_OBJECT

    Q_PROPERTY(double totalScore READ TotalScore NOTIFY DataChanged)

    public: ScoringWidget();
    public: ~ScoringWidget() override;

    public: void LoadConfig(const tinyxml2::XMLElement *_pluginElem) override;

    public: double TotalScore() const { return this->totalScore; }

    signals: void DataChanged();

    private slots: void UpdateScoreFromIPC();

    private: QTimer *pollTimer{nullptr};
    private: ScoreData *shmPtr{nullptr};
    private: int shmFd{-1};
    private: double totalScore{0.0};
    private: bool exitOnFinish{false};
    private: bool exitTriggered{false};
  };
}

#endif // REGATTA_SCORING_WIDGET_HH_
