import QtQuick
import QtQuick.Effects

Item {
    id: root

    property real rotationAngle: 0

    Rectangle {
        id: disc
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height)
        height: width
        radius: width / 2
        rotation: root.rotationAngle
        border.width: 2
        border.color: "#c5ceff"
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "#c6dbff" }
            GradientStop { position: 0.25; color: "#d6c4ff" }
            GradientStop { position: 0.5; color: "#fff2e4" }
            GradientStop { position: 0.75; color: "#d6f6ff" }
            GradientStop { position: 1.0; color: "#b9c8ff" }
        }
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: "#555d5df1"
            shadowBlur: 0.8
            shadowVerticalOffset: 10
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: parent.width * 0.22
            radius: width / 2
            color: "#70ffffff"
            border.width: 1
            border.color: "#b0ffffff"
        }

        Rectangle {
            anchors.centerIn: parent
            width: parent.width * 0.18
            height: width
            radius: width / 2
            color: "#f4f2ff"
            border.width: 2
            border.color: "#9e9bc2"
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: parent.width * 0.1
            height: parent.height * 0.28
            radius: height / 2
            color: "#48ffffff"
        }
    }

    SequentialAnimation on rotationAngle {
        loops: Animation.Infinite
        running: root.visible
        NumberAnimation { to: 360; duration: 26000; easing.type: Easing.Linear }
    }
}
