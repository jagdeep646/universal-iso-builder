import QtQuick
import QtQuick.Effects

Item {
    id: root

    property string symbol: "●"
    property url iconSource: ""
    property color accent: "#7158f5"
    property color symbolColor: "white"
    property int symbolSize: 20
    property int iconSize: 26

    implicitWidth: 52
    implicitHeight: 52

    Rectangle {
        id: halo
        anchors.centerIn: parent
        width: parent.width
        height: parent.height
        radius: width / 2
        color: Qt.lighter(root.accent, 1.75)
        border.width: 1
        border.color: "#d9ffffff"
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: Qt.alpha(root.accent, 0.38)
            shadowBlur: 0.65
            shadowVerticalOffset: 5
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: 8
            radius: width / 2
            color: root.accent
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.lighter(root.accent, 1.25) }
                GradientStop { position: 1.0; color: Qt.darker(root.accent, 1.08) }
            }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: root.iconSource.toString().length === 0
        text: root.symbol
        color: root.symbolColor
        font.pixelSize: root.symbolSize
        font.weight: Font.DemiBold
    }

    Image {
        anchors.centerIn: parent
        width: root.iconSize
        height: root.iconSize
        visible: root.iconSource.toString().length > 0
        source: root.iconSource
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
    }
}
