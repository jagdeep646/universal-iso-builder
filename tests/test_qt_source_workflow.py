import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

try:
    from PySide6.QtCore import QCoreApplication, QUrl
except ImportError:  # pragma: no cover - core-only environments skip Qt tests
    QCoreApplication = None
    QUrl = None

from iso_builder.models import ScanResult


@unittest.skipIf(QCoreApplication is None, "PySide6 GUI dependency is not installed")
class QtSourceWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QCoreApplication.instance() or QCoreApplication([])

    def wait_until(self, predicate, timeout: float = 2.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.application.processEvents()
            if predicate():
                return
            time.sleep(0.005)
        self.fail("Timed out waiting for Qt source workflow state")

    def test_source_selection_auto_names_and_scans_off_calling_thread(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        calling_thread = threading.get_ident()
        scan_threads = []

        def scanner(source: Path, profile: str, include_hidden: bool) -> ScanResult:
            scan_threads.append(threading.get_ident())
            self.assertEqual(source.name, "My Setup")
            self.assertEqual(profile, "Auto - Best Compatible")
            self.assertTrue(include_hidden)
            return ScanResult(files=3, dirs=2, total_bytes=4096)

        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "My Setup"
            source.mkdir()
            bridge = QtIsoBridge(detector=lambda: [], scanner=scanner)

            bridge.selectSourceFolder(QUrl.fromLocalFile(str(source)))
            self.assertTrue(bridge.isScanning)
            self.wait_until(lambda: not bridge.isScanning)

            self.assertEqual(bridge.sourceFolder, str(source.resolve()))
            self.assertEqual(bridge.sourceName, "My Setup")
            self.assertEqual(bridge.volumeLabel, "MY_SETUP")
            self.assertEqual(bridge.isoName, "My Setup.iso")
            self.assertEqual(bridge.scanFiles, 3)
            self.assertEqual(bridge.scanFolders, 2)
            self.assertEqual(bridge.scanSizeText, "4.00 KB")
            self.assertEqual(bridge.scanWarnings, 0)
            self.assertEqual(bridge.sourceDetail, "3 files • 4.00 KB")

        self.assertEqual(len(scan_threads), 1)
        self.assertNotEqual(scan_threads[0], calling_thread)

    def test_invalid_source_is_rejected_without_starting_scan(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        scanner_called = False

        def scanner(_source: Path, _profile: str, _include_hidden: bool):
            nonlocal scanner_called
            scanner_called = True
            return ScanResult()

        bridge = QtIsoBridge(detector=lambda: [], scanner=scanner)
        bridge.selectSourceFolder(QUrl.fromLocalFile(r"Z:\missing-source"))

        self.assertFalse(scanner_called)
        self.assertFalse(bridge.isScanning)
        self.assertEqual(bridge.sourceFolder, "")
        self.assertEqual(bridge.sourceName, "Invalid source")
        self.assertIn("not available", bridge.sourceDetail)

    def test_scan_failure_is_reported_without_crashing_qt_state(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        def scanner(_source: Path, _profile: str, _include_hidden: bool):
            raise PermissionError("controlled unreadable source")

        with TemporaryDirectory() as temporary:
            bridge = QtIsoBridge(detector=lambda: [], scanner=scanner)
            bridge.selectSourceFolder(QUrl.fromLocalFile(temporary))
            self.wait_until(lambda: not bridge.isScanning)

        self.assertEqual(bridge.scanFiles, 0)
        self.assertIn("controlled unreadable source", bridge.sourceDetail)

    def test_stale_scan_result_cannot_replace_newer_source(self) -> None:
        from iso_builder.gui.qt_bridge import QtIsoBridge

        release_first = threading.Event()

        def scanner(source: Path, _profile: str, _include_hidden: bool) -> ScanResult:
            if source.name == "First":
                release_first.wait(timeout=2)
                return ScanResult(files=99, total_bytes=99)
            return ScanResult(files=2, total_bytes=2048)

        with TemporaryDirectory() as temporary:
            first = Path(temporary) / "First"
            second = Path(temporary) / "Second"
            first.mkdir()
            second.mkdir()
            bridge = QtIsoBridge(detector=lambda: [], scanner=scanner)

            bridge.selectSourceFolder(QUrl.fromLocalFile(str(first)))
            bridge.selectSourceFolder(QUrl.fromLocalFile(str(second)))
            self.wait_until(lambda: not bridge.isScanning)
            release_first.set()
            for _ in range(10):
                self.application.processEvents()
                time.sleep(0.005)

            self.assertEqual(bridge.sourceName, "Second")
            self.assertEqual(bridge.scanFiles, 2)
            self.assertEqual(bridge.scanSizeText, "2.00 KB")


class QtSourceQmlContractTests(unittest.TestCase):
    def test_qml_connects_real_folder_selection_and_scan_state(self) -> None:
        root = Path(__file__).resolve().parents[1]
        qml = (
            root / "iso_builder" / "gui" / "qml" / "Main.qml"
        ).read_text(encoding="utf-8")

        self.assertIn("FolderDialog", qml)
        self.assertIn("bridge.selectSourceFolder(selectedFolder)", qml)
        self.assertIn("DropArea", qml)
        self.assertIn("bridge.sourceFolder", qml)
        self.assertIn("bridge.sourceDetail", qml)
        self.assertIn("bridge.volumeLabel", qml)
        self.assertIn("bridge.isoName", qml)


if __name__ == "__main__":
    unittest.main()
