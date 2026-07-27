import QtQuick
import QtQuick.Effects

Item {
    id: root

    property color fillColor: "#e8ffffff"
    property color edgeColor: "#80ffffff"
    property color shadowColor: "#340f1846"
    property real cornerRadius: 22
    property real shadowBlur: 0.45
    property bool darkSurface: false
    property real highlightOpacity: darkSurface ? 0.08 : 0.22
    default property alias content: contentLayer.data

    Rectangle {
        id: surface
        anchors.fill: parent
        radius: root.cornerRadius
        color: root.fillColor
        border.width: 1
        border.color: root.edgeColor
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: root.shadowColor
            shadowBlur: root.shadowBlur
            shadowVerticalOffset: 7
            shadowHorizontalOffset: 0
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 2
            height: Math.max(20, parent.height * 0.34)
            radius: Math.max(10, root.cornerRadius - 2)
            opacity: root.highlightOpacity
            gradient: Gradient {
                GradientStop { position: 0.0; color: "#b8ffffff" }
                GradientStop { position: 1.0; color: "#00ffffff" }
            }
        }
    }

    Item {
        id: contentLayer
        anchors.fill: parent
    }
}
