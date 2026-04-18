import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

// DevToolsView.qml — Developer Tools & Security Analysis panel
//
// ── Communication paths ──────────────────────────────────────────────────────
//
//  All buttons → backend slot (PySide6 QObject) → effect + deployLogUpdated.emit
//    → onDeployLogUpdated(log) → logArea.append(log)
//
//  "Recreate Page & Security Scan"
//    → backend.recreateAndSecurityScan()
//        → backend.sendToAgent(predefined prompt)
//            → query_ai() → HTTP POST /chat/completions → AI reply
//            → chatUpdated.emit(reply)    [chat panel receives reply]
//            → deployLogUpdated.emit(...) [logArea updated below]
//
//  "View Categorized JS-Learning_Library"
//    → backend.viewLibraries()
//        → gzip.open("libraries_compressed.gz") → load JSON
//        → deployLogUpdated.emit(summary)
//
//  "Execute Direct Command"
//    → backend.sendDevToolsCommand(directCommand.text)
//        → deployLogUpdated.emit("Executing: " + cmd)
//
//  Undo/Redo (chat-level, reflected here via deployLogReset)
//    → backend.undoChatOp() / redoChatOp()   [called from main.qml]
//        → deployLogReset.emit(full_log_str)
//        → onDeployLogReset(text) → logArea.text = text   [resets this view]
//
// ─────────────────────────────────────────────────────────────────────────────

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
        // onDeployLogUpdated: append incremental log lines
        // Path: backend.deployLogUpdated(str) → logArea.append(str)
        function onDeployLogUpdated(log) { logArea.append(log) }
        // onDeployLogReset: full reset after an undo/redo operation
        // Path: backend.deployLogReset(str) → logArea.text = str
        function onDeployLogReset(text) { logArea.text = text }
    }
}
