import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Effects 1.0
import QtQuick.Window 2.15
import "components"
import "views"

Window {
    id: root
    visible: true
    width: 1920
    height: 1080
    color: "transparent"
    flags: Qt.Window | Qt.FramelessWindowHint
    title: "AllInOnePolyglotAIJDK v3.3"

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
        function onChatUpdated(reply) {
            chatModel.append({ text: reply, isUser: false })
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
