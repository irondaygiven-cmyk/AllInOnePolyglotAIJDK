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
            text: "GUI Theme Editor"
            font.pixelSize: 26
            color: "#00ff9d"
        }

        GroupBox {
            title: "Colors"
            Layout.fillWidth: true
            GridLayout {
                columns: 2
                columnSpacing: 16
                rowSpacing: 12

                RowLayout {
                    Label { text: "Accent" }
                    Rectangle { width: 32; height: 32; radius: 4; color: accentColor.text; border.color: "#888888" }
                    TextField { id: accentColor; text: "#00ff9d"; Layout.fillWidth: true; onEditingFinished: backend.updateThemeColor("accent", text) }
                }
                RowLayout {
                    Label { text: "Background" }
                    Rectangle { width: 32; height: 32; radius: 4; color: bgColor.text; border.color: "#888888" }
                    TextField { id: bgColor; text: "#0a0a0a"; Layout.fillWidth: true; onEditingFinished: backend.updateThemeColor("background", text) }
                }
                RowLayout {
                    Label { text: "Text" }
                    Rectangle { width: 32; height: 32; radius: 4; color: textColor.text; border.color: "#888888" }
                    TextField { id: textColor; text: "#e0e0e0"; Layout.fillWidth: true; onEditingFinished: backend.updateThemeColor("text", text) }
                }
                RowLayout {
                    Label { text: "Button" }
                    Rectangle { width: 32; height: 32; radius: 4; color: buttonColor.text; border.color: "#888888" }
                    TextField { id: buttonColor; text: "#00ff9d"; Layout.fillWidth: true; onEditingFinished: backend.updateThemeColor("button", text) }
                }
            }
        }

        GroupBox {
            title: "Fonts & Size"
            Layout.fillWidth: true
            GridLayout {
                columns: 2
                columnSpacing: 16
                rowSpacing: 12

                RowLayout {
                    Label { text: "UI Font" }
                    ComboBox {
                        model: ["Segoe UI", "Arial", "Helvetica", "Inter", "Roboto", "Tahoma"]
                        currentIndex: 0
                        onCurrentTextChanged: backend.updateUIFont(currentText)
                    }
                }
                RowLayout {
                    Label { text: "Code Font" }
                    ComboBox {
                        model: ["Consolas", "Courier New", "Lucida Console", "Monaco"]
                        currentIndex: 0
                        onCurrentTextChanged: backend.updateCodeFont(currentText)
                    }
                }
                RowLayout {
                    Label { text: "Font Size" }
                    Slider { id: fontSizeSlider; from: 10; to: 24; value: 15; onValueChanged: backend.updateFontSize(value) }
                    Label { text: Math.round(fontSizeSlider.value) + " px"; font.pixelSize: 14 }
                }
            }
        }

        RowLayout {
            ModernButton { text: "Save Theme Layout"; Layout.fillWidth: true; onClicked: backend.saveThemeLayout() }
            ModernButton { text: "Load Theme Layout"; Layout.fillWidth: true; onClicked: backend.loadThemeLayout() }
            ModernButton { text: "Reset to Default";  Layout.fillWidth: true; onClicked: backend.resetTheme() }
        }

        TextArea {
            id: themeLogArea
            Layout.fillHeight: true
            Layout.fillWidth: true
            readOnly: true
            font.family: "Consolas"
            background: Rectangle { color: "#1a1a1a"; radius: 12 }
        }
    }

    Connections {
        target: backend
        // onDeployLogUpdated: append incremental theme-operation log lines
        // Path: backend.deployLogUpdated(str) → themeLogArea.append(str)
        function onDeployLogUpdated(log) { themeLogArea.append(log) }
        // onDeployLogReset: full reset after an undo/redo
        // Path: backend.deployLogReset(str) → themeLogArea.text = str
        function onDeployLogReset(text) { themeLogArea.text = text }
    }
}
