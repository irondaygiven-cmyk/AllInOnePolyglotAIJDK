import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Effects 1.0

Rectangle {
    height: 48
    color: "#1a1a1a"
    opacity: 0.96

    MultiEffect {
        source: parent
        anchors.fill: parent
        blurEnabled: true
        blur: 18
    }

    MouseArea {
        anchors.fill: parent
        onPressed: root.startSystemMove()
    }

    Text {
        text: "AllInOnePolyglotAIJDK v3.3"
        anchors.left: parent.left
        anchors.leftMargin: 24
        anchors.verticalCenter: parent.verticalCenter
        color: "#00ff9d"
        font.pixelSize: 17
        font.bold: true
    }
}
