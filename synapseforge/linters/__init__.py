"""
Unified Linter Suite for SynapseForge Collaborative Documents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from synapseforge.config import QualityGateConfig
from synapseforge.linters.anti_ai import AntiAILinter, LintIssue, LintResult
from synapseforge.linters.citations import CitationLinter
from synapseforge.linters.coherence import CoherenceLinter
from synapseforge.linters.style import StyleLinter


@dataclass
class SuiteLintReport:
    target_path: str
    passed: bool
    total_errors: int
    total_warnings: int
    results: List[LintResult] = field(default_factory=list)

    @property
    def all_issues(self) -> List[LintIssue]:
        issues = []
        for r in self.results:
            issues.extend(r.issues)
        return issues


class LintSuite:
    """Orchestrates all document quality linters."""

    def __init__(self, quality_gates: Optional[QualityGateConfig] = None, bib_file: Optional[Path] = None, glossary: Optional[Dict[str, str]] = None):
        qg = quality_gates or QualityGateConfig()
        self.anti_ai = AntiAILinter(qg.anti_ai)
        self.coherence = CoherenceLinter(qg.coherence, glossary=glossary)
        self.style = StyleLinter(qg.style)
        self.citations = CitationLinter(bib_path=bib_file, config=qg.citations)

    def lint_file(self, file_path: Path | str) -> SuiteLintReport:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Cannot lint nonexistent file: {p}")
        text = p.read_text(encoding="utf-8")
        return self.lint_text(text, filename=str(p))

    def lint_text(self, text: str, filename: str = "document.md") -> SuiteLintReport:
        results = [
            self.anti_ai.lint_text(text, filename=filename),
            self.coherence.lint_text(text),
            self.style.lint_text(text),
            self.citations.lint_text(text),
        ]
        total_errors = sum(r.error_count for r in results)
        total_warnings = sum(r.warning_count for r in results)
        passed = (total_errors == 0)

        return SuiteLintReport(
            target_path=filename,
            passed=passed,
            total_errors=total_errors,
            total_warnings=total_warnings,
            results=results,
        )


__all__ = [
    "LintIssue",
    "LintResult",
    "SuiteLintReport",
    "LintSuite",
    "AntiAILinter",
    "CoherenceLinter",
    "StyleLinter",
    "CitationLinter",
]
