import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

RowLayout {
    spacing: 8
    Repeater {
        model: ["Java", "DevTools", "Build", "General"]
        delegate: Button {
            text: modelData
            checkable: true
            checked: backend.current_environment === modelData.toLowerCase()
            onClicked: backend.setEnvironment(modelData.toLowerCase())

            background: Rectangle {
                radius: 9999
                color: parent.checked ? "#00ff9d" : "#2a2a2a"
                Behavior on color { ColorAnimation { duration: 160 } }
            }
        }
    }
}
