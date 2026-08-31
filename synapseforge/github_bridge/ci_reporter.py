"""
CI Reporter and GitHub Actions Check Run Formatter.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from synapseforge.linters import SuiteLintReport


class CIReporter:
    """Formats linter and audit results into GitHub Actions friendly outputs."""

    @staticmethod
    def _escape_workflow_command(value: str) -> str:
        """Escapes reserved characters for GitHub Actions workflow command properties/data."""
        return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")

    @staticmethod
    def print_github_annotations(report: SuiteLintReport) -> None:
        """Emits workflow command annotations (::error file=...,line=...::msg)."""
        for issue in report.all_issues:
            cmd = "error" if issue.severity == "error" else "warning"
            file_path = CIReporter._escape_workflow_command(report.target_path)
            message = CIReporter._escape_workflow_command(issue.message)
            print(f"::{cmd} file={file_path},line={issue.line_start},endLine={issue.line_end}::{message}")

    @staticmethod
    def generate_json_report(reports: List[SuiteLintReport], output_path: Path | str) -> None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "target_path": r.target_path,
                "passed": r.passed,
                "total_errors": r.total_errors,
                "total_warnings": r.total_warnings,
                "issues": [asdict(i) for i in r.all_issues],
            }
            for r in reports
        ]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
