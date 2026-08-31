import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from synapseforge.config import ProjectConfig, SectionSpec
from synapseforge.core.state import SectionStatus
from synapseforge.github_bridge.ci_reporter import CIReporter
from synapseforge.github_bridge.client import GitHubClient
from synapseforge.github_bridge.issue_orchestrator import IssueTaskOrchestrator
from synapseforge.github_bridge.pr_reviewer import PRReviewRunner
from synapseforge.linters import LintIssue, LintResult, LintSuite, SuiteLintReport


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


def test_get_pr_files_follows_link_header_pagination():
    """PRs with >100 changed files must not be silently truncated."""
    client = GitHubClient(repo="org/repo", token="t")
    next_url = "https://api.github.com/repos/org/repo/pulls/7/files?per_page=100&page=2"

    page1 = [{"filename": f"f{i}.py"} for i in range(100)]
    page2 = [{"filename": f"f{i}.py"} for i in range(100, 130)]

    resp1 = Mock(status_code=200, headers={"Link": f'<{next_url}>; rel="next", <{next_url}>; rel="last"'})
    resp1.json.return_value = page1
    resp2 = Mock(status_code=200, headers={})
    resp2.json.return_value = page2

    with patch("synapseforge.github_bridge.client.requests.get", side_effect=[resp1, resp2]) as mock_get:
        files = client.get_pr_files(7)

    assert len(files) == 130
    assert mock_get.call_count == 2
    assert mock_get.call_args_list[0].args[0].endswith("/repos/org/repo/pulls/7/files?per_page=100")
    assert mock_get.call_args_list[1].args[0] == next_url


def test_get_pr_files_non_200_response_is_logged(caplog):
    client = GitHubClient(repo="org/repo", token="t")
    resp = Mock(status_code=403, headers={})
    with patch("synapseforge.github_bridge.client.requests.get", return_value=resp):
        with caplog.at_level(logging.WARNING, logger="synapseforge.github_bridge.client"):
            assert client.get_pr_files(7) == []
    assert "403" in caplog.text


def test_print_github_annotations_escapes_reserved_characters(capsys):
    """% and newlines in message/file must not break workflow command parsing."""
    report = SuiteLintReport(
        target_path="sections/100%_intro.md",
        passed=False,
        total_errors=1,
        total_warnings=0,
        results=[
            LintResult(
                linter_name="test",
                passed=False,
                issues=[
                    LintIssue(
                        linter_name="test",
                        severity="error",
                        line_start=3,
                        line_end=4,
                        message="bad math 50% off\r\nsecond line",
                        snippet="",
                    )
                ],
            )
        ],
    )
    CIReporter.print_github_annotations(report)
    out = capsys.readouterr().out
    assert out == (
        "::error file=sections/100%25_intro.md,line=3,endLine=4::"
        "bad math 50%25 off%0D%0Asecond line\n"
    )


def test_process_issue_returns_locked_when_lease_held_by_other(tmp_path):
    config = ProjectConfig(
        name="test",
        sections=[
            SectionSpec(id="sec_01", title="Intro", file="sections/01.md", assigned_role="drafter"),
        ],
        root_dir=tmp_path,
    )
    orch = IssueTaskOrchestrator(project_root=tmp_path, config=config)
    assert orch.state_manager.claim_section("sec_01", actor="other-agent")
    orch.gh_client = Mock()

    res = orch.process_issue({
        "title": "[Task: sec_01] Write Introduction Section",
        "body": "Draft the background and problem statement.",
        "number": 43,
        "user": {"login": "octocat"},
    })

    assert res["status"] == "locked"
    assert res["section_id"] == "sec_01"
    assert res["holder"] == "other-agent"

    # State must not be hijacked: lock, status and branch stay with the holder.
    sec = orch.state_manager.state.sections["sec_01"]
    assert sec.status == SectionStatus.CLAIMED
    assert sec.status != SectionStatus.DRAFTING
    assert sec.branch_name is None
    assert orch.state_manager.state.active_locks["sec_01"] == "other-agent"
    orch.gh_client.post_issue_comment.assert_not_called()
