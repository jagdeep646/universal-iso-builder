import QtQuick

Item {
    id: root

    required property var targetWindow
    required property int edges
    required property int resizeCursor

    z: 100

    HoverHandler {
        cursorShape: root.resizeCursor
    }

    DragHandler {
        target: null
        acceptedButtons: Qt.LeftButton
        grabPermissions: PointerHandler.CanTakeOverFromAnything
        onActiveChanged: {
            if (active && root.targetWindow) {
                root.targetWindow.startSystemResize(root.edges)
            }
        }
    }
}
