import unittest
from pathlib import Path

import iso_builder
from iso_builder.constants import APP_NAME, APP_VERSION


class VersionTests(unittest.TestCase):
    def test_runtime_and_package_versions_are_2_0(self) -> None:
        self.assertEqual(APP_NAME, "Universal ISO Builder")
        self.assertEqual(APP_VERSION, "2.0")
        self.assertEqual(iso_builder.__version__, APP_VERSION)

    def test_windows_exe_metadata_is_version_2_0(self) -> None:
        version_file = Path(__file__).resolve().parents[1] / "windows_version_info.txt"
        content = version_file.read_text(encoding="utf-8")

        self.assertIn("filevers=(2, 0, 0, 0)", content)
        self.assertIn("prodvers=(2, 0, 0, 0)", content)
        self.assertIn("StringStruct(u'FileVersion', u'2.0')", content)
        self.assertIn("StringStruct(u'ProductVersion', u'2.0')", content)


if __name__ == "__main__":
    unittest.main()
