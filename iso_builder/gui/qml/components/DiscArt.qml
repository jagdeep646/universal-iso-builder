import QtQuick
import QtQuick.Effects

Item {
    id: root

    property real rotationAngle: 0
    property url artSource: Qt.resolvedUrl("../assets/icons/disc.svg")

    Rectangle {
        id: discShadow
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height)
        height: width
        radius: width / 2
        color: "#1affffff"
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: "#4d6557d9"
            shadowBlur: 0.8
            shadowVerticalOffset: Math.max(4, root.width * 0.10)
        }
    }

    Image {
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height)
        height: width
        source: root.artSource
        rotation: root.rotationAngle
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
    }

    SequentialAnimation on rotationAngle {
        loops: Animation.Infinite
        running: root.visible
        NumberAnimation { to: 360; duration: 26000; easing.type: Easing.Linear }
    }
}
