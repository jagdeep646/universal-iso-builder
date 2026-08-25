import QtQuick
import QtQuick.Controls

ComboBox {
    id: control

    property bool darkSurface: false
    property color textColor: "#17204f"
    property color mutedColor: "#626578"
    property color accentColor: "#7a55f4"

    implicitHeight: 42
    leftPadding: 14
    rightPadding: 38
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus

    contentItem: Text {
        text: control.displayText
        color: control.enabled ? control.textColor : control.mutedColor
        font.pixelSize: 12
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    indicator: Canvas {
        property color strokeColor: control.enabled
                                    ? control.textColor
                                    : control.mutedColor

        x: control.width - width - 15
        y: Math.round((control.height - height) / 2)
        width: 14
        height: 9

        onStrokeColorChanged: requestPaint()
        onPaint: {
            const context = getContext("2d")
            context.reset()
            context.strokeStyle = strokeColor
            context.lineWidth = 2
            context.lineCap = "round"
            context.lineJoin = "round"
            context.beginPath()
            context.moveTo(2, 2)
            context.lineTo(width / 2, height - 2)
            context.lineTo(width - 2, 2)
            context.stroke()
        }
    }

    background: Rectangle {
        radius: 12
        color: control.down && control.enabled
               ? (control.darkSurface ? "#343b55" : "#f4f1ff")
               : (control.darkSurface ? "#292f46" : "#ffffff")
        opacity: control.enabled ? 1.0 : 0.68
        scale: control.down && control.enabled ? 0.99 : 1.0
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus
                      ? control.accentColor
                      : (control.hovered && control.enabled
                         ? Qt.alpha(control.accentColor, 0.55)
                         : (control.darkSurface ? "#4b536b" : "#dcdeea"))

        Behavior on scale {
            NumberAnimation { duration: 100; easing.type: Easing.OutCubic }
        }
    }

    delegate: ItemDelegate {
        required property int index
        required property var modelData

        width: control.width - 8
        height: 38
        text: modelData
        highlighted: control.highlightedIndex === index
        contentItem: Text {
            text: parent.text
            color: control.textColor
            font.pixelSize: 12
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            radius: 9
            color: parent.highlighted
                   ? Qt.alpha(control.accentColor, control.darkSurface ? 0.35 : 0.16)
                   : "transparent"
        }
    }

    popup: Popup {
        y: control.height + 4
        width: control.width
        padding: 4
        implicitHeight: contentItem.implicitHeight + topPadding + bottomPadding

        contentItem: ListView {
            clip: true
            implicitHeight: Math.min(contentHeight, 240)
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator { }
        }

        background: Rectangle {
            radius: 12
            color: control.darkSurface ? "#252b43" : "#fbfbff"
            border.width: 1
            border.color: control.darkSurface ? "#4b536b" : "#dcdeea"
        }
    }
}
