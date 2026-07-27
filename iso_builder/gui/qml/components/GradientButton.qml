import QtQuick
import QtQuick.Controls
import QtQuick.Effects

Button {
    id: control

    property color startColor: "#8155f5"
    property color endColor: "#398cf6"
    property bool glowEnabled: true

    implicitHeight: 54
    hoverEnabled: true

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
        opacity: control.enabled ? 1.0 : 0.9
        scale: control.down ? 0.985 : (control.hovered ? 1.012 : 1.0)
        gradient: Gradient {
            GradientStop { position: 0.0; color: control.startColor }
            GradientStop { position: 1.0; color: control.endColor }
        }
        layer.enabled: control.glowEnabled
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: "#665d53f1"
            shadowBlur: control.hovered ? 0.75 : 0.48
            shadowVerticalOffset: control.hovered ? 8 : 5
        }

        Behavior on scale {
            NumberAnimation { duration: 130; easing.type: Easing.OutCubic }
        }
    }
}
