"""
GitHub API and Git CLI Wrapper for SynapseForge Orchestration.
Supports authentication via GITHUB_TOKEN, gh CLI, or standard git commands.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests


class GitHubClient:
    """Provides unified methods to interact with GitHub repository, PRs, issues, and Actions."""

    def __init__(self, repo: Optional[str] = None, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        self.repo = repo or os.getenv("GITHUB_REPOSITORY")
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def get_pr_diff(self, pr_number: int) -> str:
        """Retrieves raw diff for a Pull Request."""
        if not self.repo:
            return ""
        url = f"{self.base_url}/repos/{self.repo}/pulls/{pr_number}"
        headers = dict(self.headers)
        headers["Accept"] = "application/vnd.github.v3.diff"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        return ""

    def get_pr_files(self, pr_number: int) -> List[Dict[str, Any]]:
        """Retrieves list of changed files in a PR."""
        if not self.repo:
            return []
        url = f"{self.base_url}/repos/{self.repo}/pulls/{pr_number}/files"
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return []

    def post_pr_review(self, pr_number: int, commit_id: str, body: str, event: str = "COMMENT", comments: Optional[List[Dict[str, Any]]] = None) -> bool:
        """Submits a formal PR review with summary body and inline comments."""
        if not self.repo or not self.token:
            # Fallback to printing locally if running in offline test mode
            return False
        url = f"{self.base_url}/repos/{self.repo}/pulls/{pr_number}/reviews"
        payload: Dict[str, Any] = {
            "commit_id": commit_id,
            "body": body,
            "event": event,
            "comments": comments or [],
        }
        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=15)
            return resp.status_code in (200, 201)
        except Exception:
            return False

    def post_issue_comment(self, issue_or_pr_number: int, body: str) -> bool:
        """Posts a general markdown comment to an Issue or PR."""
        if not self.repo or not self.token:
            return False
        url = f"{self.base_url}/repos/{self.repo}/issues/{issue_or_pr_number}/comments"
        try:
            resp = requests.post(url, headers=self.headers, json={"body": body}, timeout=15)
            return resp.status_code in (200, 201)
        except Exception:
            return False

    @staticmethod
    def append_step_summary(markdown_content: str) -> None:
        """Appends markdown to $GITHUB_STEP_SUMMARY in GitHub Actions."""
        summary_file = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_file and Path(summary_file).parent.exists():
            with open(summary_file, "a", encoding="utf-8") as f:
                f.write(f"\n{markdown_content}\n")
