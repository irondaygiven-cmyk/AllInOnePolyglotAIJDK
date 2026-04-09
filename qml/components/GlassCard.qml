import QtQuick 2.15
import QtQuick.Effects 1.0

Rectangle {
    id: glass
    radius: 28
    color: "#1f1f1f"
    border.color: "#00ff9d"
    border.width: 1
    opacity: 0.95

    MultiEffect {
        source: glass
        anchors.fill: glass
        blurEnabled: true
        blur: 32
        brightness: -0.13
        shadowEnabled: true
        shadowColor: "#00ff9d"
        shadowBlur: 55
        shadowOpacity: 0.28
    }
}
