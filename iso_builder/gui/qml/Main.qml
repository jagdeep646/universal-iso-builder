import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window
    width: 1180
    height: 760
    minimumWidth: 980
    minimumHeight: 640
    visible: true
    title: "Universal ISO Builder " + bridge.appVersion + " — Qt Preview"
    color: "#111a3d"

    readonly property color ink: "#17204f"
    readonly property color muted: "#697198"
    readonly property color violet: "#7957f5"
    readonly property color blue: "#4189f7"
    readonly property color panel: "#f7f7fd"

    Rectangle {
        anchors.fill: parent
        color: "#111a3d"

        RowLayout {
            anchors.fill: parent
            spacing: 0

            Rectangle {
                Layout.preferredWidth: 245
                Layout.fillHeight: true
                color: "#18234d"

                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#202b5a" }
                    GradientStop { position: 1.0; color: "#111a3d" }
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 18

                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 145

                        Rectangle {
                            width: 82
                            height: 82
                            radius: 41
                            anchors.horizontalCenter: parent.horizontalCenter
                            color: "#dce7ff"
                            border.color: "#afbcff"
                            border.width: 2

                            Rectangle {
                                width: 22
                                height: 22
                                radius: 11
                                anchors.centerIn: parent
                                color: "#26305d"
                                border.color: "#ffffff"
                            }
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: parent.bottom
                            text: "ISO BUILDER"
                            color: "white"
                            font.pixelSize: 18
                            font.weight: Font.DemiBold
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 54
                        radius: 16
                        color: "#7357e8"
                        border.color: "#9d8aff"

                        Row {
                            anchors.centerIn: parent
                            spacing: 12
                            Text { text: "●"; color: "white"; font.pixelSize: 17 }
                            Text {
                                text: "Dashboard"
                                color: "white"
                                font.pixelSize: 16
                                font.weight: Font.Medium
                            }
                        }
                    }

                    Repeater {
                        model: ["Create ISO", "Backend status", "Build log"]
                        delegate: Rectangle {
                            required property string modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 46
                            radius: 14
                            color: "transparent"

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: 18
                                text: modelData
                                color: "#cbd2ec"
                                font.pixelSize: 15
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 100
                        radius: 18
                        color: "#27335e"
                        border.color: "#4a5684"

                        Column {
                            anchors.centerIn: parent
                            spacing: 7

                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: bridge.statusTitle
                                color: "white"
                                font.pixelSize: 15
                                font.weight: Font.DemiBold
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: bridge.statusDetail
                                color: "#bbc4e1"
                                font.pixelSize: 12
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: window.panel
                radius: 24

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 38
                    spacing: 24

                    Column {
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            text: "Welcome back"
                            color: window.muted
                            font.pixelSize: 16
                        }
                        Text {
                            text: "Universal ISO Builder"
                            color: window.ink
                            font.pixelSize: 36
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: "Qt Quick migration preview — backend status is live; build controls remain in the verified Tkinter app."
                            color: window.muted
                            font.pixelSize: 15
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 18

                        Repeater {
                            model: [
                                {
                                    caption: "Preferred backend",
                                    value: bridge.preferredBackend,
                                    accent: "#62b96f"
                                },
                                {
                                    caption: "Detected tools",
                                    value: bridge.backendCount.toString(),
                                    accent: window.violet
                                },
                                {
                                    caption: "Application",
                                    value: "Version " + bridge.appVersion,
                                    accent: window.blue
                                }
                            ]

                            delegate: Rectangle {
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredHeight: 128
                                radius: 22
                                color: "#ffffff"
                                border.color: "#e3e5f2"

                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 20
                                    spacing: 12

                                    Rectangle {
                                        width: 34
                                        height: 7
                                        radius: 4
                                        color: modelData.accent
                                    }
                                    Text {
                                        text: modelData.caption
                                        color: window.muted
                                        font.pixelSize: 13
                                    }
                                    Text {
                                        text: modelData.value
                                        color: window.ink
                                        font.pixelSize: 19
                                        font.weight: Font.DemiBold
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 24
                        color: "#ffffff"
                        border.color: "#e3e5f2"

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 28
                            spacing: 18

                            RowLayout {
                                Layout.fillWidth: true

                                Column {
                                    Layout.fillWidth: true
                                    spacing: 7

                                    Text {
                                        text: "Qt migration gate"
                                        color: window.ink
                                        font.pixelSize: 22
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        text: "This preview validates Qt Quick rendering and the read-only Python bridge."
                                        color: window.muted
                                        font.pixelSize: 14
                                    }
                                }

                                Button {
                                    id: refreshButton
                                    text: "Refresh backends"
                                    onClicked: bridge.refreshBackends()

                                    contentItem: Text {
                                        text: refreshButton.text
                                        color: "white"
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        font.pixelSize: 14
                                        font.weight: Font.DemiBold
                                    }
                                    background: Rectangle {
                                        radius: 14
                                        gradient: Gradient {
                                            GradientStop { position: 0.0; color: window.violet }
                                            GradientStop { position: 1.0; color: window.blue }
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 1
                                color: "#ececf4"
                            }

                            Text {
                                Layout.fillWidth: true
                                text: bridge.backendCount > 0
                                      ? "Available: " + bridge.backendNames.join(", ")
                                      : "No ISO backend detected on this machine."
                                color: window.ink
                                font.pixelSize: 15
                                wrapMode: Text.WordWrap
                            }

                            Item { Layout.fillHeight: true }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 92
                                radius: 18
                                color: "#f1efff"
                                border.color: "#ddd7ff"

                                Text {
                                    anchors.fill: parent
                                    anchors.margins: 20
                                    text: "Q2 scope: launcher + backend status only. ISO creation, scanning, cancellation, hashing and transactional output remain unchanged and continue through the existing verified application."
                                    color: "#4d4679"
                                    font.pixelSize: 14
                                    wrapMode: Text.WordWrap
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "Source-only preview • Production entrypoint unchanged"
                        color: "#858bac"
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignRight
                    }
                }
            }
        }
    }
}
