import hashlib
import json
import unittest
from pathlib import Path

try:
    from iso_builder.backends.commands import build_command
    from iso_builder.backends.detection import select_backend, select_requested_backend
    from iso_builder.backends.imapi import cleanup_temp_script_from_command
    from iso_builder.constants import (
        PROFILE_AUTO,
        PROFILE_LEGACY,
        PROFILE_MODERN,
        PROFILE_UDF_ONLY,
    )
    from iso_builder.models import Backend
except ModuleNotFoundError:
    from universal_iso_builder_v1_4_1 import (
        PROFILE_AUTO,
        PROFILE_LEGACY,
        PROFILE_MODERN,
        PROFILE_UDF_ONLY,
        Backend,
        build_command,
        cleanup_temp_script_from_command,
        select_backend,
        select_requested_backend,
    )


EXPECTED_COMMAND_SNAPSHOT_SHA256 = (
    "ed67be593b76030f068925b5d628f96c2d84a46f38c9c8e5d8bcebceb876cad7"
)


def make_backend(
    name: str,
    *,
    supports_udf: bool = True,
    supports_joliet: bool = True,
) -> Backend:
    return Backend(
        name=name,
        executable=f"/tools/{name}",
        priority=1,
        description="test",
        supports_udf=supports_udf,
        supports_joliet=supports_joliet,
        supports_iso_level3=True,
        source="test",
    )


class BackendSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.first = make_backend(
            "first",
            supports_udf=False,
            supports_joliet=False,
        )
        self.udf = make_backend(
            "udf",
            supports_udf=True,
            supports_joliet=False,
        )
        self.joliet = make_backend(
            "joliet",
            supports_udf=False,
            supports_joliet=True,
        )
        self.backends = [self.first, self.udf, self.joliet]

    def test_select_backend_across_profiles(self) -> None:
        self.assertIs(select_backend(self.backends, PROFILE_AUTO), self.udf)
        self.assertIs(select_backend(self.backends, PROFILE_MODERN), self.udf)
        self.assertIs(select_backend(self.backends, PROFILE_UDF_ONLY), self.udf)
        self.assertIs(select_backend(self.backends, PROFILE_LEGACY), self.joliet)

    def test_udf_only_has_no_fallback_to_non_udf_backend(self) -> None:
        self.assertIsNone(select_backend([self.first], PROFILE_UDF_ONLY))

    def test_auto_and_modern_preserve_non_udf_fallback(self) -> None:
        self.assertIs(select_backend([self.first], PROFILE_AUTO), self.first)
        self.assertIs(select_backend([self.first], PROFILE_MODERN), self.first)
        self.assertIsNone(select_backend([], PROFILE_AUTO))

    def test_select_requested_backend_auto_and_explicit(self) -> None:
        self.assertIs(
            select_requested_backend(self.backends, "Auto", PROFILE_AUTO),
            self.udf,
        )
        choice = f"{self.joliet.name} | {self.joliet.executable}"
        self.assertIs(
            select_requested_backend(self.backends, choice, PROFILE_AUTO),
            self.joliet,
        )
        udf_choice = f"{self.udf.name} | {self.udf.executable}"
        self.assertIs(
            select_requested_backend(self.backends, udf_choice, PROFILE_UDF_ONLY),
            self.udf,
        )

    def test_udf_only_auto_rejects_when_no_udf_backend_exists(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "No UDF-capable ISO backend found"):
            select_requested_backend([self.first], "Auto", PROFILE_UDF_ONLY)

    def test_udf_only_rejects_explicit_non_udf_backend(self) -> None:
        choice = f"{self.joliet.name} | {self.joliet.executable}"
        with self.assertRaisesRegex(RuntimeError, "does not support UDF"):
            select_requested_backend(self.backends, choice, PROFILE_UDF_ONLY)

    def test_select_requested_backend_rejects_missing_backend(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "No ISO backend found"):
            select_requested_backend([], "Auto", PROFILE_AUTO)
        with self.assertRaisesRegex(RuntimeError, "Selected backend not found"):
            select_requested_backend(self.backends, "missing", PROFILE_AUTO)


class BackendCommandTests(unittest.TestCase):
    def test_all_backend_command_snapshots(self) -> None:
        source = Path("C:/Source Folder")
        output = Path("D:/Output Folder/Test.iso")
        cases = [
            ("oscdimg", PROFILE_AUTO, True, False),
            ("oscdimg", PROFILE_UDF_ONLY, False, True),
            ("oscdimg", PROFILE_LEGACY, True, True),
            ("xorriso", PROFILE_AUTO, True, True),
            ("xorriso", PROFILE_LEGACY, True, False),
            ("genisoimage", PROFILE_MODERN, True, False),
            ("mkisofs", PROFILE_LEGACY, True, False),
            ("powershell_imapi", PROFILE_UDF_ONLY, True, True),
            ("hdiutil", PROFILE_AUTO, True, True),
            ("hdiutil", PROFILE_LEGACY, True, False),
        ]
        snapshots = []

        for name, profile, include_hidden, optimize_duplicates in cases:
            backend = make_backend(name)
            command, warnings = build_command(
                backend,
                source,
                output,
                "R5_LABEL",
                profile,
                include_hidden,
                optimize_duplicates,
            )
            normalized = list(command)
            try:
                if "-File" in normalized:
                    script_index = normalized.index("-File") + 1
                    normalized[script_index] = "<TEMP_PS1>"
                snapshots.append(
                    {
                        "case": [name, profile, include_hidden, optimize_duplicates],
                        "command": normalized,
                        "warnings": warnings,
                    }
                )
            finally:
                cleanup_temp_script_from_command(command)

        canonical = json.dumps(
            snapshots,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        actual_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.assertEqual(actual_hash, EXPECTED_COMMAND_SNAPSHOT_SHA256)

    def test_powershell_temp_script_lifecycle(self) -> None:
        backend = make_backend("powershell_imapi")
        command, _ = build_command(
            backend,
            Path("C:/Source"),
            Path("D:/Output/Test.iso"),
            "TEST",
            PROFILE_AUTO,
            True,
            False,
        )
        script_path = Path(command[command.index("-File") + 1])

        self.assertTrue(script_path.exists())
        cleanup_temp_script_from_command(command)
        self.assertFalse(script_path.exists())

    def test_unsupported_backend_guard(self) -> None:
        backend = make_backend("unknown")
        with self.assertRaisesRegex(ValueError, "Unsupported backend: unknown"):
            build_command(
                backend,
                Path("source"),
                Path("output.iso"),
                "LABEL",
                PROFILE_AUTO,
                True,
                False,
            )


if __name__ == "__main__":
    unittest.main()
