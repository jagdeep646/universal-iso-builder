import QtQuick
import QtQuick.Controls

CheckBox {
    id: control

    property bool darkSurface: false
    property color textColor: "#17204f"
    property color mutedColor: "#626578"
    property color accentColor: "#7a55f4"

    implicitHeight: 32
    spacing: 10
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus

    indicator: Rectangle {
        x: 0
        y: Math.round((control.height - height) / 2)
        width: 28
        height: 28
        radius: 7
        color: control.checked
               ? control.accentColor
               : (control.darkSurface ? "#292f46" : "#ffffff")
        opacity: control.enabled ? 1.0 : 0.62
        scale: control.down ? 0.94 : 1.0
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus
                      ? control.accentColor
                      : (control.hovered && control.enabled
                         ? Qt.alpha(control.accentColor, 0.65)
                         : (control.darkSurface ? "#4b536b" : "#cfd2df"))

        Canvas {
            property color strokeColor: "white"

            anchors.centerIn: parent
            width: 17
            height: 13
            visible: control.checked

            onPaint: {
                const context = getContext("2d")
                context.reset()
                context.strokeStyle = strokeColor
                context.lineWidth = 2.6
                context.lineCap = "round"
                context.lineJoin = "round"
                context.beginPath()
                context.moveTo(2, height * 0.52)
                context.lineTo(width * 0.40, height - 2)
                context.lineTo(width - 2, 2)
                context.stroke()
            }
        }

        Behavior on scale {
            NumberAnimation { duration: 100; easing.type: Easing.OutCubic }
        }
    }

    contentItem: Text {
        leftPadding: control.indicator.width + control.spacing
        text: control.text
        color: control.enabled ? control.textColor : control.mutedColor
        opacity: control.enabled ? 1.0 : 0.68
        font.pixelSize: 13
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
