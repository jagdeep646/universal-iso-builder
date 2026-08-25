import QtQuick
import QtQuick.Controls
import QtQuick.Effects

Button {
    id: control

    property color startColor: "#865fe7"
    property color endColor: "#5575e4"
    property bool glowEnabled: true

    implicitHeight: 54
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus

    contentItem: Text {
        text: control.text
        color: control.enabled ? "white" : "#f7f6ff"
        font.pixelSize: 15
        font.weight: Font.DemiBold
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }

    background: Rectangle {
        id: buttonSurface
        radius: height / 2
        opacity: control.enabled ? 1.0 : 0.86
        scale: control.enabled
               ? (control.down ? 0.985 : (control.hovered ? 1.012 : 1.0))
               : 1.0
        border.width: control.activeFocus ? 2 : 0
        border.color: "#f2ffffff"
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop {
                position: 0.0
                color: control.down
                       ? Qt.darker(control.startColor, 1.10)
                       : (control.hovered && control.enabled
                          ? Qt.lighter(control.startColor, 1.06)
                          : control.startColor)
            }
            GradientStop {
                position: 1.0
                color: control.down
                       ? Qt.darker(control.endColor, 1.10)
                       : (control.hovered && control.enabled
                          ? Qt.lighter(control.endColor, 1.06)
                          : control.endColor)
            }
        }
        layer.enabled: control.glowEnabled && control.enabled
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: "#66202048"
            shadowBlur: control.hovered ? 0.75 : 0.48
            shadowVerticalOffset: control.hovered ? 8 : 5
        }

        Behavior on scale {
            NumberAnimation { duration: 130; easing.type: Easing.OutCubic }
        }
    }
}
