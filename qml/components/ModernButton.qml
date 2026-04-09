import QtQuick 2.15
import QtQuick.Controls 2.15

Button {
    hoverEnabled: true
    background: Rectangle {
        radius: 14
        color: parent.down ? "#00cc7a" : (parent.hovered ? "#00ff9d" : "#2a2a2a")
        border.color: "#00ff9d"
        border.width: parent.hovered ? 2 : 1
    }
    scale: hovered ? 1.06 : 1.0
    Behavior on scale { NumberAnimation { duration: 110 } }
}
