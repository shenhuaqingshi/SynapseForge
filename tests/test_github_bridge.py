from pathlib import Path
import pytest
from synapseforge.config import ProjectConfig, SectionSpec
from synapseforge.github_bridge.ci_reporter import CIReporter
from synapseforge.github_bridge.issue_orchestrator import IssueTaskOrchestrator
from synapseforge.github_bridge.pr_reviewer import PRReviewRunner
from synapseforge.linters import LintSuite


def test_issue_orchestrator(tmp_path):
    config = ProjectConfig(
        name="test",
        sections=[
            SectionSpec(id="sec_01", title="Intro", file="sections/01.md", assigned_role="drafter"),
        ],
        root_dir=tmp_path,
    )
    orch = IssueTaskOrchestrator(project_root=tmp_path, config=config)
    issue_data = {
        "title": "[Task: sec_01] Write Introduction Section",
        "body": "Draft the background and problem statement.",
        "number": 42,
        "user": {"login": "octocat"},
    }
    res = orch.process_issue(issue_data)
    assert res["status"] == "claimed"
    assert res["section_id"] == "sec_01"
    assert res["actor"] == "octocat"
