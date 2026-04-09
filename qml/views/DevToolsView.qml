import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

GlassCard {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 16

        Label {
            text: "Developer Tools – Security & Analysis"
            font.pixelSize: 26
            color: "#00ff9d"
        }

        ModernButton {
            text: "Recreate Current Page & Security Scan"
            onClicked: backend.recreateAndSecurityScan()
        }

        ModernButton {
            text: "View Categorized JS-Learning_Library"
            onClicked: backend.viewLibraries()
        }

        ModernButton {
            text: "View JS-Mal_LL (Malicious)"
            onClicked: backend.viewLibraries()
        }

        TextField {
            id: directCommand
            Layout.fillWidth: true
            placeholderText: "Direct JS command"
        }

        ModernButton {
            text: "Execute Direct Command"
            onClicked: backend.sendDevToolsCommand(directCommand.text)
        }

        TextArea {
            id: logArea
            Layout.fillHeight: true
            Layout.fillWidth: true
            readOnly: true
            font.family: "Consolas"
            background: Rectangle { color: "#1a1a1a"; radius: 12 }
        }
    }

    Connections {
        target: backend
        function onDeployLogUpdated(log) { logArea.append(log) }
    }
}
