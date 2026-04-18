import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import "../components"

GlassCard {
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 32
        spacing: 20

        GroupBox {
            title: "File Operation History  [±20 operations]"
            Layout.fillWidth: true
            // Communication: buttons → backend.undoFileOp() / redoFileOp()
            //   → _file_stack.undo() / .redo()
            //   → file deleted / recreated on disk
            //   → deployLogUpdated.emit(msg) → buildLogArea.append(msg)
            ColumnLayout {
                RowLayout {
                    ModernButton {
                        text: "↩ Undo File Op"
                        onClicked: backend.undoFileOp()
                    }
                    ModernButton {
                        text: "↪ Redo File Op"
                        onClicked: backend.redoFileOp()
                    }
                }
            }
        }

        GroupBox {
            // Research / Pattern Synthesis — launch directly from Build Tools tab
            // Communication: buttons → backend.selectSynthesisTarget() / beginDeconstruction()
            //   selectSynthesisTarget  → QFileDialog → _synthesis_target set
            //   beginDeconstruction    → SynthesisAgent thread → deployLogUpdated per step
            title: "Pattern Synthesis  [Research]"
            Layout.fillWidth: true
            ColumnLayout {
                RowLayout {
                    ModernButton {
                        text: "Select Synthesis Target"
                        onClicked: backend.selectSynthesisTarget()
                    }
                    ModernButton {
                        text: "⚡ Begin Deconstruction"
                        onClicked: backend.beginDeconstruction()
                    }
                }
            }
        }

        GroupBox {
            title: "Development Build Tools"
            Layout.fillWidth: true
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
        // onDeployLogUpdated: append incremental log lines
        // Path: backend.deployLogUpdated(str) → buildLogArea.append(str)
        function onDeployLogUpdated(log) { buildLogArea.append(log) }
        // onDeployLogReset: full log reset after an undo/redo
        // Path: backend.deployLogReset(str) → buildLogArea.text = str
        function onDeployLogReset(text)  { buildLogArea.text = text }
        // onTerminalOutput: live process stdout/stderr
        // Path: QProcess.readyReadStdout/err → terminalReadyRead() → terminalOutput.emit(str)
        function onTerminalOutput(text)  { terminalArea.append(text) }
    }
}
