import QtQuick 2.15

Item {
    width: chatList.width
    height: bubble.height + 16

    Rectangle {
        id: bubble
        width: Math.min(messageText.implicitWidth + 52, chatList.width * 0.78)
        height: messageText.height + 36
        radius: 26
        color: model.isUser ? "#00ff9d" : "#2a2a2a"
        anchors.left: model.isUser ? undefined : parent.left
        anchors.right: model.isUser ? parent.right : undefined

        ScaleAnimator { target: bubble; from: 0.82; to: 1.0; duration: 160; running: true; easing.type: Easing.OutCubic }
        OpacityAnimator { target: bubble; from: 0; to: 1; duration: 180; running: true }

        Text {
            id: messageText
            text: model.text
            color: model.isUser ? "#111111" : "#e0e0e0"
            wrapMode: Text.Wrap
            width: parent.width - 52
            anchors.centerIn: parent
            font.pixelSize: 15.5
            lineHeight: 1.3
        }
    }
}
