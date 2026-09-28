#include "ScoringWidget.hh"
#include <gz/gui/Application.hh>
#include <gz/plugin/Register.hh>
#include <QCoreApplication>
#include <cmath>
#include <iostream>
#include <string>
#include <algorithm>

namespace regatta
{
  ScoringWidget::ScoringWidget()
  {
    this->title = "Regatta Scoring";
  }

  ScoringWidget::~ScoringWidget()
  {
    if (this->pollTimer)
    {
      this->pollTimer->stop();
      delete this->pollTimer;
      this->pollTimer = nullptr;
    }
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

  void ScoringWidget::LoadConfig(const tinyxml2::XMLElement *_pluginElem)
  {
    if (this->title.empty())
      this->title = "Regatta Scoring";

    if (_pluginElem)
    {
      const tinyxml2::XMLElement *exitElem = _pluginElem->FirstChildElement("exit_on_finish");
      if (!exitElem)
        exitElem = _pluginElem->FirstChildElement("exit_on_completion");
      if (!exitElem)
        exitElem = _pluginElem->FirstChildElement("auto_exit");

      if (exitElem && exitElem->GetText())
      {
        std::string val = exitElem->GetText();
        std::transform(val.begin(), val.end(), val.begin(), ::tolower);
        if (val.empty() || val == "true" || val == "1" || val == "yes")
          this->exitOnFinish = true;
      }
    }

    if (this->Context())
    {
      this->Context()->setContextProperty("ScoringWidget", this);
    }

    this->pollTimer = new QTimer(this);
    connect(this->pollTimer, &QTimer::timeout, this, &ScoringWidget::UpdateScoreFromIPC);
    this->pollTimer->start(100); // 10 Hz refresh
  }

  void ScoringWidget::UpdateScoreFromIPC()
  {
    if (!this->shmPtr)
    {
      std::string path = GetScoreShmPath();
      this->shmFd = open(path.c_str(), O_RDONLY);
      if (this->shmFd >= 0)
      {
        void *ptr = mmap(nullptr, sizeof(ScoreData), PROT_READ, MAP_SHARED, this->shmFd, 0);
        if (ptr != MAP_FAILED)
        {
          this->shmPtr = static_cast<ScoreData*>(ptr);
        }
        else
        {
          close(this->shmFd);
          this->shmFd = -1;
        }
      }
    }

    if (this->shmPtr && this->shmPtr->magic == kScoreMagic)
    {
      double newScore = this->shmPtr->totalScore;
      if (std::abs(newScore - this->totalScore) > 1e-4)
      {
        this->totalScore = newScore;
        emit this->DataChanged();
      }

      bool shouldExit = (this->shmPtr->finished == 1) && (this->shmPtr->exitOnFinish == 1 || this->exitOnFinish);
      if (shouldExit && !this->exitTriggered)
      {
        this->exitTriggered = true;
        std::cout << " [ScoringWidget] Simulation completed with exit_on_finish enabled. Closing GUI window..." << std::endl;
        QTimer::singleShot(150, this, []() {
          if (gz::gui::App())
          {
            gz::gui::App()->exit(0);
          }
          else
          {
            QCoreApplication::quit();
          }
        });
      }
    }
  }
}

// Register GUI plugin
GZ_ADD_PLUGIN(regatta::ScoringWidget, gz::gui::Plugin)
