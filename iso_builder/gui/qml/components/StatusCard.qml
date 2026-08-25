import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root

    cornerRadius: 18

    property string symbol: "●"
    property url iconSource: ""
    property color accent: "#7458f5"
    property string caption: ""
    property string value: ""
    property string detail: ""
    property color captionColor: "#626578"
    property color valueColor: "#17204d"

    implicitHeight: 100

    RowLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        ClayBadge {
            symbol: root.symbol
            iconSource: root.iconSource
            accent: root.accent
            Layout.preferredWidth: 50
            Layout.preferredHeight: 50
            iconSize: 27
            symbolSize: 18
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Text {
                Layout.fillWidth: true
                text: root.caption
                color: root.captionColor
                font.pixelSize: 12
                elide: Text.ElideRight
            }
            Text {
                Layout.fillWidth: true
                text: root.value
                color: root.valueColor
                font.pixelSize: root.width < 210 ? 14 : 15
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            Text {
                Layout.fillWidth: true
                text: root.detail
                color: root.accent
                font.pixelSize: 12
                elide: Text.ElideRight
            }
        }
    }
}
