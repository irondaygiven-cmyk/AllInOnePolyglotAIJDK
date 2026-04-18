import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Effects 1.0
import QtQuick.Window 2.15
import "components"
import "views"

// main.qml — AllInOnePolyglotAIJDK QML root window
//
// ── Communication paths ──────────────────────────────────────────────────────
//
//  Chat input → backend
//    [TextField accepted / SEND clicked]
//    → root.sendMessage()
//        → chatModel.append({text, isUser:true})     [user bubble added]
//        → backend.sendToAgent(chatInput.text)        [→ AI → HTTP → reply]
//            → chatUpdated.emit(reply)
//                → onChatUpdated(reply) → chatModel.append({text:reply, isUser:false})
//            → undoStateChanged.emit(canUndo, canRedo)
//                → onUndoStateChanged → canUndoChat / canRedoChat updated
//                    → ↩/↪ buttons' enabled binding re-evaluated
//
//  Chat Undo / Redo (±20 steps)
//    [↩ Undo button clicked] → backend.undoChatOp()
//        → _chat_stack.undo()
//        → chatHistoryReset.emit(json_str)
//            → onChatHistoryReset(json_str) → chatModel.clear() + rebuild
//        → deployLogReset.emit(log_str)
//            → each view's onDeployLogReset → TextArea.text = log_str
//        → undoStateChanged.emit(canUndo, canRedo)
//    [↪ Redo button clicked] → backend.redoChatOp()  [symmetric]
//
//  Research (from Slint UI path — QML equivalent also available via BuildToolsView)
//    backend.selectSynthesisTarget() → QFileDialog → _synthesis_target
//    backend.beginDeconstruction()   → SynthesisAgent thread → deployLogUpdated per step
//
// ─────────────────────────────────────────────────────────────────────────────

Window {
    id: root
    visible: true
    width: 1920
    height: 1080
    color: "transparent"
    flags: Qt.Window | Qt.FramelessWindowHint
    title: "AllInOnePolyglotAIJDK v3.3"

    // ── Undo/Redo state (updated by backend.undoStateChanged signal) ──────────
    // Path: backend.undoStateChanged(canUndo, canRedo) → onUndoStateChanged
    //       → canUndoChat / canRedoChat → ↩/↪ button enabled bindings
    property bool canUndoChat: false
    property bool canRedoChat: false

    // Global background with subtle glass effect
    Rectangle {
        anchors.fill: parent
        color: "#0a0a0a"

        MultiEffect {
            source: parent
            anchors.fill: parent
            blurEnabled: true
            blur: 28
            brightness: -0.09
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // Custom Fluent Title Bar
        TitleBar { id: titleBar }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // LEFT: Chat Panel
            GlassCard {
                Layout.preferredWidth: 740
                Layout.fillHeight: true
                radius: 28

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 28
                    spacing: 20

                    EnvironmentPills {}

                    ScrollView {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        ListView {
                            id: chatList
                            model: ListModel { id: chatModel }
                            spacing: 24
                            delegate: ChatBubble {}
                        }
                    }

                    RowLayout {
                        TextField {
                            id: chatInput
                            Layout.fillWidth: true
                            placeholderText: "Send directions to the Agent..."
                            onAccepted: root.sendMessage()
                        }
                        ModernButton {
                            text: "SEND"
                            onClicked: root.sendMessage()
                        }
                        // ↩ Undo: revert last chat exchange (up to 20 steps)
                        // Path: → backend.undoChatOp() → _chat_stack.undo()
                        //       → chatHistoryReset + deployLogReset emitted
                        ModernButton {
                            text: "↩"
                            enabled: root.canUndoChat
                            onClicked: backend.undoChatOp()
                        }
                        // ↪ Redo: re-apply undone chat exchange (up to 20 steps)
                        // Path: → backend.redoChatOp() → _chat_stack.redo()
                        //       → chatHistoryReset + deployLogReset emitted
                        ModernButton {
                            text: "↪"
                            enabled: root.canRedoChat
                            onClicked: backend.redoChatOp()
                        }
                    }
                }
            }

            // RIGHT: Content Area
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                TabBar {
                    id: tabBar
                    Layout.fillWidth: true
                    TabButton { text: "DevTools & Security" }
                    TabButton { text: "Development Build Tools" }
                    TabButton { text: "Settings" }
                }

                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: tabBar.currentIndex
                    DevToolsView {}
                    BuildToolsView {}
                    SettingsView {}
                }
            }
        }
    }

    // Global backend connections
    Connections {
        target: backend

        // Chat reply received — append AI bubble to chat list
        // Path: backend.chatUpdated(reply) → chatModel.append({isUser:false})
        function onChatUpdated(reply) {
            chatModel.append({ text: reply, isUser: false })
            chatList.positionViewAtEnd()
        }

        // Undo/redo availability changed — update ↩/↪ enabled state
        // Path: backend.undoStateChanged(canUndo, canRedo) → root.canUndoChat/canRedoChat
        function onUndoStateChanged(canUndo, canRedo) {
            root.canUndoChat = canUndo
            root.canRedoChat = canRedo
        }

        // Full chat history reset after undo/redo — rebuild chatModel from JSON
        // Path: backend.chatHistoryReset(json_str)
        //       → JSON.parse → chatModel.clear() + chatModel.append(each entry)
        function onChatHistoryReset(jsonStr) {
            var history = JSON.parse(jsonStr)
            chatModel.clear()
            for (var i = 0; i < history.length; i++) {
                chatModel.append(history[i])
            }
            chatList.positionViewAtEnd()
        }
    }

    function sendMessage() {
        if (chatInput.text.trim() === "") return
        chatModel.append({ text: chatInput.text, isUser: true })
        chatList.positionViewAtEnd()
        backend.sendToAgent(chatInput.text)
        chatInput.clear()
    }
}
