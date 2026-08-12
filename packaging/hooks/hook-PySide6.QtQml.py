"""Collect only QML modules used by Universal ISO Builder.

PyInstaller's generic QtQml hook intentionally collects the complete PySide6 QML tree.
This application uses the Basic controls style and the modules listed below; the list is
derived from repository QML imports and pyside6-qmlimportscanner output.
"""

from pathlib import Path, PurePath

from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info


hiddenimports, binaries, datas = add_qt6_dependencies(__file__)

QML_MODULES = (
    "QtQuick",
    "QtQml",
    "QtQml/Models",
    "QtQml/WorkerScript",
    "QtQuick/Controls",
    "QtQuick/Controls/Basic",
    "QtQuick/Controls/Basic/impl",
    "QtQuick/Controls/impl",
    "QtQuick/Templates",
    "QtQuick/Effects",
    "QtQuick/Layouts",
    "QtQuick/Shapes",
    "QtQuick/Window",
    "QtQuick/Dialogs",
    "QtQuick/Dialogs/quickimpl",
    "Qt/labs/folderlistmodel",
)

qml_source_root = Path(pyside6_library_info.location["QmlImportsPath"]).resolve()
qml_destination_root = PurePath(pyside6_library_info.qt_rel_dir) / "qml"

for module in QML_MODULES:
    module_path = qml_source_root / module
    qmldir_file = module_path / "qmldir"
    if not qmldir_file.is_file():
        raise RuntimeError(f"Required PySide6 QML module is missing: {module}")

    module_binaries, module_datas = pyside6_library_info._process_qml_plugin(qmldir_file)
    destination = str(qml_destination_root / module)
    binaries += [(str(source), destination) for source in module_binaries]
    datas += [(str(source), destination) for source in module_datas]
