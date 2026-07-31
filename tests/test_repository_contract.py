"""Repository-level contracts for a reproducible Electronics Stack checkout."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositoryContractTests(unittest.TestCase):
    def test_agent_entrypoints_and_domain_docs_exist(self) -> None:
        expected = (
            "AGENTS.md",
            "PROJECT.md",
            "CONTEXT.md",
            "docs/agents/issue-tracker.md",
            "docs/agents/triage-labels.md",
            "docs/agents/domain.md",
            "docs/adr/0001-local-on-demand-runtime.md",
            "docs/adr/0002-quota-safe-provider-access.md",
            "docs/adr/0003-experimental-design-generation.md",
        )

        missing = [relative for relative in expected if not (ROOT / relative).is_file()]
        self.assertEqual([], missing, f"missing repository contracts: {missing}")

    def test_python_environment_is_declared(self) -> None:
        pyproject = ROOT / "pyproject.toml"
        self.assertTrue(pyproject.is_file(), "pyproject.toml is required")

        text = pyproject.read_text(encoding="utf-8")
        for dependency in (
            "mcp",
            "openpyxl",
            "pdfplumber",
            "PyYAML",
            "rapidfuzz",
            "requests",
            "sexpdata",
        ):
            self.assertIn(dependency, text)
        self.assertIn("pytest", text)

    def test_ci_runs_repository_contract_and_behavior_tests(self) -> None:
        workflow = ROOT / ".github" / "workflows" / "validate.yml"
        self.assertTrue(workflow.is_file(), "validation workflow is required")

        text = workflow.read_text(encoding="utf-8")
        self.assertIn("python -m pytest", text)
        self.assertIn("python -m compileall", text)

    def test_generated_dependencies_are_not_tracked(self) -> None:
        tracked = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        generated = [
            path
            for path in tracked
            if "__pycache__/" in path
            or path.endswith((".pyc", ".pyo"))
            or "node_modules/" in path
        ]
        self.assertEqual([], generated, f"generated dependencies are tracked: {generated}")

    def test_corpus_projects_are_materialized_from_the_manifest(self) -> None:
        tree = subprocess.run(
            ["git", "ls-files", "--stage"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        corpus_gitlinks = [
            line.rsplit("\t", 1)[-1]
            for line in tree
            if line.startswith("160000 ") and "\ttest-corpus/" in line
        ]
        self.assertEqual(
            [],
            corpus_gitlinks,
            "corpus clones must not be committed as undeclared gitlinks",
        )
        self.assertTrue((ROOT / "test-corpus" / "manifest.csv").is_file())
        self.assertTrue((ROOT / "test-corpus" / "download_all.sh").is_file())

    def test_external_tools_are_not_undeclared_gitlinks(self) -> None:
        tree = subprocess.run(
            ["git", "ls-files", "--stage"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        gitlinks = [
            line.rsplit("\t", 1)[-1]
            for line in tree
            if line.startswith("160000 ")
        ]
        self.assertEqual(
            [],
            gitlinks,
            "external tools need a declared install path, not an orphan Git link",
        )

    def test_license_matches_public_readme_claim(self) -> None:
        license_file = ROOT / "LICENSE"
        self.assertTrue(license_file.is_file(), "LICENSE is required")
        self.assertIn("MIT License", license_file.read_text(encoding="utf-8"))

    def test_public_docs_separate_current_and_historical_state(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("design draft", readme.lower())
        self.assertIn("on-demand", readme.lower())
        self.assertNotIn("/home/reidsurmeier", readme)

        for report in ("PIPELINE-FINAL.md", "PIPELINE-STATE.md"):
            text = (ROOT / report).read_text(encoding="utf-8")
            self.assertIn("historical", text.lower(), f"{report} needs a scope marker")


if __name__ == "__main__":
    unittest.main()
