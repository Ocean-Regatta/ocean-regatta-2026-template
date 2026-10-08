#ifndef REGATTA_SCORE_IPC_HH_
#define REGATTA_SCORE_IPC_HH_

#include <cstdint>
#include <string>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

namespace regatta
{
  constexpr uint32_t kScoreMagic = 0x53434F52; // "SCOR"

  struct ScoreData
  {
    uint32_t magic;
    double totalScore;
    double maxScore;
    uint8_t finished;
    uint8_t exitOnFinish;
    uint8_t padding[6];
  };

  inline std::string GetScoreShmPath()
  {
    struct stat st;
    if (stat("/dev/shm", &st) == 0 && S_ISDIR(st.st_mode))
      return "/dev/shm/regatta_score.dat";
    return "/tmp/regatta_score.dat";
  }
}

#endif // REGATTA_SCORE_IPC_HH_
