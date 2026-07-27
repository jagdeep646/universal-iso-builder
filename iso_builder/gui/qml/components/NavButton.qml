import QtQuick
import QtQuick.Controls
import QtQuick.Effects

Button {
    id: control

    property string symbol: "•"
    property url iconSource: ""
    property bool selected: false

    implicitHeight: 44
    hoverEnabled: true

    contentItem: Row {
        leftPadding: 16
        spacing: 12
        anchors.verticalCenter: parent.verticalCenter

        Item {
            width: 21
            height: 21

            Image {
                anchors.fill: parent
                visible: control.iconSource.toString().length > 0
                source: control.iconSource
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
                layer.enabled: true
                layer.effect: MultiEffect {
                    colorization: 1.0
                    colorizationColor: control.selected ? "#ffffff" : "#c8cee2"
                }
            }

            Text {
                anchors.fill: parent
                visible: control.iconSource.toString().length === 0
                text: control.symbol
                color: control.selected ? "white" : "#c9cfe4"
                font.pixelSize: 18
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: control.text
            color: control.selected ? "white" : "#d9deef"
            font.pixelSize: 14
            font.weight: control.selected ? Font.DemiBold : Font.Normal
        }
    }

    background: Rectangle {
        radius: 14
        color: control.selected
               ? "#7355ec"
               : (control.hovered ? "#24325f" : "transparent")
        border.width: control.selected ? 1 : 0
        border.color: "#9e8cff"
        layer.enabled: control.selected
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: "#775a52ee"
            shadowBlur: 0.7
            shadowVerticalOffset: 4
        }

        Behavior on color {
            ColorAnimation { duration: 150 }
        }
    }
}
