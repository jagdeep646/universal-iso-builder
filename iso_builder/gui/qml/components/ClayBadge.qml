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
            shadowColor: Qt.alpha(root.accent, 0.20)
            shadowBlur: 0.65
            shadowVerticalOffset: 4
        }

        Rectangle {
            anchors.fill: parent
            anchors.margins: Math.max(7, parent.width * 0.16)
            radius: width / 2
            color: root.accent
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.lighter(root.accent, 1.25) }
                GradientStop { position: 1.0; color: Qt.darker(root.accent, 1.08) }
            }

            Rectangle {
                width: parent.width * 0.58
                height: parent.height * 0.24
                radius: height / 2
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: parent.height * 0.12
                color: "#5cffffff"
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
