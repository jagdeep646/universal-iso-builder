import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import QtQuick.Effects
import "components"

ApplicationWindow {
    id: window

    width: 1320
    height: 880
    minimumWidth: 1080
    minimumHeight: 720
    visible: true
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "transparent"
    title: "Universal ISO Builder " + bridge.appVersion + " — Qt Preview"

    property bool followSystemTheme: true
    property bool manualDarkMode: false
    readonly property bool darkMode: followSystemTheme
                                     ? bridge.systemDarkMode
                                     : manualDarkMode
    readonly property color workspaceColor: darkMode ? "#171b31" : "#f4f3fa"
    readonly property color cardColor: darkMode ? "#e8232941" : "#e8ffffff"
    readonly property color cardEdge: darkMode ? "#3e495f78" : "#9affffff"
    readonly property color ink: darkMode ? "#f4f3ff" : "#17204f"
    readonly property color muted: darkMode ? "#aeb5d1" : "#6e7599"
    readonly property color purple: "#7a55f4"
    readonly property color blue: "#398df7"
    readonly property color cyan: "#32c6ea"
    readonly property color green: "#43b65d"
    readonly property color orange: "#f18a35"

    function toggleMaximized() {
        if (window.visibility === Window.Maximized) {
            window.showNormal()
        } else {
            window.showMaximized()
        }
    }

    FolderDialog {
        id: sourceFolderDialog
        title: "Select source setup folder"
        onAccepted: bridge.selectSourceFolder(selectedFolder)
    }

    FolderDialog {
        id: outputFolderDialog
        title: "Select ISO output folder"
        onAccepted: bridge.selectOutputFolder(selectedFolder)
    }

    Connections {
        target: bridge

        function onCommandChanged() {
            if (!bridge.isPlanning
                    && (bridge.commandText.length > 0
                        || bridge.planningError.length > 0)) {
                commandDialog.open()
            }
        }

        function onExecutionChanged() {
            if (!bridge.isDryRunning
                    && bridge.buildOutcome !== "IDLE"
                    && bridge.buildOutcome !== "RUNNING") {
                dryRunDialog.open()
            }
        }
    }

    Dialog {
        id: buildSettingsDialog
        width: Math.min(690, window.width - 80)
        height: Math.min(650, window.height - 70)
        x: Math.round((window.width - width) / 2)
        y: Math.round((window.height - height) / 2)
        modal: true
        focus: true
        padding: 0
        closePolicy: Popup.CloseOnEscape

        background: Rectangle {
            radius: 24
            color: window.darkMode ? "#20263c" : "#f8f8fd"
            border.width: 1
            border.color: window.darkMode ? "#505a74" : "#ffffff"
        }

        contentItem: ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 13

            RowLayout {
                Layout.fillWidth: true

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text {
                        text: "Build Settings"
                        color: window.ink
                        font.pixelSize: 22
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: "Configure the verified ISO planning snapshot."
                        color: window.muted
                        font.pixelSize: 12
                    }
                }

                Button {
                    text: "×"
                    width: 36
                    height: 36
                    onClicked: buildSettingsDialog.close()
                    contentItem: Text {
                        text: parent.text
                        color: window.ink
                        font.pixelSize: 20
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 10
                        color: parent.hovered
                               ? (window.darkMode ? "#343c55" : "#ebeaf2")
                               : "transparent"
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: window.darkMode ? "#3b4258" : "#e2e2eb"
            }

            Text {
                text: "Output Folder"
                color: window.muted
                font.pixelSize: 12
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 42
                    radius: 12
                    color: window.darkMode ? "#292f46" : "#ffffff"
                    border.width: 1
                    border.color: window.darkMode ? "#4b536b" : "#dcdeea"
                    Text {
                        anchors.fill: parent
                        anchors.leftMargin: 13
                        anchors.rightMargin: 13
                        text: bridge.outputFolder.length > 0
                              ? bridge.outputFolder
                              : "Choose output folder"
                        color: window.muted
                        font.pixelSize: 12
                        elide: Text.ElideMiddle
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Button {
                    id: outputBrowseButton
                    Layout.preferredWidth: 92
                    Layout.preferredHeight: 42
                    text: "Browse"
                    enabled: !bridge.isDryRunning
                    onClicked: outputFolderDialog.open()
                    contentItem: Text {
                        text: outputBrowseButton.text
                        color: "white"
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        radius: 12
                        color: outputBrowseButton.hovered ? "#765ff0" : "#6553d9"
                    }
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 12
                rowSpacing: 8

                Text {
                    text: "ISO File Name"
                    color: window.muted
                    font.pixelSize: 12
                }
                Text {
                    text: "Volume Label"
                    color: window.muted
                    font.pixelSize: 12
                }

                TextField {
                    id: isoNameField
                    Layout.fillWidth: true
                    Layout.preferredHeight: 42
                    text: bridge.isoName
                    enabled: !bridge.autoPackage && !bridge.isDryRunning
                    selectByMouse: true
                    onEditingFinished: bridge.setIsoName(text)
                    color: window.ink
                    placeholderTextColor: window.muted
                    background: Rectangle {
                        radius: 12
                        color: window.darkMode ? "#292f46" : "#ffffff"
                        border.width: 1
                        border.color: window.darkMode ? "#4b536b" : "#dcdeea"
                        opacity: isoNameField.enabled ? 1.0 : 0.65
                    }
                }

                TextField {
                    id: volumeLabelField
                    Layout.fillWidth: true
                    Layout.preferredHeight: 42
                    text: bridge.volumeLabel
                    enabled: !bridge.autoPackage && !bridge.isDryRunning
                    selectByMouse: true
                    onEditingFinished: bridge.setVolumeLabel(text)
                    color: window.ink
                    background: Rectangle {
                        radius: 12
                        color: window.darkMode ? "#292f46" : "#ffffff"
                        border.width: 1
                        border.color: window.darkMode ? "#4b536b" : "#dcdeea"
                        opacity: volumeLabelField.enabled ? 1.0 : 0.65
                    }
                }

                Text {
                    text: "Build Profile"
                    color: window.muted
                    font.pixelSize: 12
                }
                Text {
                    text: "Backend"
                    color: window.muted
                    font.pixelSize: 12
                }

                ComboBox {
                    id: profileCombo
                    Layout.fillWidth: true
                    Layout.preferredHeight: 42
                    model: bridge.profileOptions
                    enabled: !bridge.isDryRunning
                    currentIndex: Math.max(0, bridge.profileOptions.indexOf(
                                               bridge.selectedProfile))
                    onActivated: bridge.setProfile(currentText)
                }

                ComboBox {
                    id: backendCombo
                    Layout.fillWidth: true
                    Layout.preferredHeight: 42
                    model: bridge.backendOptions
                    enabled: !bridge.isDryRunning
                    currentIndex: Math.max(0, bridge.backendOptions.indexOf(
                                               bridge.selectedBackend))
                    onActivated: bridge.setBackend(currentText)
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 22
                rowSpacing: 5

                CheckBox {
                    text: "Auto package folder"
                    checked: bridge.autoPackage
                    enabled: !bridge.isDryRunning
                    onToggled: bridge.setAutoPackage(checked)
                }
                CheckBox {
                    text: "Include hidden files"
                    checked: bridge.includeHidden
                    enabled: !bridge.isDryRunning
                    onToggled: bridge.setIncludeHidden(checked)
                }
                CheckBox {
                    text: "Generate SHA256"
                    checked: bridge.generateHash
                    enabled: !bridge.isDryRunning
                    onToggled: bridge.setGenerateHash(checked)
                }
                CheckBox {
                    text: "Optimize duplicates"
                    checked: bridge.optimizeDuplicates
                    enabled: !bridge.isDryRunning
                    onToggled: bridge.setOptimizeDuplicates(checked)
                }
            }

            Text {
                Layout.fillWidth: true
                visible: bridge.planningError.length > 0
                text: bridge.planningError
                color: "#ef5965"
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }

            Item { Layout.fillHeight: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Button {
                    Layout.preferredWidth: 110
                    Layout.preferredHeight: 46
                    text: "Close"
                    onClicked: buildSettingsDialog.close()
                }

                GradientButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 46
                    text: bridge.isPlanning ? "Preparing command..." : "Show Command"
                    enabled: bridge.canShowCommand
                    onClicked: bridge.showCommand()
                }

                GradientButton {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 46
                    text: bridge.isDryRunning ? "Running..." : "Run Dry Test"
                    enabled: bridge.canRunDryRun
                    onClicked: {
                        buildSettingsDialog.close()
                        bridge.runDryRun()
                    }
                }
            }
        }
    }

    Dialog {
        id: commandDialog
        width: Math.min(760, window.width - 70)
        height: Math.min(540, window.height - 70)
        x: Math.round((window.width - width) / 2)
        y: Math.round((window.height - height) / 2)
        modal: true
        focus: true
        padding: 0
        closePolicy: Popup.CloseOnEscape

        background: Rectangle {
            radius: 24
            color: window.darkMode ? "#20263c" : "#f8f8fd"
            border.width: 1
            border.color: window.darkMode ? "#505a74" : "#ffffff"
        }

        contentItem: ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 12

            Text {
                text: bridge.planningError.length > 0
                      ? "Command Preparation Failed"
                      : "Prepared Command"
                color: window.ink
                font.pixelSize: 22
                font.weight: Font.DemiBold
            }

            Text {
                Layout.fillWidth: true
                visible: bridge.plannedOutput.length > 0
                text: "Output: " + bridge.plannedOutput
                color: window.muted
                font.pixelSize: 12
                elide: Text.ElideMiddle
            }

            TextArea {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: bridge.commandText.length > 0
                text: bridge.commandText
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.WrapAnywhere
                color: window.ink
                background: Rectangle {
                    radius: 14
                    color: window.darkMode ? "#161b2e" : "#ffffff"
                    border.width: 1
                    border.color: window.darkMode ? "#454e68" : "#dcdeea"
                }
            }

            Text {
                Layout.fillWidth: true
                visible: bridge.commandWarningsText.length > 0
                text: "Warnings:\n" + bridge.commandWarningsText
                color: window.orange
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }

            Text {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: bridge.planningError.length > 0
                text: bridge.planningError
                color: "#ef5965"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }

            GradientButton {
                Layout.fillWidth: true
                Layout.preferredHeight: 46
                text: "Close"
                onClicked: commandDialog.close()
            }
        }
    }

    Dialog {
        id: dryRunDialog
        width: Math.min(780, window.width - 70)
        height: Math.min(570, window.height - 70)
        x: Math.round((window.width - width) / 2)
        y: Math.round((window.height - height) / 2)
        modal: true
        focus: true
        padding: 0
        closePolicy: Popup.CloseOnEscape

        background: Rectangle {
            radius: 24
            color: window.darkMode ? "#20263c" : "#f8f8fd"
            border.width: 1
            border.color: window.darkMode ? "#505a74" : "#ffffff"
        }

        contentItem: ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                ClayBadge {
                    Layout.preferredWidth: 46
                    Layout.preferredHeight: 46
                    iconSource: bridge.buildOutcome === "DRY RUN"
                                ? Qt.resolvedUrl("assets/icons/check.svg")
                                : ""
                    symbol: bridge.buildOutcome === "DRY RUN" ? "" : "!"
                    symbolSize: 18
                    accent: bridge.buildOutcome === "DRY RUN"
                            ? window.green
                            : window.orange
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3
                    Text {
                        text: bridge.buildOutcome === "DRY RUN"
                              ? "Dry Run Complete"
                              : "Dry Run Failed"
                        color: window.ink
                        font.pixelSize: 22
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: bridge.buildOutcome === "DRY RUN"
                              ? "Planning and validation completed without creating an ISO."
                              : bridge.buildError
                        color: bridge.buildOutcome === "DRY RUN"
                               ? window.muted
                               : "#ef5965"
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                visible: bridge.lastExecutionOutput.length > 0
                text: "Planned output: " + bridge.lastExecutionOutput
                color: window.muted
                font.pixelSize: 12
                elide: Text.ElideMiddle
            }

            TextArea {
                Layout.fillWidth: true
                Layout.fillHeight: true
                text: bridge.buildLogText.length > 0
                      ? bridge.buildLogText
                      : bridge.buildError
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.WrapAnywhere
                color: window.ink
                background: Rectangle {
                    radius: 14
                    color: window.darkMode ? "#161b2e" : "#ffffff"
                    border.width: 1
                    border.color: window.darkMode ? "#454e68" : "#dcdeea"
                }
            }

            GradientButton {
                Layout.fillWidth: true
                Layout.preferredHeight: 46
                text: "Close"
                onClicked: dryRunDialog.close()
            }
        }
    }

    Rectangle {
        id: shell
        anchors.fill: parent
        anchors.margins: window.visibility === Window.Maximized ? 0 : 12
        radius: window.visibility === Window.Maximized ? 0 : 28
        color: window.workspaceColor
        clip: true
        border.width: 1
        border.color: window.darkMode ? "#46506f" : "#d9ffffff"
        layer.enabled: window.visibility !== Window.Maximized
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: "#8a050c2b"
            shadowBlur: 1.0
            shadowVerticalOffset: 12
        }

        RowLayout {
            anchors.fill: parent
            spacing: 0

            Rectangle {
                id: sidebar
                Layout.preferredWidth: 232
                Layout.fillHeight: true
                color: "#1a244d"

                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#29345f" }
                    GradientStop { position: 0.52; color: "#1b2854" }
                    GradientStop { position: 1.0; color: "#121d43" }
                }

                Rectangle {
                    anchors.fill: parent
                    color: "#18000000"
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "#15ffffff" }
                        GradientStop { position: 1.0; color: "#00132343" }
                    }
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 4

                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 145

                        DiscArt {
                            width: 86
                            height: 86
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: parent.top
                            anchors.topMargin: 3
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: parent.bottom
                            anchors.bottomMargin: 15
                            text: "ISO BUILDER"
                            color: "white"
                            font.pixelSize: 18
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.5
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.bottom: parent.bottom
                            text: "v" + bridge.appVersion
                            color: "#aeb6d8"
                            font.pixelSize: 11
                        }
                    }

                    NavButton {
                        Layout.fillWidth: true
                        text: "Home"
                        iconSource: Qt.resolvedUrl("assets/icons/home.svg")
                        selected: true
                    }

                    NavButton {
                        Layout.fillWidth: true
                        text: "Create ISO"
                        iconSource: Qt.resolvedUrl("assets/icons/create.svg")
                        enabled: false
                        opacity: 0.78
                    }

                    NavButton {
                        Layout.fillWidth: true
                        text: "Verify ISO"
                        iconSource: Qt.resolvedUrl("assets/icons/verify.svg")
                        enabled: false
                        opacity: 0.78
                    }

                    NavButton {
                        Layout.fillWidth: true
                        text: "History"
                        iconSource: Qt.resolvedUrl("assets/icons/history.svg")
                        enabled: false
                        opacity: 0.78
                    }

                    NavButton {
                        Layout.fillWidth: true
                        text: "Settings"
                        iconSource: Qt.resolvedUrl("assets/icons/settings.svg")
                        enabled: !bridge.isDryRunning
                        onClicked: buildSettingsDialog.open()
                    }

                    NavButton {
                        Layout.fillWidth: true
                        text: "Tools"
                        iconSource: Qt.resolvedUrl("assets/icons/tools.svg")
                        enabled: false
                        opacity: 0.78
                    }

                    NavButton {
                        Layout.fillWidth: true
                        text: "Help"
                        iconSource: Qt.resolvedUrl("assets/icons/help.svg")
                        enabled: false
                        opacity: 0.78
                    }

                    Item { Layout.fillHeight: true }

                    GlassCard {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 90
                        fillColor: "#28365f"
                        edgeColor: "#55658f"
                        shadowColor: "#4507122d"
                        cornerRadius: 19

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 10

                            ClayBadge {
                                Layout.preferredWidth: 42
                                Layout.preferredHeight: 42
                                iconSource: bridge.backendCount > 0
                                            ? Qt.resolvedUrl("assets/icons/check.svg")
                                            : ""
                                symbol: bridge.backendCount > 0 ? "✓" : "!"
                                symbolSize: 17
                                accent: bridge.backendCount > 0
                                        ? window.green
                                        : window.orange
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 5

                                Text {
                                    Layout.fillWidth: true
                                    text: bridge.statusTitle
                                    color: "white"
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: bridge.statusDetail
                                    color: "#c5cce3"
                                    font.pixelSize: 10
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 2
                                }
                            }
                        }
                    }

                    GlassCard {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 46
                        fillColor: "#25315a"
                        edgeColor: "#40507d"
                        shadowColor: "#3006112c"
                        cornerRadius: 16

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            spacing: 6

                            Repeater {
                                model: [
                                    { text: "☀", dark: false },
                                    { text: "☾", dark: true }
                                ]

                                delegate: Button {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 34
                                    text: modelData.text
                                    onClicked: {
                                        window.followSystemTheme = false
                                        window.manualDarkMode = modelData.dark
                                    }
                                    contentItem: Text {
                                        text: parent.text
                                        color: "white"
                                        font.pixelSize: 17
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    background: Rectangle {
                                        radius: 11
                                        color: !window.followSystemTheme
                                               && window.manualDarkMode === modelData.dark
                                               ? "#7256e8"
                                               : "#00ffffff"
                                    }
                                }
                            }

                            Button {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 34
                                text: "A"
                                onClicked: window.followSystemTheme = true
                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                background: Rectangle {
                                    radius: 11
                                    color: window.followSystemTheme
                                           ? "#7256e8"
                                           : "#00ffffff"
                                }
                            }
                        }
                    }
                }
            }

            Item {
                id: workspace
                Layout.fillWidth: true
                Layout.fillHeight: true

                Rectangle {
                    anchors.fill: parent
                    color: window.workspaceColor
                }

                Rectangle {
                    width: parent.width * 0.68
                    height: parent.height * 0.52
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.rightMargin: -width * 0.12
                    anchors.topMargin: -height * 0.25
                    radius: width / 2
                    color: window.darkMode ? "#162d3965" : "#42e6d9ff"
                }

                Item {
                    id: titleDragArea
                    anchors.left: parent.left
                    anchors.right: windowControls.left
                    anchors.top: parent.top
                    height: 150
                    z: 10

                    DragHandler {
                        target: null
                        acceptedButtons: Qt.LeftButton
                        grabPermissions: PointerHandler.CanTakeOverFromAnything
                        onActiveChanged: {
                            if (active) {
                                window.startSystemMove()
                            }
                        }
                    }

                    TapHandler {
                        acceptedButtons: Qt.LeftButton
                        onDoubleTapped: window.toggleMaximized()
                    }
                }

                Row {
                    id: windowControls
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.rightMargin: 14
                    anchors.topMargin: 9
                    spacing: 5
                    z: 20

                    Repeater {
                        model: [
                            { text: "—", action: "minimize" },
                            { text: "□", action: "maximize" },
                            { text: "×", action: "close" }
                        ]

                        delegate: Button {
                            required property var modelData
                            width: 38
                            height: 30
                            hoverEnabled: true
                            text: modelData.text
                            onClicked: {
                                if (modelData.action === "minimize") {
                                    window.showMinimized()
                                } else if (modelData.action === "maximize") {
                                    window.toggleMaximized()
                                } else {
                                    window.close()
                                }
                            }
                            contentItem: Text {
                                text: parent.text
                                color: window.ink
                                font.pixelSize: 17
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle {
                                radius: 9
                                color: parent.hovered
                                       ? (modelData.action === "close"
                                          ? "#ef5260"
                                          : (window.darkMode ? "#34405f" : "#e9e7f3"))
                                       : "transparent"
                            }
                        }
                    }
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 30
                    anchors.rightMargin: 30
                    anchors.topMargin: 40
                    anchors.bottomMargin: 18
                    spacing: 12

                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 100

                        Column {
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width * 0.68
                            spacing: 8

                            Text {
                                text: "Welcome back!"
                                color: window.muted
                                font.pixelSize: 15
                            }
                            Text {
                                text: "Universal ISO Builder"
                                color: window.ink
                                font.pixelSize: 32
                                font.weight: Font.DemiBold
                            }
                            Text {
                                text: "Create reliable ISO packages with verified Windows backends."
                                color: window.muted
                                font.pixelSize: 14
                            }
                        }

                        DiscArt {
                            width: 100
                            height: 100
                            anchors.right: parent.right
                            anchors.rightMargin: 45
                            anchors.verticalCenter: parent.verticalCenter
                            opacity: 0.9
                        }
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 100
                        Layout.minimumHeight: 100
                        columns: 4
                        columnSpacing: 14

                        StatusCard {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            fillColor: window.cardColor
                            edgeColor: window.cardEdge
                            darkSurface: window.darkMode
                            captionColor: window.muted
                            valueColor: window.ink
                            caption: "Source folder"
                            value: bridge.sourceName
                            detail: bridge.sourceDetail
                            iconSource: Qt.resolvedUrl("assets/icons/folder.svg")
                            accent: window.blue
                        }

                        StatusCard {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            fillColor: window.cardColor
                            edgeColor: window.cardEdge
                            darkSurface: window.darkMode
                            captionColor: window.muted
                            valueColor: window.ink
                            caption: "Backend"
                            value: bridge.preferredBackend
                            detail: bridge.backendCount > 0
                                    ? "Available & ready"
                                    : "Backend required"
                            iconSource: bridge.backendCount > 0
                                        ? Qt.resolvedUrl("assets/icons/check.svg")
                                        : ""
                            symbol: bridge.backendCount > 0 ? "✓" : "!"
                            accent: bridge.backendCount > 0
                                    ? window.green
                                    : window.orange
                        }

                        StatusCard {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            fillColor: window.cardColor
                            edgeColor: window.cardEdge
                            darkSurface: window.darkMode
                            captionColor: window.muted
                            valueColor: window.ink
                            caption: "Compatibility"
                            value: "Auto profile"
                            detail: "Planning preview"
                            iconSource: Qt.resolvedUrl("assets/icons/globe.svg")
                            accent: window.purple
                        }

                        StatusCard {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            fillColor: window.cardColor
                            edgeColor: window.cardEdge
                            darkSurface: window.darkMode
                            captionColor: window.muted
                            valueColor: window.ink
                            caption: "Integrity"
                            value: "SHA-256"
                            detail: "Available"
                            iconSource: Qt.resolvedUrl("assets/icons/shield.svg")
                            accent: window.orange
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 270
                        spacing: 12

                        GlassCard {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.preferredWidth: 2.05
                            fillColor: window.cardColor
                            edgeColor: window.cardEdge
                            darkSurface: window.darkMode

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 18
                                spacing: 8

                                Text {
                                    text: "Create New ISO"
                                    color: window.ink
                                    font.pixelSize: 17
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    text: "Source Folder"
                                    color: window.muted
                                    font.pixelSize: 12
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 44
                                    radius: 13
                                    color: window.darkMode ? "#252b43" : "#f9f9fd"
                                    border.width: 1
                                    border.color: window.darkMode ? "#46506a" : "#dcdeea"

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 16
                                        anchors.rightMargin: 8
                                        spacing: 10

                                        Text {
                                            text: "▣"
                                            color: window.muted
                                            font.pixelSize: 18
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: bridge.sourceFolder.length > 0
                                                  ? bridge.sourceFolder
                                                  : "Choose or drop a source folder"
                                            color: window.muted
                                            font.pixelSize: 13
                                            elide: Text.ElideMiddle
                                        }

                                        Button {
                                            id: sourceBrowseButton
                                            Layout.preferredWidth: 82
                                            Layout.preferredHeight: 32
                                            text: "Browse"
                                            enabled: !bridge.isDryRunning
                                            onClicked: sourceFolderDialog.open()
                                            contentItem: Text {
                                                text: sourceBrowseButton.text
                                                color: "white"
                                                font.pixelSize: 12
                                                font.weight: Font.DemiBold
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                            background: Rectangle {
                                                radius: 10
                                                color: sourceBrowseButton.hovered
                                                       ? "#765ff0"
                                                       : "#6553d9"
                                                opacity: sourceBrowseButton.down ? 0.78 : 0.92
                                            }
                                        }
                                    }

                                    DropArea {
                                        anchors.fill: parent
                                        enabled: !bridge.isDryRunning
                                        onDropped: function(drop) {
                                            if (drop.hasUrls && drop.urls.length > 0) {
                                                bridge.selectSourceFolder(drop.urls[0])
                                                drop.acceptProposedAction()
                                            }
                                        }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 6
                                        Text {
                                            text: "Volume Label"
                                            color: window.muted
                                            font.pixelSize: 12
                                        }
                                        Rectangle {
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 40
                                            radius: 13
                                            color: window.darkMode ? "#252b43" : "#f9f9fd"
                                            border.width: 1
                                            border.color: window.darkMode ? "#46506a" : "#dcdeea"
                                            Text {
                                                anchors.left: parent.left
                                                anchors.leftMargin: 14
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: bridge.volumeLabel
                                                color: window.muted
                                                font.pixelSize: 12
                                            }
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 6
                                        Text {
                                            text: "Build Profile"
                                            color: window.muted
                                            font.pixelSize: 12
                                        }
                                        Rectangle {
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 40
                                            radius: 13
                                            color: window.darkMode ? "#252b43" : "#f9f9fd"
                                            border.width: 1
                                            border.color: window.darkMode ? "#46506a" : "#dcdeea"
                                            Text {
                                                anchors.left: parent.left
                                                anchors.leftMargin: 14
                                                anchors.verticalCenter: parent.verticalCenter
                                                text: bridge.selectedProfile
                                                color: window.muted
                                                font.pixelSize: 12
                                            }
                                        }
                                    }
                                }

                                Item { Layout.fillHeight: true }

                                GradientButton {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 44
                                    text: bridge.isDryRunning
                                          ? "Running safe dry test..."
                                          : "Run Dry Test"
                                    enabled: bridge.canRunDryRun
                                    onClicked: bridge.runDryRun()
                                }
                            }
                        }

                        GlassCard {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.preferredWidth: 0.95
                            fillColor: window.cardColor
                            edgeColor: window.cardEdge
                            darkSurface: window.darkMode

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 18
                                spacing: 10

                                RowLayout {
                                    Layout.fillWidth: true

                                    Text {
                                        Layout.fillWidth: true
                                        text: "Live Status"
                                        color: window.ink
                                        font.pixelSize: 18
                                        font.weight: Font.DemiBold
                                    }

                                    Button {
                                        text: "↻"
                                        width: 34
                                        height: 34
                                        enabled: !bridge.isDryRunning
                                        onClicked: bridge.refreshBackends()
                                        contentItem: Text {
                                            text: parent.text
                                            color: window.purple
                                            font.pixelSize: 18
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                        background: Rectangle {
                                            radius: 10
                                            color: parent.hovered
                                                   ? "#1f7656ed"
                                                   : "transparent"
                                        }
                                    }
                                }

                                Repeater {
                                    model: [
                                        {
                                            symbol: bridge.backendCount > 0 ? "✓" : "!",
                                            icon: bridge.backendCount > 0
                                                  ? Qt.resolvedUrl("assets/icons/check.svg")
                                                  : "",
                                            title: bridge.statusTitle,
                                            detail: bridge.statusDetail,
                                            accent: bridge.backendCount > 0
                                                    ? window.green
                                                    : window.orange
                                        },
                                        {
                                            symbol: "◆",
                                            icon: "",
                                            title: "Qt Quick shell",
                                            detail: "Premium visual layer active",
                                            accent: window.purple
                                        },
                                        {
                                            symbol: "○",
                                            icon: "",
                                            title: bridge.isScanning
                                                   ? "Scanning source"
                                                   : "Source scan",
                                            detail: bridge.sourceFolder.length > 0
                                                    ? bridge.sourceDetail
                                                    : "Choose a source folder",
                                            accent: window.blue
                                        }
                                    ]

                                    delegate: RowLayout {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        spacing: 11

                                        ClayBadge {
                                            Layout.preferredWidth: 38
                                            Layout.preferredHeight: 38
                                            iconSource: modelData.icon
                                            symbol: modelData.symbol
                                            symbolSize: 14
                                            accent: modelData.accent
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 3
                                            Text {
                                                Layout.fillWidth: true
                                                text: modelData.title
                                                color: window.ink
                                                font.pixelSize: 12
                                                font.weight: Font.DemiBold
                                                elide: Text.ElideRight
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: modelData.detail
                                                color: window.muted
                                                font.pixelSize: 10
                                                wrapMode: Text.WordWrap
                                                maximumLineCount: 2
                                            }
                                        }
                                    }
                                }

                                Item { Layout.fillHeight: true }

                                Text {
                                    Layout.fillWidth: true
                                    text: bridge.backendNames.length > 0
                                          ? "Available: " + bridge.backendNames.join(", ")
                                          : "No backend detected"
                                    color: window.muted
                                    font.pixelSize: 10
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }

                    GlassCard {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 90
                        Layout.minimumHeight: 90
                        fillColor: window.cardColor
                        edgeColor: window.cardEdge
                        darkSurface: window.darkMode

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 20
                            spacing: 22

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        Layout.fillWidth: true
                                        text: "Build progress"
                                        color: window.ink
                                        font.pixelSize: 15
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        text: bridge.buildStatusText
                                        color: window.muted
                                        font.pixelSize: 12
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12

                                    PremiumProgressBar {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 13
                                        value: bridge.buildProgress
                                        trackColor: window.darkMode
                                                    ? "#30364d"
                                                    : "#e8e8f1"
                                    }

                                    Text {
                                        text: bridge.buildProgressPercent + "%"
                                        color: window.ink
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                    }
                                }
                            }

                            Rectangle {
                                Layout.preferredWidth: 1
                                Layout.fillHeight: true
                                color: window.darkMode ? "#3b425b" : "#e4e3ec"
                            }

                            RowLayout {
                                Layout.preferredWidth: 260
                                spacing: 12

                                ClayBadge {
                                    Layout.preferredWidth: 48
                                    Layout.preferredHeight: 48
                                    iconSource: Qt.resolvedUrl("assets/icons/disc.svg")
                                    iconSize: 31
                                    symbolSize: 16
                                    accent: window.blue
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Text {
                                        text: "Output"
                                        color: window.ink
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: bridge.lastExecutionOutput.length > 0
                                              ? bridge.lastExecutionOutput + " (dry run)"
                                              : (bridge.sourceFolder.length > 0
                                                 ? bridge.outputPreview
                                                 : "No ISO output yet")
                                        color: window.muted
                                        font.pixelSize: 11
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    WindowResizeHandle {
        targetWindow: window
        edges: Qt.LeftEdge
        resizeCursor: Qt.SizeHorCursor
        enabled: window.visibility !== Window.Maximized
        anchors.left: shell.left
        anchors.top: shell.top
        anchors.bottom: shell.bottom
        width: 8
    }

    WindowResizeHandle {
        targetWindow: window
        edges: Qt.RightEdge
        resizeCursor: Qt.SizeHorCursor
        enabled: window.visibility !== Window.Maximized
        anchors.right: shell.right
        anchors.top: shell.top
        anchors.bottom: shell.bottom
        width: 8
    }

    WindowResizeHandle {
        targetWindow: window
        edges: Qt.TopEdge
        resizeCursor: Qt.SizeVerCursor
        enabled: window.visibility !== Window.Maximized
        anchors.left: shell.left
        anchors.right: shell.right
        anchors.top: shell.top
        height: 8
    }

    WindowResizeHandle {
        targetWindow: window
        edges: Qt.BottomEdge
        resizeCursor: Qt.SizeVerCursor
        enabled: window.visibility !== Window.Maximized
        anchors.left: shell.left
        anchors.right: shell.right
        anchors.bottom: shell.bottom
        height: 8
    }

    WindowResizeHandle {
        targetWindow: window
        edges: Qt.LeftEdge | Qt.TopEdge
        resizeCursor: Qt.SizeFDiagCursor
        enabled: window.visibility !== Window.Maximized
        anchors.left: shell.left
        anchors.top: shell.top
        width: 16
        height: 16
    }

    WindowResizeHandle {
        targetWindow: window
        edges: Qt.RightEdge | Qt.TopEdge
        resizeCursor: Qt.SizeBDiagCursor
        enabled: window.visibility !== Window.Maximized
        anchors.right: shell.right
        anchors.top: shell.top
        width: 16
        height: 16
    }

    WindowResizeHandle {
        targetWindow: window
        edges: Qt.LeftEdge | Qt.BottomEdge
        resizeCursor: Qt.SizeBDiagCursor
        enabled: window.visibility !== Window.Maximized
        anchors.left: shell.left
        anchors.bottom: shell.bottom
        width: 16
        height: 16
    }

    WindowResizeHandle {
        targetWindow: window
        edges: Qt.RightEdge | Qt.BottomEdge
        resizeCursor: Qt.SizeFDiagCursor
        enabled: window.visibility !== Window.Maximized
        anchors.right: shell.right
        anchors.bottom: shell.bottom
        width: 16
        height: 16
    }
}
