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

        Text {
            anchors.centerIn: parent
            text: "\u2713"
            visible: control.checked
            color: "white"
            font.pixelSize: 18
            font.weight: Font.DemiBold
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
