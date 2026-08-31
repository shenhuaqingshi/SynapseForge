"""
Automated Multi-Agent PR Peer Review Runner.
Executes quality gate linters and autonomous agent review matrix on Pull Request diffs.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from synapseforge.agents.critic import CriticAgent
from synapseforge.agents.harmonizer import HarmonizerAgent
from synapseforge.config import ProjectConfig, load_config
from synapseforge.github_bridge.client import GitHubClient
from synapseforge.linters import LintSuite


class PRReviewRunner:
    """Runs automated multi-agent PR peer review and produces GitHub PR comments."""

    def __init__(self, project_root: Optional[Path] = None, config: Optional[ProjectConfig] = None):
        self.project_root = project_root or Path.cwd()
        self.config = config or load_config(self.project_root / "synapseforge.yaml")
        
        bib_file = self.project_root / self.config.quality_gates.citations.get("bib_file", "bibliography.bib")
        self.lint_suite = LintSuite(
            quality_gates=self.config.quality_gates,
            bib_file=bib_file,
            glossary=self.config.glossary,
        )
        self.critic_agent = CriticAgent()
        self.harmonizer_agent = HarmonizerAgent()
        self.gh_client = GitHubClient()

    def get_changed_markdown_files(self, base_ref: str = "main") -> List[Path]:
        """Detects changed markdown files via local git diff against base branch."""
        try:
            cmd = ["git", "diff", "--name-only", f"{base_ref}...HEAD"]
            out = subprocess.check_output(cmd, cwd=self.project_root, text=True, stderr=subprocess.DEVNULL)
            files = [
                self.project_root / line.strip()
                for line in out.splitlines()
                if line.strip().endswith(".md") and (self.project_root / line.strip()).exists()
            ]
            return files
        except Exception:
            # Fallback: return all markdown files in sections/
            sec_dir = self.project_root / "sections"
            if sec_dir.exists():
                return list(sec_dir.glob("*.md"))
            return list(self.project_root.glob("*.md"))

    def review_file(self, file_path: Path) -> Dict[str, Any]:
        """Runs full linter suite and agent reviews on a single markdown file."""
        text = file_path.read_text(encoding="utf-8")
        rel_path = file_path.relative_to(self.project_root) if file_path.is_relative_to(self.project_root) else file_path

        # 1. Lint Suite
        lint_report = self.lint_suite.lint_text(text, filename=str(rel_path))

        # 2. Agent Critic
        critic_feedbacks = self.critic_agent.review_section(text, section_id=file_path.stem)

        # 3. Agent Harmonizer
        harmonizer_feedbacks = self.harmonizer_agent.review_transitions("", text, curr_section_id=file_path.stem)

        return {
            "file": str(rel_path),
            "lint_report": lint_report,
            "critic_feedbacks": critic_feedbacks,
            "harmonizer_feedbacks": harmonizer_feedbacks,
            "passed": lint_report.passed and (len([f for f in critic_feedbacks if f.severity == "blocking"]) == 0),
        }

    def run_full_pr_review(self, base_ref: str = "main", pr_number: Optional[int] = None) -> Dict[str, Any]:
        changed_files = self.get_changed_markdown_files(base_ref)
        file_results = [self.review_file(f) for f in changed_files]

        all_passed = all(r["passed"] for r in file_results) if file_results else True
        total_errors = sum(r["lint_report"].total_errors for r in file_results)
        total_warnings = sum(r["lint_report"].total_warnings for r in file_results)
        total_critic_suggestions = sum(len(r["critic_feedbacks"]) for r in file_results)

        # Build GitHub PR review summary markdown
        summary_md = self._generate_pr_summary_markdown(
            file_results=file_results,
            all_passed=all_passed,
            total_errors=total_errors,
            total_warnings=total_warnings,
            total_critic_suggestions=total_critic_suggestions,
        )

        # Post to GitHub Step Summary if in Actions
        self.gh_client.append_step_summary(summary_md)

        # If PR number given and in CI, post comment
        if pr_number:
            self.gh_client.post_issue_comment(pr_number, summary_md)

        return {
            "all_passed": all_passed,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "total_critic_suggestions": total_critic_suggestions,
            "file_results": file_results,
            "summary_markdown": summary_md,
        }

    def _generate_pr_summary_markdown(
        self,
        file_results: List[Dict[str, Any]],
        all_passed: bool,
        total_errors: int,
        total_warnings: int,
        total_critic_suggestions: int,
    ) -> str:
        status_badge = "✅ **QUALITY GATES PASSED**" if all_passed else "❌ **CHANGES REQUESTED**"
        
        md = [
            f"## 🤖 SynapseForge Swarm Peer Review Report",
            f"",
            f"**Status**: {status_badge}",
            f"**Inspected Files**: {len(file_results)} | **Errors**: {total_errors} | **Warnings**: {total_warnings} | **Agent Suggestions**: {total_critic_suggestions}",
            f"",
            f"| File | Anti-AI Gate | Coherence | Style & Booktabs | Critic Agent | Result |",
            f"|---|:---:|:---:|:---:|:---:|:---:|",
        ]

        for r in file_results:
            lint = r["lint_report"]
            anti_ai_ok = "✅" if lint.results[0].error_count == 0 else f"❌ ({lint.results[0].error_count})"
            coherence_ok = "✅" if lint.results[1].error_count == 0 else f"❌ ({lint.results[1].error_count})"
            style_ok = "✅" if lint.results[2].error_count == 0 else f"⚠️ ({lint.results[2].warning_count})"
            critic_count = len(r["critic_feedbacks"])
            critic_status = f"{critic_count} notes" if critic_count > 0 else "Clear"
            verdict = "PASS" if r["passed"] else "FAIL"
            md.append(f"| `{r['file']}` | {anti_ai_ok} | {coherence_ok} | {style_ok} | {critic_status} | **{verdict}** |")

        md.append("")
        # Section issues breakdown
        for r in file_results:
            issues = r["lint_report"].all_issues
            if issues or r["critic_feedbacks"]:
                md.append(f"### 🔍 Detailed Audit for `{r['file']}`")
                for issue in issues:
                    icon = "🚨" if issue.severity == "error" else "⚠️"
                    md.append(f"- {icon} **[Line {issue.line_start}] {issue.linter_name}**: {issue.message}")
                    if issue.suggested_fix:
                        md.append(f"  - *Suggested Fix*: `{issue.suggested_fix}`")
                for fb in r["critic_feedbacks"]:
                    md.append(f"- 💡 **[Line {fb.line_number}] {fb.agent_role.upper()} ({fb.category})**: {fb.comment}")
                md.append("")

        md.append("---")
        md.append("*Generated automatically by SynapseForge GitOps Peer Review Bot.*")
        return "\n".join(md)
