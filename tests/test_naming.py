import tempfile
import unittest
from pathlib import Path

try:
    from iso_builder.naming import (
        auto_names_from_source,
        clean_volume_label,
        normalize_iso_name,
        resolve_build_paths,
        safe_path_component,
    )
except ModuleNotFoundError:
    from universal_iso_builder_v1_4_1 import (
        auto_names_from_source,
        clean_volume_label,
        normalize_iso_name,
        resolve_build_paths,
        safe_path_component,
    )


class NamingTests(unittest.TestCase):
    def test_clean_volume_label(self) -> None:
        self.assertEqual(clean_volume_label("  My Setup 2026!  "), "MY_SETUP_2026")
        self.assertEqual(clean_volume_label(""), "SOFTWARE_SETUP")
        self.assertEqual(clean_volume_label("a" * 40), "A" * 32)

    def test_normalize_iso_name(self) -> None:
        self.assertEqual(normalize_iso_name("setup"), "setup.iso")
        self.assertEqual(normalize_iso_name("setup.ISO"), "setup.ISO")
        self.assertEqual(normalize_iso_name('bad<>:"/\\|?*name'), "bad_________name.iso")

    def test_safe_path_component_reserved_windows_names(self) -> None:
        reserved = ["CON", "PRN", "AUX", "NUL"]
        reserved.extend(f"COM{i}" for i in range(1, 10))
        reserved.extend(f"LPT{i}" for i in range(1, 10))

        for name in reserved:
            with self.subTest(name=name):
                self.assertEqual(safe_path_component(name), f"{name}_SETUP")

        self.assertEqual(safe_path_component("COM10"), "COM10")
        self.assertEqual(safe_path_component("bad:name. "), "bad_name")
        self.assertEqual(len(safe_path_component("x" * 200)), 120)

    def test_auto_names_from_source(self) -> None:
        safe_base, iso_name, label = auto_names_from_source(Path("C:/Source/My Setup"))
        self.assertEqual(safe_base, "My Setup")
        self.assertEqual(iso_name, "My Setup.iso")
        self.assertEqual(label, "MY_SETUP")

    def test_resolve_build_paths_rejects_blank_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "Source folder select karo"):
            resolve_build_paths("", "C:/", "test.iso", "TEST", False)

        with tempfile.TemporaryDirectory() as source_dir:
            with self.assertRaisesRegex(ValueError, "Output folder select karo"):
                resolve_build_paths(source_dir, "", "test.iso", "TEST", False)

    def test_resolve_build_paths_rejects_output_inside_source(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir:
            with self.assertRaisesRegex(ValueError, "source folder ke andar"):
                resolve_build_paths(
                    source_dir,
                    source_dir,
                    "nested.iso",
                    "NESTED",
                    False,
                )

    def test_resolve_build_paths_manual_mode(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            output.mkdir()

            resolved_source, output_iso, label, iso_name = resolve_build_paths(
                str(source),
                str(output),
                "Manual Name",
                "Manual Label",
                False,
            )

            self.assertEqual(resolved_source, source.resolve())
            self.assertEqual(output_iso, (output / "Manual Name.iso").resolve())
            self.assertEqual(label, "MANUAL_LABEL")
            self.assertEqual(iso_name, "Manual Name.iso")


if __name__ == "__main__":
    unittest.main()
