import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root

    property string symbol: "●"
    property url iconSource: ""
    property color accent: "#7458f5"
    property string caption: ""
    property string value: ""
    property string detail: ""
    property color captionColor: "#73799a"
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
            Layout.preferredWidth: 42
            Layout.preferredHeight: 42
            symbolSize: 16
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Text {
                Layout.fillWidth: true
                text: root.caption
                color: root.captionColor
                font.pixelSize: 11
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
                font.pixelSize: 10
                elide: Text.ElideRight
            }
        }
    }
}
