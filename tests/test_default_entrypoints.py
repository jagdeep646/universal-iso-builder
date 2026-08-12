import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DefaultEntrypointPolicyTests(unittest.TestCase):
    def read(self, filename: str) -> str:
        return (ROOT / filename).read_text(encoding="utf-8")

    def test_default_entrypoint_launches_qt_application(self) -> None:
        launcher = self.read("universal_iso_builder.py")

        self.assertIn("from iso_builder.gui.qt_app import main", launcher)
        self.assertIn("raise SystemExit(main())", launcher)
        self.assertNotIn("iso_builder.gui.app", launcher)

    def test_explicit_legacy_entrypoint_launches_tkinter_application(self) -> None:
        launcher = self.read("universal_iso_builder_legacy_tk.py")

        self.assertIn("from iso_builder.gui.app import main", launcher)
        self.assertIn("main()", launcher)
        self.assertNotIn("iso_builder.gui.qt_app", launcher)

    def test_versioned_compatibility_entrypoint_remains_tkinter(self) -> None:
        launcher = self.read("universal_iso_builder_v1_4_1.py")

        self.assertIn("from iso_builder.gui.app import main", launcher)
        self.assertNotIn("iso_builder.gui.qt_app", launcher)


if __name__ == "__main__":
    unittest.main()
