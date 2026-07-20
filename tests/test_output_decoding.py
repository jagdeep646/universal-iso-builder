import sys
import unittest
from unittest.mock import patch

from iso_builder import execution


class ProcessOutputDecodingTests(unittest.TestCase):
    def test_utf8_output_is_preserved_before_code_page_fallback(self) -> None:
        raw_output = "Unicode: नमस्ते café\n".encode("utf-8")

        decoded = execution.decode_process_output(
            raw_output,
            fallback_encoding="cp1252",
        )

        self.assertEqual(decoded, "Unicode: नमस्ते café\n")

    def test_windows_code_page_output_uses_fallback(self) -> None:
        raw_output = "café – résumé\n".encode("cp1252")

        decoded = execution.decode_process_output(
            raw_output,
            fallback_encoding="cp1252",
        )

        self.assertEqual(decoded, "café – résumé\n")

    def test_unknown_fallback_and_invalid_utf8_do_not_crash(self) -> None:
        decoded = execution.decode_process_output(
            b"\xff\n",
            fallback_encoding="not-a-real-code-page",
        )

        self.assertEqual(decoded, "\ufffd\n")

    def test_run_process_streams_code_page_output_without_replacement(self) -> None:
        logs = []
        child_code = (
            "import sys;"
            "sys.stdout.buffer.write("
            "bytes([99,97,102,233,32,150,32,114,233,115,117,109,233,10])"
            ")"
        )

        with patch.object(
            execution,
            "preferred_process_output_encoding",
            return_value="cp1252",
        ):
            return_code = execution.run_process(
                [sys.executable, "-c", child_code],
                logs.append,
            )

        self.assertEqual(return_code, 0)
        self.assertEqual(logs, ["café – résumé"])


if __name__ == "__main__":
    unittest.main()
