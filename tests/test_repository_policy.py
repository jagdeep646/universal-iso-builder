import unittest
from pathlib import Path


class RepositoryPolicyTests(unittest.TestCase):
    def test_line_endings_are_explicit_and_cross_platform(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        attributes = (project_root / ".gitattributes").read_text(encoding="utf-8")

        self.assertIn("* text=auto", attributes)
        self.assertIn("*.py text eol=lf", attributes)
        self.assertIn("*.qml text eol=lf", attributes)
        self.assertIn("*.svg text eol=lf", attributes)
        self.assertIn("*.txt text eol=lf", attributes)
        self.assertIn("*.bat text eol=crlf", attributes)
        self.assertIn("*.cmd text eol=crlf", attributes)
        self.assertIn("*.ps1 text eol=crlf", attributes)
        self.assertIn("*.exe binary", attributes)
        self.assertIn("*.iso binary", attributes)


if __name__ == "__main__":
    unittest.main()
