"""Parallel Qt Quick launcher used during the PySide6 GUI migration."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .qt_bridge import QtIsoBridge


QML_MAIN = Path(__file__).with_name("qml") / "Main.qml"


def _parse_args(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Universal ISO Builder Qt Quick preview")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Load the QML window and exit automatically.",
    )
    return parser.parse_args(list(arguments))


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if arguments is None else arguments)

    QQuickStyle.setStyle("Basic")
    app = QGuiApplication([sys.argv[0]])
    app.setApplicationName("Universal ISO Builder")
    app.setOrganizationName("Universal ISO Builder")
    application_font = QFont("Segoe UI")
    application_font.setPixelSize(14)
    application_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(application_font)

    engine = QQmlApplicationEngine()
    bridge = QtIsoBridge(parent=engine)
    engine.rootContext().setContextProperty("bridge", bridge)
    bridge.refreshBackends()
    engine.load(QUrl.fromLocalFile(str(QML_MAIN.resolve())))

    if not engine.rootObjects():
        print(f"QT QUICK LOAD FAILED: {QML_MAIN}", file=sys.stderr)
        return 1

    print("QT QUICK LOAD OK")
    if args.smoke_test:
        QTimer.singleShot(200, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
