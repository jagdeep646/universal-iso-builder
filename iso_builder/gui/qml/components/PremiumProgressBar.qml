import QtQuick
import QtQuick.Effects

Item {
    id: root

    property real value: 0.0
    property color startColor: "#7d51f5"
    property color endColor: "#388ef7"
    property color trackColor: "#e8e8f1"

    implicitHeight: 14

    Rectangle {
        id: track
        anchors.fill: parent
        radius: height / 2
        color: root.trackColor
        border.width: 1
        border.color: "#36ffffff"

        Rectangle {
            id: fill
            width: root.value > 0
                   ? Math.max(parent.height, parent.width * Math.min(1, Math.max(0, root.value)))
                   : 0
            height: parent.height
            radius: height / 2
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: root.startColor }
                GradientStop { position: 0.72; color: root.endColor }
                GradientStop { position: 1.0; color: "#57bcff" }
            }
            layer.enabled: width > 0
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: "#704f75ee"
                shadowBlur: 0.7
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 2
                height: Math.max(1, parent.height * 0.28)
                radius: height / 2
                color: "#62ffffff"
            }

            Behavior on width {
                NumberAnimation { duration: 320; easing.type: Easing.OutCubic }
            }
        }
    }
}
