import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

GlassCard {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 20

        Label {
            text: "Development Build Tools"
            font.pixelSize: 26
            color: "#00ff9d"
        }

        RowLayout {
            ModernButton {
                text: "Download Java Development Toolkit"
                onClicked: backend.openJavaToolkitDownload()
            }
            ModernButton {
                text: "Check Java Development Toolkit"
                onClicked: backend.checkJavaToolkit()
            }
        }

        GroupBox {
            title: "Project Build Configuration"
            Layout.fillWidth: true
            ColumnLayout {
                ModernButton {
                    text: "Create XML-based Build Project"
                    onClicked: backend.createProjectWithBuildSystem("xml")
                }
                ModernButton {
                    text: "Create Script-based Build Project"
                    onClicked: backend.createProjectWithBuildSystem("script")
                }
            }
        }

        GroupBox {
            title: "Git"
            Layout.fillWidth: true
            ColumnLayout {
                RowLayout {
                    ModernButton { text: "Check Git";    onClicked: backend.checkGit() }
                    ModernButton { text: "Download Git"; onClicked: backend.openGitDownload() }
                }
                RowLayout {
                    ModernButton { text: "git status"; onClicked: backend.runGitCommand("status") }
                    ModernButton { text: "git init";   onClicked: backend.runGitCommand("init") }
                    ModernButton { text: "git add .";  onClicked: backend.runGitCommand("add .") }
                }
                RowLayout {
                    ModernButton { text: "git commit"; onClicked: backend.runGitCommand("commit -m \"update\"") }
                    ModernButton { text: "git push";   onClicked: backend.runGitCommand("push") }
                    ModernButton { text: "git pull";   onClicked: backend.runGitCommand("pull") }
                }
            }
        }

        GroupBox {
            title: "System Command Shell"
            Layout.fillWidth: true
            ColumnLayout {
                RowLayout {
                    ModernButton {
                        text: "Open Command Shell"
                        onClicked: backend.runSystemCommandShell("powershell", false)
                    }
                    ModernButton {
                        text: "Open Command Shell as Administrator"
                        onClicked: backend.runSystemCommandShell("powershell", true)
                    }
                }
                TextArea {
                    id: terminalArea
                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    readOnly: true
                    font.family: "Consolas"
                    background: Rectangle { color: "#1a1a1a"; radius: 12 }
                }
            }
        }

        TextArea {
            id: buildLogArea
            Layout.fillHeight: true
            Layout.fillWidth: true
            readOnly: true
            font.family: "Consolas"
            background: Rectangle { color: "#1a1a1a"; radius: 12 }
        }
    }

    Connections {
        target: backend
        function onDeployLogUpdated(log) { buildLogArea.append(log) }
        function onTerminalOutput(text)  { terminalArea.append(text) }
    }
}
