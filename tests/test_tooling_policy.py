import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ToolingPolicyTests(unittest.TestCase):
    def test_uv_dependencies_are_pinned(self) -> None:
        config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(config["project"]["requires-python"], ">=3.14,<3.15")
        self.assertEqual(config["project"]["dependencies"], ["PySide6==6.11.1"])
        self.assertEqual(
            config["dependency-groups"]["dev"],
            [
                "pre-commit==4.6.0",
                "pyinstaller==6.21.0",
                "pytest==9.0.3",
                "ruff==0.16.0",
            ],
        )
        self.assertFalse(config["tool"]["uv"]["package"])
        self.assertEqual(config["tool"]["pytest"]["ini_options"]["pythonpath"], ["."])

    def test_ruff_uses_a_surgical_lint_baseline(self) -> None:
        config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(config["tool"]["ruff"]["target-version"], "py314")
        self.assertEqual(config["tool"]["ruff"]["lint"]["select"], ["E4", "E7", "E9", "F"])

    def test_pre_commit_has_lint_lock_secret_and_test_gates(self) -> None:
        config = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")

        self.assertIn("rev: v0.16.0", config)
        self.assertIn("id: ruff-check", config)
        self.assertIn("rev: v8.28.0", config)
        self.assertIn("id: gitleaks", config)
        self.assertIn("entry: uv lock --check", config)
        self.assertIn("entry: uv run pytest -q", config)
        self.assertIn("stages: [pre-push]", config)

    def test_repository_guidelines_preserve_verified_behavior(self) -> None:
        guidelines = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("Do not present an unverified claim as fact", guidelines)
        self.assertIn("Keep changes surgical", guidelines)
        self.assertIn("Do not add antivirus bypasses", guidelines)
        self.assertIn("Run focused tests first", guidelines)

    def test_local_tool_caches_are_ignored(self) -> None:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn(".uv-cache/", gitignore)
        self.assertIn(".pre-commit-cache/", gitignore)


if __name__ == "__main__":
    unittest.main()
