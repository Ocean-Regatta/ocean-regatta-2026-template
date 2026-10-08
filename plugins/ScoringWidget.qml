import QtQuick 2.9
import QtQuick.Controls 2.2
import QtQuick.Layouts 1.3

Rectangle {
  id: root
  color: "#0f172a"
  border.color: "#334155"
  border.width: 1
  radius: 6
  implicitWidth: 180
  implicitHeight: 70
  anchors.fill: parent

  readonly property var scoringWidget: (typeof _ScoringWidget !== 'undefined' && _ScoringWidget !== null) ? _ScoringWidget : null

  ColumnLayout {
    anchors.centerIn: parent
    spacing: 3

    Text {
      text: "SCORE"
      color: "#94a3b8"
      font.pixelSize: 11
      font.bold: true
      font.letterSpacing: 1.2
      Layout.alignment: Qt.AlignHCenter
    }

    Text {
      text: (scoringWidget ? scoringWidget.totalScore.toFixed(2) : "0.00") + " pts"
      color: (scoringWidget && scoringWidget.totalScore > 0) ? "#22c55e" : "#f8fafc"
      font.bold: true
      font.pixelSize: 24
      Layout.alignment: Qt.AlignHCenter
    }
  }
}
