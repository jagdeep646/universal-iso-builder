import QtQuick
import QtQuick.Controls
import QtQuick.Effects

Button {
    id: control

    property color baseColor: "#6553d9"
    property real cornerRadius: 12
    property int labelSize: 12

    implicitHeight: 42
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus

    contentItem: Text {
        text: control.text
        color: control.enabled ? "white" : "#e5e4f0"
        font.pixelSize: control.labelSize
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        radius: control.cornerRadius
        color: control.down
               ? Qt.darker(control.baseColor, 1.10)
               : (control.hovered && control.enabled
                  ? Qt.lighter(control.baseColor, 1.10)
                  : control.baseColor)
        opacity: !control.enabled ? 0.72 : (control.down ? 0.82 : 0.94)
        scale: control.enabled
               ? (control.down ? 0.98 : (control.hovered ? 1.02 : 1.0))
               : 1.0
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? "#f2ffffff" : "#35ffffff"
        layer.enabled: control.enabled
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: "#55202048"
            shadowBlur: control.hovered ? 0.65 : 0.42
            shadowVerticalOffset: control.hovered ? 6 : 4
        }

        Behavior on scale {
            NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
        }
    }
}
